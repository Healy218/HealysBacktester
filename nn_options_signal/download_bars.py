# nn_options_signal/download_bars.py
"""SPY daily bars + universe filter + resumable bulk option-bar download.

Steps:
  1. SPY daily bars (SPY_HISTORY_START -> WINDOW_END) -> spy_daily.parquet
  2. Universe filter: keep contracts whose strike lies within MONEYNESS_BAND of
     SPY's close range during the contract's entry-eligible life
     ([expiry-DTE_MAX, expiry-DTE_MIN] ∩ data window) -> universe.parquet
  3. Threaded, resumable download of each universe contract's full daily bar
     life -> data_cache/bars/bars_part_NNNN.parquet (+ bars_done.txt manifest;
     zero-bar contracts are recorded so reruns skip them)
  4. Coverage report -> reports/coverage_report.txt

Run:  python -m nn_options_signal.download_bars [--smoke] [--universe-only]
"""
import argparse
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
from dotenv import load_dotenv

from nn_options_signal import config

FLUSH_EVERY = 500          # contracts per parquet part file
_thread_local = threading.local()


def _session() -> requests.Session:
    if not hasattr(_thread_local, "s"):
        _thread_local.s = requests.Session()
    return _thread_local.s


def _get_with_retry(url: str, params: dict, attempts: int = config.MAX_RETRIES) -> dict:
    for attempt in range(attempts):
        try:
            r = _session().get(url, params=params, timeout=config.REQUEST_TIMEOUT)
        except requests.RequestException:
            time.sleep(2 ** attempt)
            continue
        if r.status_code == 429:
            # stock aggs live on a ~5 req/min tier: wait out the minute window
            time.sleep(15)
            continue
        if r.status_code >= 500:
            time.sleep(2 ** attempt)
            continue
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
        return r.json()
    raise RuntimeError(f"exhausted retries for {url}")


def _aggs(ticker: str, start: str, end: str, key: str,
          attempts: int = config.MAX_RETRIES) -> list[dict]:
    url = f"{config.MASSIVE_BASE_URL}/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}"
    body = _get_with_retry(url, {"adjusted": "true", "sort": "asc",
                                 "limit": 50000, "apiKey": key}, attempts=attempts)
    return body.get("results", [])


def download_underlyings(key: str) -> pd.DataFrame:
    frames = []
    for i, sym in enumerate(config.UNDERLYINGS):
        if i:
            time.sleep(12.5)   # stock-aggs tier: stay under 5 requests/min
        rows = _aggs(sym, config.SPY_HISTORY_START, config.WINDOW_END, key, attempts=10)
        if not rows:
            print(f"  WARNING: no underlying bars for {sym}", flush=True)
            continue
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["t"], unit="ms").dt.normalize()
        df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close",
                                "v": "volume", "vw": "vwap", "n": "transactions"})
        df["underlying"] = sym
        frames.append(df[["underlying", "date", "open", "high", "low", "close",
                          "volume", "vwap", "transactions"]])
    und = pd.concat(frames, ignore_index=True)
    und.to_parquet(config.UNDERLYING_PARQUET, index=False)
    print(f"underlying daily: {len(und)} bars across {und['underlying'].nunique()} symbols")
    return und


def _universe_for(contracts: pd.DataFrame, closes: pd.Series) -> pd.Series:
    """Boolean keep-mask for one underlying's contracts vs its own spot series."""
    win_start = pd.Timestamp(config.WINDOW_START)
    win_end = pd.Timestamp(config.WINDOW_END)

    # Entry-eligible life per contract, clipped to the data window.
    lo_d = (contracts["expiration"] - pd.Timedelta(days=config.DTE_MAX)).clip(lower=win_start)
    hi_d = (contracts["expiration"] - pd.Timedelta(days=config.DTE_MIN)).clip(upper=win_end)
    valid = lo_d <= hi_d

    idx = closes.index
    cummax = closes.cummax()
    suffix_min = closes[::-1].cummin()[::-1]
    lo_pos = idx.searchsorted(lo_d.values, side="left")
    hi_pos = idx.searchsorted(hi_d.values, side="right") - 1

    n = len(idx)
    lo_pos_c = pd.Series(lo_pos).clip(0, n - 1).values
    hi_pos_c = pd.Series(hi_pos).clip(0, n - 1).values
    # suffix_min[lo] (min from span start to end of data) and cummax[hi] (max
    # from start of data to span end) are OUTER bounds of the span's range, so
    # the band test can over-include but never drop a contract that belongs.
    span_lo = pd.Series(suffix_min.values[lo_pos_c], index=contracts.index)
    span_hi = pd.Series(cummax.values[hi_pos_c], index=contracts.index)

    band = config.MONEYNESS_BAND
    return valid & (contracts["strike"] >= span_lo * (1 - band)) \
                 & (contracts["strike"] <= span_hi * (1 + band))


def build_universe(und: pd.DataFrame) -> pd.DataFrame:
    contracts = pd.read_parquet(config.CONTRACTS_PARQUET)
    kept = []
    for sym, grp in contracts.groupby("underlying"):
        closes = und[und["underlying"] == sym].set_index("date")["close"].sort_index()
        if closes.empty:
            print(f"  {sym}: no underlying bars — skipped")
            continue
        keep = _universe_for(grp, closes)
        kept.append(grp[keep.fillna(False)])
        print(f"  {sym}: {int(keep.sum())} / {len(grp)} contracts in band")
    uni = pd.concat(kept, ignore_index=True)
    uni["life_start"] = (uni["expiration"] - pd.Timedelta(days=config.DTE_MAX + 15)).dt.strftime("%Y-%m-%d")
    uni["life_end"] = uni["expiration"].dt.strftime("%Y-%m-%d")
    uni.to_parquet(config.UNIVERSE_PARQUET, index=False)
    print(f"universe: {len(uni)} / {len(contracts)} contracts within ±{config.MONEYNESS_BAND:.0%} band")
    return uni


