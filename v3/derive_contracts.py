# v3/derive_contracts.py — universe listing + daily option bars from day-frames.
"""One scan over the flat-file 15m day-frames produces the two remaining
inputs the pipeline needs, entirely offline (no REST):

1. universe.parquet — every contract seen, with life_start (first date it
   traded) and OCC-parsed underlying/expiration/strike/type. Used by the
   provider for chain selection, so it must be COMPLETE (all strikes), not
   filtered.
2. bars_daily/bars_part_*.parquet — per-contract daily OHLCV (15m aggregated),
   filtered to tradeable premium/DTE. Feeds build_surface (ATM IV, pc_ratio).

Run:  python -m v3.derive_contracts --cache nn_meta/data_cache_v3
"""
import argparse
import re
from pathlib import Path

import pandas as pd

from nn_meta import config as nn_config

_OCC = re.compile(r"^([A-Z]+)(\d{6})([CP])(\d{8})$")
_CHUNK = 40                                    # day-frames per bars_part file
_1D = {"Open": "first", "High": "max", "Low": "min", "Close": "last",
       "Volume": "sum"}


def parse_occ(occ: str):
    m = _OCC.match(occ)
    if not m:
        return None
    root, ymd, cp, strike = m.groups()
    exp = pd.Timestamp(f"20{ymd[:2]}-{ymd[2:4]}-{ymd[4:6]}")
    return root, exp, ("call" if cp == "C" else "put"), int(strike) / 1000.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default="nn_meta/data_cache_v3")
    ap.add_argument("--min-premium", type=float, default=0.05)
    ap.add_argument("--max-dte", type=int, default=70)
    ap.add_argument("--moneyness-band", type=float, default=0.15,
                    help="|log(strike/spot)| kept in the daily bars (surface "
                         "input); the universe listing stays complete")
    args = ap.parse_args()
    cache = Path(args.cache)
    ff_dir = cache / "flatfiles_15m"
    bars_dir = cache / "bars_daily"
    bars_dir.mkdir(parents=True, exist_ok=True)

    # spot per (underlying, date) — to keep only near-ATM daily bars (surface
    # only needs IV/pc near the money; this bounds build_surface's memory)
    und = pd.read_parquet(cache / "underlying_daily.parquet",
                          columns=["underlying", "date", "close"])
    spot = {(r.underlying, r.date): r.close for r in und.itertuples()}

    frames = sorted(ff_dir.glob("*.parquet"))
    print(f"scanning {len(frames)} day-frames…", flush=True)

    first_seen: dict[str, pd.Timestamp] = {}   # occ -> life_start
    daily_buf, part = [], 0
    import numpy as np
    for i, fp in enumerate(frames, 1):
        day = pd.Timestamp(fp.stem)
        df = pd.read_parquet(fp)
        # daily bar per contract (aggregate the day's 15m)
        d = df.groupby("occ").agg(_1D)
        d["date"] = day
        d = d.reset_index()
        # track life_start for the COMPLETE universe (all contracts)
        for occ in d["occ"].values:
            if occ not in first_seen:
                first_seen[occ] = day
        # daily bars = near-ATM, tradeable premium/dte (surface input only)
        parsed = d["occ"].map(parse_occ)
        ok = parsed.notna()
        d = d[ok].copy()
        parsed = parsed[ok]
        d["underlying"] = parsed.map(lambda p: p[0])
        exp = parsed.map(lambda p: p[1])
        d["strike"] = parsed.map(lambda p: p[3])
        dte = (exp - day).dt.days
        sp = pd.to_numeric(d["underlying"].map(lambda u: spot.get((u, day))),
                           errors="coerce")
        mny = np.log(d["strike"].astype(float) / sp)
        keep = (d["Close"] >= args.min_premium) & dte.between(1, args.max_dte) \
            & sp.notna() & (mny.abs() <= args.moneyness_band)
        d = d[keep].copy()
        d["ticker"] = "O:" + d["occ"]
        daily_buf.append(d.rename(columns=str.lower)[
            ["ticker", "date", "open", "high", "low", "close", "volume"]])
        if i % _CHUNK == 0 or i == len(frames):
            pd.concat(daily_buf, ignore_index=True).to_parquet(
                bars_dir / f"bars_part_{part}.parquet", index=False)
            daily_buf, part = [], part + 1
            print(f"  [{i}/{len(frames)}] {day.date()} · "
                  f"{len(first_seen):,} contracts seen", flush=True)

    # universe listing (COMPLETE — every contract, for chain selection)
    rows = []
    for occ, life in first_seen.items():
        p = parse_occ(occ)
        if p:
            root, exp, typ, strike = p
            rows.append({"ticker": "O:" + occ, "underlying": root,
                         "expiration": exp, "life_start": life,
                         "strike": strike, "type": typ})
    uni = pd.DataFrame(rows)
    uni.to_parquet(cache / "universe.parquet", index=False)
    uni.to_parquet(cache / "contracts.parquet", index=False)
    print(f"\nuniverse: {len(uni):,} contracts, "
          f"{uni['underlying'].nunique()} underlyings → {cache}/universe.parquet")
    print(f"daily bars: {part} part files → {bars_dir}")


if __name__ == "__main__":
    main()
