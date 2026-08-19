# scripts/spx0_stage0_audit.py — stage-0 data audit for the spx0 pool.
"""Answer the questions ROADMAP wave-2 #2 says gate the SPX/NDX seat.

    ./venv/bin/python scripts/spx0_stage0_audit.py [--sample 12]

The extraction itself is done (scripts/extract_index_1m.py). What was never
established is whether the archive is SOUND, and that is not a formality: on
2026-08-19 a v4 dataset was built from a cache missing 44 of 486 day-frames,
which silently dropped 16,500 trades and FLATTERED the backtest by removing
the losers. Nothing errored. The same failure mode is available here, so the
holes get found before anything is built on top.

Reports, in order of what would stop the seat:
  1. COVERAGE — day-files vs the trading days the proxy underlying knows about.
     A weekday with no file is a hole, not a holiday, because SPY's own 1m
     archive only contains real sessions.
  2. ROOTS — SPX/SPXW/NDX/NDXP presence per day. A root that vanishes
     mid-window changes what the pool can trade.
  3. 0DTE — same-day-expiry contract counts. The seat's whole premise is
     daily-expiry options; if 0DTE depth is thin the design changes.
  4. LIQUIDITY — volume distribution, because ROADMAP calls out cost modeling
     (index fees + spreads on small premiums) as the make-or-break here.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

CACHE = Path("nn_meta/data_cache_spx0")
DAYS = CACHE / "flatfiles_1m"
UNDER = CACHE / "underlying_1m"
ROOTS = ("SPXW", "SPX", "NDXP", "NDX")
# OCC: ROOT + YYMMDD + C/P + strike(8). Root is greedy-safe because we test
# the longer roots first (SPXW before SPX, NDXP before NDX).
_OCC = re.compile(r"^([A-Z]+)(\d{6})([CP])(\d{8})$")


def day_files() -> list[str]:
    return sorted(p.stem for p in DAYS.glob("*.parquet"))


def proxy_index(sym: str) -> pd.DatetimeIndex:
    """1m bar timestamps for a proxy underlying.

    The extractor wrote `timestamp` as the INDEX, not a column, so asking for
    columns=["timestamp"] raises KeyError. Handle both shapes.
    """
    df = pd.read_parquet(UNDER / f"{sym}.parquet")
    if isinstance(df.index, pd.DatetimeIndex):
        return df.index
    return pd.DatetimeIndex(df["timestamp"])


def proxy_sessions() -> set[str]:
    """Trading days according to SPY's own 1m archive — real sessions only."""
    return set(proxy_index("SPY").normalize().strftime("%Y-%m-%d").unique())


def root_of(occ: str) -> str | None:
    m = _OCC.match(occ)
    if not m:
        return None
    for r in ROOTS:
        if m.group(1) == r:
            return r
    return m.group(1)


def audit_day(day: str) -> dict:
    df = pd.read_parquet(DAYS / f"{day}.parquet", columns=["occ", "Volume"])
    roots = df["occ"].map(root_of)
    exp = df["occ"].str.extract(_OCC)[1]
    same_day = exp == pd.Timestamp(day).strftime("%y%m%d")
    return {
        "day": day,
        "rows": len(df),
        "contracts": df["occ"].nunique(),
        **{r: int((roots == r).sum()) for r in ROOTS},
        "zerodte_contracts": int(df.loc[same_day, "occ"].nunique()),
        "zerodte_rows": int(same_day.sum()),
        "vol_median": float(df["Volume"].median()),
        "vol_p90": float(df["Volume"].quantile(0.90)),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sample", type=int, default=12,
                    help="days to open for the per-day stats (0 = all)")
    args = ap.parse_args()

    days = day_files()
    print(f"== 1. COVERAGE ==\nday-files: {len(days)}  "
          f"span {days[0]} .. {days[-1]}")
    lo, hi = days[0], days[-1]
    # SPY cannot be the authority here — it is itself a candidate for being
    # short (see below). Use weekdays, and read the residual against the ~9-10
    # US market holidays per year that legitimately have no session.
    weekdays = {d.strftime("%Y-%m-%d")
                for d in pd.bdate_range(lo, hi)}
    missing = sorted(weekdays - set(days))
    want = weekdays
    yrs = (pd.Timestamp(hi) - pd.Timestamp(lo)).days / 365.25
    print(f"weekdays in span: {len(weekdays)}   day-files: {len(days)}   "
          f"weekdays with no file: {len(missing)}")
    print(f"  expected holidays over {yrs:.1f}y: ~{9.5 * yrs:.0f} — a residual "
          "near that is clean; a large excess is holes")
    if missing:
        for d in missing[:40]:
            print("   ", d)
        if len(missing) > 40:
            print(f"    ... and {len(missing) - 40} more")

    print("\n-- proxy underlying (the signal feed; index data is 403-gated) --")
    for sym in ("SPY", "QQQ"):
        if not (UNDER / f"{sym}.parquet").exists():
            print(f"  MISSING proxy underlying: {sym}")
            continue
        t = proxy_index(sym)
        sess = sorted(set(t.normalize().strftime("%Y-%m-%d")))
        # ~390 RTH minutes/session; the option window needs 2y of these.
        covered = [d for d in sess if lo <= d <= hi]
        print(f"  {sym}: {len(t)} bars over {len(sess)} sessions, "
              f"{t.min()} .. {t.max()}")
        print(f"      sessions inside the option window {lo}..{hi}: "
              f"{len(covered)} of {len(want)}")
        if len(covered) < len(want):
            print(f"      SHORT BY {len(want) - len(covered)} sessions — the "
                  "proxy cannot feed signals it has no bars for")

    picks = days if args.sample == 0 else days[:: max(1, len(days) // args.sample)]
    print(f"\n== 2-4. PER-DAY (sampling {len(picks)} of {len(days)}) ==")
    rows = [audit_day(d) for d in picks]
    rep = pd.DataFrame(rows).set_index("day")
    print(rep.to_string())

    print("\n== SUMMARY ==")
    for r in ROOTS:
        present = int((rep[r] > 0).sum())
        print(f"  {r:<5} present on {present}/{len(rep)} sampled days, "
              f"median {rep[r].median():.0f} rows/day")
    print(f"  0DTE contracts/day: median {rep['zerodte_contracts'].median():.0f}, "
          f"min {rep['zerodte_contracts'].min():.0f}")
    print(f"  volume: median {rep['vol_median'].median():.1f}, "
          f"p90 {rep['vol_p90'].median():.1f}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