def bulk_download(uni: pd.DataFrame, key: str) -> None:
    done: set[str] = set()
    if config.DONE_MANIFEST.exists():
        done = set(config.DONE_MANIFEST.read_text().split())
    todo = uni[~uni["ticker"].isin(done)]
    print(f"bars: {len(done)} cached, {len(todo)} to download", flush=True)
    if todo.empty:
        return

    existing = sorted(config.BARS_DIR.glob("bars_part_*.parquet"))
    part_no = len(existing)
    buffer: list[dict] = []
    buffer_tickers: list[str] = []
    n_done = 0
    t0 = time.time()

    def fetch(row) -> tuple[str, list[dict]]:
        bars = _aggs(row.ticker, row.life_start, row.life_end, key)
        out = []
        for b in bars:
            out.append({"ticker": row.ticker,
                        "date": b["t"],
                        "open": b["o"], "high": b["h"], "low": b["l"],
                        "close": b["c"], "volume": b.get("v", 0),
                        "vwap": b.get("vw"), "transactions": b.get("n")})
        return row.ticker, out

    def flush():
        nonlocal part_no, buffer, buffer_tickers
        if buffer_tickers:
            if buffer:
                df = pd.DataFrame(buffer)
                df["date"] = pd.to_datetime(df["date"], unit="ms").dt.normalize()
                df.to_parquet(config.BARS_DIR / f"bars_part_{part_no:04d}.parquet", index=False)
                part_no += 1
            with open(config.DONE_MANIFEST, "a") as f:
                f.write("\n".join(buffer_tickers) + "\n")
        buffer, buffer_tickers = [], []

    with ThreadPoolExecutor(max_workers=config.DOWNLOAD_WORKERS) as ex:
        futures = [ex.submit(fetch, row) for row in todo.itertuples()]
        for fut in as_completed(futures):
            try:
                ticker, rows = fut.result()
            except Exception as e:                      # one bad contract shouldn't kill the run
                print(f"  ERROR {e}", flush=True)
                continue
            buffer.extend(rows)
            buffer_tickers.append(ticker)
            n_done += 1
            if len(buffer_tickers) >= FLUSH_EVERY:
                flush()
                rate = n_done / (time.time() - t0)
                eta_min = (len(todo) - n_done) / rate / 60 if rate else 0
                print(f"  {n_done}/{len(todo)} ({rate:.0f}/s, ETA {eta_min:.0f}m)", flush=True)
    flush()
    print(f"bars download complete: {n_done} contracts in {(time.time()-t0)/60:.1f}m", flush=True)


def coverage_report() -> None:
    parts = sorted(config.BARS_DIR.glob("bars_part_*.parquet"))
    if not parts:
        print("no bar files yet")
        return
    bars = pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)
    uni = pd.read_parquet(config.UNIVERSE_PARQUET)
    done = set(config.DONE_MANIFEST.read_text().split()) if config.DONE_MANIFEST.exists() else set()
    per_contract = bars.groupby("ticker").size()
    per_und = uni.groupby("underlying").size().sort_values(ascending=False)
    lines = [
        "universe by underlying:    " + ", ".join(f"{s}={n}" for s, n in per_und.items()),
        f"universe contracts:        {len(uni)}",
        f"downloaded (manifest):     {len(done)}",
        f"contracts with >=1 bar:    {bars['ticker'].nunique()}",
        f"contracts with zero bars:  {len(done) - bars['ticker'].nunique()}",
        f"total bar rows:            {len(bars)}",
        f"bars per contract:         median {per_contract.median():.0f}, "
        f"p10 {per_contract.quantile(.1):.0f}, p90 {per_contract.quantile(.9):.0f}",
        f"date range:                {bars['date'].min().date()} → {bars['date'].max().date()}",
        f"rows with volume >= {config.MIN_VOLUME}:   "
        f"{(bars['volume'] >= config.MIN_VOLUME).mean():.1%}",
    ]
    report = "\n".join(lines)
    config.REPORTS_DIR.mkdir(exist_ok=True)
    (config.REPORTS_DIR / "coverage_report.txt").write_text(report + "\n")
    print(report)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--universe-only", action="store_true", help="stop after the universe filter")
    args = ap.parse_args()

    load_dotenv(config.ROOT.parent / ".env")
    key = os.environ.get("MASSIVE_API_KEY", "")
    if not key:
        sys.exit("MASSIVE_API_KEY not set")
    config.ensure_dirs()

    und = download_underlyings(key)
    uni = build_universe(und)
    if args.smoke:
        uni = uni[(uni["expiration"] >= config.SMOKE_EXPIRY_MIN)
                  & (uni["expiration"] <= config.SMOKE_EXPIRY_MAX)]
        print(f"smoke mode: {len(uni)} contracts")
    if args.universe_only:
        return
    bulk_download(uni, key)
    coverage_report()


if __name__ == "__main__":
    main()
