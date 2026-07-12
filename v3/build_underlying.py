# v3/build_underlying.py — 120-universe underlying parquets for the big run.
"""Resample the 1m crawl (v3/data/underlying) into the two long-format
parquets HybridCachedProvider reads, matching the existing schema exactly:

  underlying_15m.parquet : symbol, timestamp, Open/High/Low/Close/Volume
  underlying_daily.parquet: underlying, date, open/high/low/close/volume,
                            vwap, transactions

RTH is filtered with the pipeline's own DST-correct filter_rth (via
America/New_York), applied to the 1m bars before resampling, so a Jan 09:30
(14:30 UTC) and a Jun 09:30 (13:30 UTC) both survive. Written under
nn_meta/data_cache_v3/.

Run:  python -m v3.build_underlying
"""
import json
from pathlib import Path

import pandas as pd

from nn_meta.download_data import filter_rth
from v3 import config, underlying

OUT_DIR = Path("nn_meta/data_cache_v3")
_15M = {"Open": "first", "High": "max", "Low": "min", "Close": "last",
        "Volume": "sum"}
_1D = {"open": "first", "high": "max", "low": "min", "close": "last",
       "volume": "sum"}


def main() -> None:
    universe = json.loads((config.ARTIFACTS / "universe_120.json").read_text())
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    m15, daily = [], []
    for i, sym in enumerate(universe, 1):
        try:
            bars = filter_rth(underlying.load_1m(sym))
        except Exception as e:
            print(f"  {sym}: skip ({str(e)[:60]})", flush=True)
            continue
        if bars.empty:
            continue
        # 15m (RTH)
        b15 = bars.resample("15min", label="left", closed="left").agg(_15M) \
                  .dropna(subset=["Close"]).reset_index()
        b15.insert(0, "symbol", sym)
        m15.append(b15)
        # daily (RTH session)
        low = bars.rename(columns=str.lower)
        d = low.resample("1D").agg(_1D).dropna(subset=["close"]).reset_index()
        d = d.rename(columns={"timestamp": "date"})
        d.insert(0, "underlying", sym)
        d["vwap"] = None
        d["transactions"] = None
        daily.append(d)
        if i % 20 == 0:
            print(f"  [{i}/{len(universe)}] {sym}", flush=True)

    m15_df = pd.concat(m15, ignore_index=True)
    daily_df = pd.concat(daily, ignore_index=True)[
        ["underlying", "date", "open", "high", "low", "close", "volume",
         "vwap", "transactions"]]
    m15_df.to_parquet(OUT_DIR / "underlying_15m.parquet", index=False)
    daily_df.to_parquet(OUT_DIR / "underlying_daily.parquet", index=False)
    print(f"\nunderlying_15m : {len(m15_df):,} rows, "
          f"{m15_df['symbol'].nunique()} symbols → {OUT_DIR}")
    print(f"underlying_daily: {len(daily_df):,} rows, "
          f"{daily_df['underlying'].nunique()} symbols")
    print(f"15m span: {m15_df['timestamp'].min()} → {m15_df['timestamp'].max()}")


if __name__ == "__main__":
    main()
