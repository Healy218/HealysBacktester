# nn_meta/download_universe.py
"""v2 options universe: contracts crawl + universe filter + daily bar download.

Owned by nn_meta (56 names, window 2024-07-14 → 2026-07-02); the completed
nn_options_signal experiment's cache is left untouched. Steps:

  1. Contract listings for every UNDERLYINGS name whose expiration falls in
     [EXPIRY_MIN, EXPIRY_MAX]  → data_cache/contracts.parquet
     (reuses nn_options_signal.download_contracts.crawl — fully parameterized)
  2. Underlying DAILY bars via the Alpaca loader (fast; avoids Massive's
     ~5/min stock tier and its 2-year entitlement) → underlying_daily.parquet
  3. Universe filter: strike within MONEYNESS_BAND of the underlying's close
     range during the contract's entry-eligible life → universe.parquet
  4. Threaded, resumable download of each universe contract's daily bar life
     → data_cache/bars_daily/bars_part_NNNN.parquet (+ bars_done.txt manifest)

IMPORTANT: Massive serves aggregates for a rolling 2-year window only — bars
older than (today - 2y) exist ONLY in this cache once downloaded. Run this
promptly after changing the window; reruns resume from the manifest.

Run:  python -m nn_meta.download_universe [--universe-only]
"""
import argparse
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from data import vbt_data_loader
from nn_options_signal.download_contracts import crawl
from nn_meta import config

FLUSH_EVERY = 500
_thread_local = threading.local()


def _session() -> requests.Session:
    if not hasattr(_thread_local, "s"):
        _thread_local.s = requests.Session()
    return _thread_local.s


def _get_with_retry(url: str, params: dict) -> dict:
    for attempt in range(config.MAX_RETRIES):
        try:
            r = _session().get(url, params=params, timeout=config.REQUEST_TIMEOUT)
        except requests.RequestException:
            time.sleep(2 ** attempt)
            continue
        if r.status_code == 429:
            time.sleep(15)
            continue
        if r.status_code >= 500:
            time.sleep(2 ** attempt)
            continue
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:160]}")
        return r.json()
    raise RuntimeError(f"exhausted retries for {url}")


def _aggs_daily(ticker: str, start: str, end: str, key: str) -> list[dict]:
    url = f"{config.MASSIVE_BASE_URL}/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}"
    body = _get_with_retry(url, {"adjusted": "true", "sort": "asc",
                                 "limit": 50000, "apiKey": key})
    return body.get("results", [])


# ── step 1: contracts ─────────────────────────────────────────────────────────

def _atomic_parquet(df: pd.DataFrame, path) -> None:
    """tmp + rename so a reader (the live scanner) never sees a torn file."""
    tmp = path.with_suffix(".tmp")
    df.to_parquet(tmp, index=False)
    tmp.replace(path)


def download_contracts(key: str, expiry_max: str | None = None) -> pd.DataFrame:
    expiry_max = expiry_max or config.EXPIRY_MAX
    rows: list[dict] = []
    t0 = time.time()
    for sym in config.UNDERLYINGS:
        n0 = len(rows)
        rows += crawl(True, key, config.EXPIRY_MIN, expiry_max, sym)
        rows += crawl(False, key, config.EXPIRY_MIN, expiry_max, sym)
        print(f"  {sym}: {len(rows) - n0} contracts", flush=True)
    df = pd.DataFrame(rows).drop_duplicates("ticker").reset_index(drop=True)
    df["expiration"] = pd.to_datetime(df["expiration"])
    _atomic_parquet(df, config.CONTRACTS_PARQUET)
    print(f"contracts: {len(df)} unique across {df['underlying'].nunique()} names "
          f"| {time.time() - t0:.0f}s → {config.CONTRACTS_PARQUET}")
    return df


# ── step 2: underlying daily bars (Alpaca) ────────────────────────────────────

