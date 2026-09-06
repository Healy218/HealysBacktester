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
import re
import shutil
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
from nn_meta.config import TICKER_ALIASES

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
        # the reference API wants exchange symbology (BRK.B), but the OCC
        # tickers it returns carry the root form (O:BRKB…) — rekey rows to
        # sym so everything downstream joins on the OCC-root form
        fetch_sym = config.FETCH_ALIASES.get(sym, sym)
        new = crawl(True, key, config.EXPIRY_MIN, expiry_max, fetch_sym) \
            + crawl(False, key, config.EXPIRY_MIN, expiry_max, fetch_sym)
        if fetch_sym != sym:
            for r in new:
                r["underlying"] = sym
        rows += new
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
        # Renamed listings (SQ→XYZ) FETCH under the current exchange ticker —
        # the old symbol returns nothing and would silently kill the name's
        # beta/moneyness context — while rows keep underlying=sym, the symbol
        # the spec/universe/models are keyed on. Options-CONTRACT aliasing is
        # deliberately out of scope: chain continuity across a rename is
        # messy, and the v31 legacy scorer simply filters SQ (accepted).
        fetch_sym = config.FETCH_ALIASES.get(sym) or TICKER_ALIASES.get(sym, sym)
        raw = vbt_data_loader.load_price_data_smart(
            fetch_sym, config.HISTORY_START, end, "1D")
        if raw is None or raw.empty:
            print(f"  WARNING: no daily bars for {sym}"
                  + (f" (fetched as {fetch_sym})" if fetch_sym != sym else ""),
                  flush=True)
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


def _guard_universe_shrink(new_uni: pd.DataFrame, *, floor: float = 0.5) -> None:
    """Refuse to replace a healthy universe with a drastically smaller one.

    The weekly refresh atomically overwrites the file the live scanners select
    contracts from; a pathological crawl (partial listings, provider hiccup
    that still exited 0) must not shrink the tradable chain silently. Exits
    non-zero so the cron chain stops and the old universe stays in place."""
    if not config.UNIVERSE_PARQUET.exists():
        return
    try:
        old_n = len(pd.read_parquet(config.UNIVERSE_PARQUET, columns=["ticker"]))
    except Exception:
        return                                     # old file unreadable — replace
    if old_n > 0 and len(new_uni) < old_n * floor:
        raise SystemExit(
            f"universe shrink guard: new universe has {len(new_uni)} contracts "
            f"vs {old_n} existing (< {floor:.0%}) — refusing to replace. "
            f"Inspect the crawl log; the previous universe remains in place.")


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
    _guard_universe_shrink(uni)
    _atomic_parquet(uni, config.UNIVERSE_PARQUET)
    per = uni.groupby("underlying").size().sort_values(ascending=False)
    print(f"universe: {len(uni)} / {len(contracts)} contracts in ±"
          f"{config.MONEYNESS_BAND:.0%} band")
    print("  " + ", ".join(f"{s}={n}" for s, n in per.items()))
    return uni


# ── step 4: resumable bulk daily-bar download ─────────────────────────────────

def bootstrap_manifest_from_parts() -> int:
    """Synthesize a done-manifest from the tickers already present in the
    bars_daily parts. The v31 cache was built by the flat-files pipeline and
    carries no manifest — without this, an incremental refresh would try to
    re-download the entire universe."""
    if config.DONE_MANIFEST.exists():
        return 0
    parts = sorted(config.BARS_DAILY_DIR.glob("bars_part_*.parquet"))
    if not parts:
        return 0
    tickers: set[str] = set()
    for p in parts:
        tickers |= set(pd.read_parquet(p, columns=["ticker"])["ticker"].unique())
    tmp = config.DONE_MANIFEST.with_suffix(".tmp")
    tmp.write_text("\n".join(sorted(tickers)) + "\n")
    tmp.replace(config.DONE_MANIFEST)
    print(f"manifest bootstrapped from parts: {len(tickers)} tickers")
    return len(tickers)


