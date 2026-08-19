# v3/underlying.py — Stage 2: 1m crawl → partitioned parquet (+ resampling).
"""Download config.BASE_INTERVAL (1m) ONLY; every higher timeframe derives
via resample() (one quota spend, zero cross-feed misalignment — V3_SPEC).

Layout: UNDERLYING_DIR/<symbol>/<year>.parquet. Checkpointed per
symbol-year: completed past years are skipped on rerun; the current year is
always refreshed. Alpaca's SDK auto-paginates and rate-limits fine at this
pace (~200 req/min account cap shared with the live scanner's tiny usage).

Run (repo root):  python -m v3.underlying [--symbols A,B | --universe]
                                          [--start-year 2017]
"""
import argparse
import time
from datetime import date

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import pandas as pd

from data.alpaca_loader import load_alpaca_bars
from v3 import config
from v3.universe import BOOTSTRAP_UNIVERSE

_AGG = {"Open": "first", "High": "max", "Low": "min",
        "Close": "last", "Volume": "sum"}


def crawl_symbol(symbol: str, start_year: int = 2017) -> int:
    """Fetch/refresh per-year 1m partitions for `symbol`; returns new rows."""
    out_dir = config.UNDERLYING_DIR / symbol
    out_dir.mkdir(parents=True, exist_ok=True)
    this_year = date.today().year
    added = 0
    for year in range(start_year, this_year + 1):
        path = out_dir / f"{year}.parquet"
        if path.exists() and year < this_year:
            continue                            # completed past year
        # END IS EXCLUSIVE at 00:00, so a bare "YYYY-12-31" silently drops
        # 31 Dec's whole session — every completed year in the 9y crawl was
        # short its last trading day (found 2026-08-19 via the spx0 proxy,
        # which came up 498/500 sessions on exactly 2024-12-31 and
        # 2025-12-31). Ask for the following midnight instead.
        # The CURRENT year deliberately still ends at today-00:00: asking for
        # tomorrow trips Alpaca's "subscription does not permit querying
        # recent SIP data" (seen 2026-08-19), which fails the whole year. The
        # current year is refreshed on every run anyway, so yesterday's close
        # is the most this tier can hold.
        end = (f"{year + 1}-01-01" if year < this_year
               else date.today().isoformat())
        try:
            df = load_alpaca_bars(symbol, f"{year}-01-01", end, "1m")
        except Exception as e:                   # listed later / no data yet
            print(f"  {symbol} {year}: no data ({str(e)[:80]})", flush=True)
            continue
        # The exclusive-end request above reaches the following midnight, which
        # can return a single bar stamped 00:00 on Jan 1 — that would land in
        # BOTH this partition and the next one, and load_1m concatenates
        # without deduping. Clip to the year that owns the file.
        df = df[df.index.year == year]
        df.to_parquet(path)
        added += len(df)
        print(f"  {symbol} {year}: {len(df):,} bars", flush=True)
        time.sleep(0.3)                          # stay polite on the API
    return added


def load_1m(symbol: str) -> pd.DataFrame:
    parts = sorted((config.UNDERLYING_DIR / symbol).glob("*.parquet"))
    if not parts:
        raise FileNotFoundError(f"no 1m partitions for {symbol} — crawl first")
    return pd.concat([pd.read_parquet(p) for p in parts]).sort_index()


def resample(symbol: str, interval: str) -> pd.DataFrame:
    """Derive any RESAMPLE_STACK interval from the stored 1m partitions."""
    if interval not in config.RESAMPLE_STACK:
        raise ValueError(f"{interval} not in {config.RESAMPLE_STACK}")
    bars = load_1m(symbol)
    out = bars.resample(interval, label="left", closed="left").agg(_AGG)
    return out.dropna(subset=["Close"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=None,
                    help="comma list; default = full bootstrap universe")
    ap.add_argument("--start-year", type=int, default=2017)
    args = ap.parse_args()
    symbols = ([s.strip().upper() for s in args.symbols.split(",")]
               if args.symbols else BOOTSTRAP_UNIVERSE)

    print(f"crawling 1m {args.start_year}→now for {len(symbols)} symbols",
          flush=True)
    total = 0
    for i, symbol in enumerate(symbols, 1):
        total += crawl_symbol(symbol, args.start_year)
        if i % 10 == 0:
            print(f"[{i}/{len(symbols)}] running total {total:,} bars",
                  flush=True)
    print(f"DONE: {total:,} new 1m bars across {len(symbols)} symbols",
          flush=True)


if __name__ == "__main__":
    main()