def download_underlying_daily(end: str | None = None) -> pd.DataFrame:
    end = end or config.WINDOW_END
    frames = []
    for sym in config.UNDERLYINGS:
        raw = vbt_data_loader.load_price_data_smart(
            sym, config.HISTORY_START, end, "1D")
        if raw is None or raw.empty:
            print(f"  WARNING: no daily bars for {sym}", flush=True)
            continue
        df = raw.rename(columns={"Open": "open", "High": "high", "Low": "low",
                                 "Close": "close", "Volume": "volume"})
        df = df[["open", "high", "low", "close", "volume"]].copy()
        df["vwap"] = pd.NA          # unused by the surface builder
        df["transactions"] = pd.NA
        df["date"] = pd.DatetimeIndex(df.index).normalize()
        df["underlying"] = sym
        frames.append(df.reset_index(drop=True))
    und = pd.concat(frames, ignore_index=True)
    und = und[["underlying", "date", "open", "high", "low", "close",
               "volume", "vwap", "transactions"]]
    _atomic_parquet(und, config.UNDERLYING_DAILY_PARQUET)
    print(f"underlying daily: {len(und)} bars, "
          f"{und['underlying'].nunique()} names → {config.UNDERLYING_DAILY_PARQUET}")
    return und


# ── step 3: universe filter (same criteria as nn_options_signal) ─────────────

def _universe_for(contracts: pd.DataFrame, closes: pd.Series,
                  win_end: str | None = None) -> pd.Series:
    win_start = pd.Timestamp(config.WINDOW_START)
    win_end = pd.Timestamp(win_end or config.WINDOW_END)
    lo_d = (contracts["expiration"] - pd.Timedelta(days=config.DTE_MAX)).clip(lower=win_start)
    hi_d = (contracts["expiration"] - pd.Timedelta(days=config.DTE_MIN)).clip(upper=win_end)
    valid = lo_d <= hi_d

    idx = closes.index
    cummax = closes.cummax()
    suffix_min = closes[::-1].cummin()[::-1]
    n = len(idx)
    lo_pos = pd.Series(idx.searchsorted(lo_d.values, side="left")).clip(0, n - 1).values
    hi_pos = pd.Series(idx.searchsorted(hi_d.values, side="right") - 1).clip(0, n - 1).values
    span_lo = pd.Series(suffix_min.values[lo_pos], index=contracts.index)
    span_hi = pd.Series(cummax.values[hi_pos], index=contracts.index)

    band = config.MONEYNESS_BAND
    return valid & (contracts["strike"] >= span_lo * (1 - band)) \
                 & (contracts["strike"] <= span_hi * (1 + band))


def build_universe(contracts: pd.DataFrame, und: pd.DataFrame,
                   win_end: str | None = None) -> pd.DataFrame:
    kept = []
    for sym, grp in contracts.groupby("underlying"):
        closes = und[und["underlying"] == sym].set_index("date")["close"].sort_index()
        if closes.empty:
            print(f"  {sym}: no underlying bars — skipped")
            continue
        keep = _universe_for(grp, closes, win_end=win_end)
        kept.append(grp[keep.fillna(False)])
    uni = pd.concat(kept, ignore_index=True)
    uni["life_start"] = (uni["expiration"] - pd.Timedelta(days=config.DTE_MAX + 15)) \
        .dt.strftime("%Y-%m-%d")
    uni["life_end"] = uni["expiration"].dt.strftime("%Y-%m-%d")
    _atomic_parquet(uni, config.UNIVERSE_PARQUET)
    per = uni.groupby("underlying").size().sort_values(ascending=False)
    print(f"universe: {len(uni)} / {len(contracts)} contracts in ±"
          f"{config.MONEYNESS_BAND:.0%} band")
    print("  " + ", ".join(f"{s}={n}" for s, n in per.items()))
    return uni


# ── step 4: resumable bulk daily-bar download ─────────────────────────────────