def prune_manifest_for_refresh(uni: pd.DataFrame, days: int) -> int:
    """Drop from the done-manifest every universe contract whose bar life may
    still be growing (life_end within ``days`` of today, or in the future), so
    ``bulk_download`` refetches it life-to-date. Duplicate (ticker, date) rows
    across old and new parts are deduped by ``build_surface.load_daily_bars``.
    """
    if not config.DONE_MANIFEST.exists():
        return 0
    cutoff = (pd.Timestamp.today().normalize()
              - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
    recent = set(uni.loc[uni["life_end"] >= cutoff, "ticker"])
    done = [t for t in config.DONE_MANIFEST.read_text().split() if t]
    keep = [t for t in done if t not in recent]
    tmp = config.DONE_MANIFEST.with_suffix(".tmp")
    tmp.write_text("\n".join(keep) + ("\n" if keep else ""))
    tmp.replace(config.DONE_MANIFEST)
    pruned = len(done) - len(keep)
    print(f"manifest: pruned {pruned} recent-life contracts (life_end >= {cutoff})")
    return pruned


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


_PART_NO_RE = re.compile(r"bars_part_(\d+)\.parquet$")


def _part_number(path) -> int:
    m = _PART_NO_RE.search(path.name)
    return int(m.group(1)) if m else -1


def compact_bars_daily() -> None:
    """Deduplicate daily observations, preserving disjoint contract history.

    Walk parts newest-first by numeric index and keep the newest value for
    each (ticker, date). Original flat-file parts partition days, so a ticker
    can legitimately span several parts; ticker-level replacement loses data.
    Only one part and the set of seen observation keys remain in memory.

    "Newest" is the highest NUMERIC part index, not reverse-lexical filename
    order: the v31 cache mixes the flat-file pipeline's unpadded parts
    (``bars_part_0`` … ``bars_part_12``, ``v3/derive_contracts.py``) with the
    zero-padded parts this module's refresh appends (``bars_part_0013`` …),
    and lexically ``bars_part_9`` > ``bars_part_0013``. Numeric order is
    chronological across both pipelines (the refresh starts numbering at
    ``len(existing parts)``). Output parts are renumbered ``0000`` ascending
    in processing order — read order is irrelevant afterwards because no
    (ticker, date) observation spans two parts.

    Crash-safe swap: survivors are written into a sibling
    ``bars_daily.compacting/`` dir, then ``bars_daily`` → ``bars_daily.old``,
    ``bars_daily.compacting`` → ``bars_daily``, and ``bars_daily.old`` is
    deleted. RECOVERY RULE: if ``bars_daily`` is missing and
    ``bars_daily.old`` exists, restore ``.old`` back to ``bars_daily`` (a
    leftover ``.compacting`` dir is partial output — delete it). This
    function performs that recovery itself on entry, so rerunning after a
    crash is always safe. ``config.DONE_MANIFEST`` is untouched: the ticker
    SET is unchanged, only redundant rows are dropped.
    """
    bars_dir = config.BARS_DAILY_DIR
    old_dir = bars_dir.with_name(bars_dir.name + ".old")
    tmp_dir = bars_dir.with_name(bars_dir.name + ".compacting")

    # Recovery is CONTENT-based, not existence-based (P0 fix, 2026-08-16
    # pre-merge review): main() runs config.ensure_dirs() before dispatching
    # here, which recreates an EMPTY bars_daily after a mid-swap crash — an
    # existence check would classify that as "crashed after the swap" and
    # delete .old, the only full copy (partly unrecoverable: bars older than
    # the rolling 2y entitlement exist only in this cache).
    def _has_parts(d):
        return d.exists() and any(d.glob("bars_part_*.parquet"))

    if _has_parts(old_dir) and not _has_parts(bars_dir):
        # crashed between the swap renames — .old holds the only real data
        print(f"compact: recovering {bars_dir.name} from {old_dir.name}")
        if bars_dir.exists():
            shutil.rmtree(bars_dir)                    # empty ensure_dirs shell
        old_dir.rename(bars_dir)
    elif old_dir.exists():
        # bars_daily has real parts (or .old has none) — the swap completed
        shutil.rmtree(old_dir)
    if tmp_dir.exists():                               # stale partial output
        shutil.rmtree(tmp_dir)

    parts = (sorted(bars_dir.glob("bars_part_*.parquet"),
                    key=_part_number, reverse=True)
             if bars_dir.exists() else [])
    if not parts:
        print("compact: no bar parts — nothing to do")
        return

    bytes_before = sum(p.stat().st_size for p in parts)
    seen: set[tuple] = set()
    rows_before = rows_after = out_no = 0
    tmp_dir.mkdir()
    for p in parts:
        df = pd.read_parquet(p)
        rows_before += len(df)
        if df.empty:
            continue
        # Flat-file parts partition DAYS, not full contract lifetimes. Only
        # repeated ticker/date observations are redundant across those parts.
        df = df.drop_duplicates(["ticker", "date"], keep="last")
        keys = list(zip(df["ticker"], pd.to_datetime(df["date"])))
        keep = df[[key not in seen for key in keys]]
        seen.update(keys)
        if keep.empty:
            continue
        keep.to_parquet(tmp_dir / f"bars_part_{out_no:04d}.parquet", index=False)
        out_no += 1
        rows_after += len(keep)

    bytes_after = sum(q.stat().st_size
                      for q in tmp_dir.glob("bars_part_*.parquet"))
    bars_dir.rename(old_dir)
    tmp_dir.rename(bars_dir)
    shutil.rmtree(old_dir)
    print(f"compact: {len(parts)} parts / {rows_before} rows / "
          f"{bytes_before / 1e6:.1f} MB → {out_no} parts / {rows_after} rows / "
          f"{bytes_after / 1e6:.1f} MB ({len(seen)} ticker/date observations)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe-only", action="store_true")
    ap.add_argument("--bars-and-surface-only", action="store_true",
                    help="skip the listings/universe rebuild; incrementally "
                    "refresh the daily option-bar cache against the EXISTING "
                    "universe parquet (chain `python -m nn_meta.build_surface` "
                    "after this to rebuild surface_daily)")
    ap.add_argument("--refresh-recent-days", type=int, default=None,
                    metavar="DAYS", help="re-download bars for contracts "
                    "whose life_end is within DAYS of today (their bars grew "
                    "since the last fetch); weekly cron uses ~10, a backfill "
                    "after a gap uses the gap length")
    ap.add_argument("--compact", action="store_true",
                    help="rewrite bars_daily so each ticker's rows live only "
                    "in its newest part, reclaiming the space the weekly "
                    "refresh leaks; runs automatically at the end of "
                    "--bars-and-surface-only, standalone here (offline — no "
                    "API key needed)")
    ap.add_argument("--live-horizon", type=int, default=None, metavar="DAYS",
                    help="LIVE-SCANNER REFRESH: crawl listings and build the "
                    "universe through today+DAYS instead of the frozen "
                    "research window (WINDOW_END stays untouched for research "
                    "reproducibility), and pull underlying daily bars through "
                    "today. The deployed chain otherwise dies when the frozen "
                    "window's horizon passes (it did: 2026-08-16). Weekly "
                    "cron this with --universe-only on the server.")
    args = ap.parse_args()
    config.ensure_dirs()
    if args.compact and not args.bars_and_surface_only:
        compact_bars_daily()                 # offline maintenance — no key
        return
    key = os.environ.get("MASSIVE_API_KEY", "")
    if not key:
        sys.exit("MASSIVE_API_KEY not set")

    if args.bars_and_surface_only:
        uni = pd.read_parquet(config.UNIVERSE_PARQUET)
        bootstrap_manifest_from_parts()
        if args.refresh_recent_days:
            prune_manifest_for_refresh(uni, args.refresh_recent_days)
        bulk_download(uni, key)
        compact_bars_daily()                 # weekly cron self-compacts
        return

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