def bulk_download(uni: pd.DataFrame, key: str) -> None:
    done: set[str] = set()
    if config.DONE_MANIFEST.exists():
        done = set(config.DONE_MANIFEST.read_text().split())
    todo = uni[~uni["ticker"].isin(done)]
    print(f"bars: {len(done)} cached, {len(todo)} to download "
          f"({config.DOWNLOAD_WORKERS} workers)", flush=True)
    if todo.empty:
        return

    part_no = len(sorted(config.BARS_DAILY_DIR.glob("bars_part_*.parquet")))
    buffer: list[dict] = []
    buffer_tickers: list[str] = []
    n_done = 0
    t0 = time.time()

    def fetch(row):
        bars = _aggs_daily(row.ticker, row.life_start, row.life_end, key)
        return row.ticker, [
            {"ticker": row.ticker, "date": b["t"],
             "open": b["o"], "high": b["h"], "low": b["l"], "close": b["c"],
             "volume": b.get("v", 0), "vwap": b.get("vw"),
             "transactions": b.get("n")} for b in bars]

    def flush():
        nonlocal part_no, buffer, buffer_tickers
        if buffer_tickers:
            if buffer:
                df = pd.DataFrame(buffer)
                df["date"] = pd.to_datetime(df["date"], unit="ms").dt.normalize()
                df.to_parquet(config.BARS_DAILY_DIR / f"bars_part_{part_no:04d}.parquet",
                              index=False)
                part_no += 1
            with open(config.DONE_MANIFEST, "a") as f:
                f.write("\n".join(buffer_tickers) + "\n")
        buffer, buffer_tickers = [], []

    with ThreadPoolExecutor(max_workers=config.DOWNLOAD_WORKERS) as ex:
        futures = [ex.submit(fetch, row) for row in todo.itertuples()]
        for fut in as_completed(futures):
            try:
                ticker, rows = fut.result()
            except Exception as e:
                print(f"  ERROR {e}", flush=True)
                continue
            buffer.extend(rows)
            buffer_tickers.append(ticker)
            n_done += 1
            if len(buffer_tickers) >= FLUSH_EVERY:
                flush()
                rate = n_done / (time.time() - t0)
                eta_h = (len(todo) - n_done) / rate / 3600 if rate else 0
                print(f"  {n_done}/{len(todo)} ({rate:.0f}/s, ETA {eta_h:.1f}h)",
                      flush=True)
    flush()
    print(f"bars download complete: {n_done} contracts in {(time.time()-t0)/3600:.1f}h",
          flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe-only", action="store_true")
    ap.add_argument("--live-horizon", type=int, default=None, metavar="DAYS",
                    help="LIVE-SCANNER REFRESH: crawl listings and build the "
                    "universe through today+DAYS instead of the frozen "
                    "research window (WINDOW_END stays untouched for research "
                    "reproducibility), and pull underlying daily bars through "
                    "today. The deployed chain otherwise dies when the frozen "
                    "window's horizon passes (it did: 2026-08-16). Weekly "
                    "cron this with --universe-only on the server.")
    args = ap.parse_args()
    key = os.environ.get("MASSIVE_API_KEY", "")
    if not key:
        sys.exit("MASSIVE_API_KEY not set")
    config.ensure_dirs()

    expiry_max = daily_end = win_end = None
    if args.live_horizon is not None:
        horizon = (pd.Timestamp.today().normalize()
                   + pd.Timedelta(days=args.live_horizon)).strftime("%Y-%m-%d")
        today = pd.Timestamp.today().normalize().strftime("%Y-%m-%d")
        expiry_max, daily_end, win_end = horizon, today, horizon
        print(f"live refresh: listings+universe through {horizon}, "
              f"underlying daily through {today}")

    contracts = download_contracts(key, expiry_max=expiry_max)
    und = download_underlying_daily(end=daily_end)
    uni = build_universe(contracts, und, win_end=win_end)
    if args.universe_only:
        return
    bulk_download(uni, key)


if __name__ == "__main__":
    main()
