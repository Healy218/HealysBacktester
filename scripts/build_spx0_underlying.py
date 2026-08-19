# scripts/build_spx0_underlying.py — proxy underlying feed for the spx0 pool.
"""Build data_cache_spx0/underlying_1m/{SPY,QQQ}.parquet from the 9y 1m crawl.

WHY A PROXY AT ALL
    SPX/NDX *index* data is 403-gated on our entitlement (stage-0 decision
    2026-08-17), so the seat trades index options but takes its SIGNALS from
    the SPY/QQQ proxies, with strikes ratio-mapped. That decision stands; the
    data behind it was never actually fetched.

WHY THIS SCRIPT
    The 2026-08-19 stage-0 audit found `underlying_1m/` holding SPY and QQQ at
    exactly **10,000 bars each** — 12 sessions ending 2024-08-16, covering 1 of
    the 521 sessions the option archive spans. A round 10,000 is an unraised
    API page limit, not a feed. Meanwhile `v3/data/underlying/{SPY,QQQ}/`
    already holds 2017→now at 1m in the same schema, so the fix is to slice the
    crawl we own rather than re-pull two years.

CONVENTIONS
    - RTH only, via the pipeline's DST-correct `filter_rth`, matching
      `v3/build_underlying.py`. Pre/post index options are untradeable anyway:
      the audit measured a median of 3 contracts of volume per 1m bar.
    - `timestamp` stays the INDEX, matching both the crawl and the stub it
      replaces.
    - The window is read from the option archive's own day-files, so it is
      self-describing and cannot drift from what the seat can actually trade.

FAIL CLOSED
    If the crawl cannot cover the option window, this exits non-zero and says
    how short it is, rather than writing a feed with holes in it. Refresh the
    crawl first: `python -m v3.underlying --symbols SPY,QQQ --start-year 2026`.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from nn_meta.download_data import filter_rth   # noqa: E402
from v3 import underlying                      # noqa: E402

CACHE = Path("nn_meta/data_cache_spx0")
DAYS = CACHE / "flatfiles_1m"
OUT = CACHE / "underlying_1m"
SYMBOLS = ("SPY", "QQQ")


def option_window() -> tuple[str, str]:
    """First and last day the option archive actually covers."""
    days = sorted(p.stem for p in DAYS.glob("*.parquet"))
    if not days:
        raise FileNotFoundError(f"no option day-files under {DAYS}")
    return days[0], days[-1]


def build(sym: str, lo: str, hi: str) -> tuple[pd.DataFrame, int, int]:
    bars = filter_rth(underlying.load_1m(sym))
    win = bars.loc[(bars.index >= lo) & (bars.index <= f"{hi} 23:59:59")]
    sessions = win.index.normalize().nunique()
    return win, len(win), sessions


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--min-coverage", type=float, default=0.99,
                    help="fraction of option sessions the proxy must cover")
    args = ap.parse_args()

    lo, hi = option_window()
    want = len(sorted(p.stem for p in DAYS.glob("*.parquet")))
    print(f"option window {lo} .. {hi}  ({want} option day-files)")
    OUT.mkdir(parents=True, exist_ok=True)

    short = []
    for sym in SYMBOLS:
        win, rows, sessions = build(sym, lo, hi)
        cover = sessions / want if want else 0.0
        print(f"  {sym}: {rows:,} RTH bars over {sessions} sessions "
              f"({100 * cover:.1f}% of option days), "
              f"{win.index.min()} .. {win.index.max()}")
        if cover < args.min_coverage:
            short.append((sym, sessions, want))
            continue
        tmp = OUT / f".{sym}.parquet.tmp"
        win.to_parquet(tmp)
        tmp.replace(OUT / f"{sym}.parquet")     # atomic; never a half file
        print(f"     wrote {OUT / (sym + '.parquet')}")

    if short:
        print("\nFATAL: proxy feed does not cover the option window.",
              file=sys.stderr)
        for sym, have, need in short:
            print(f"  {sym}: {have} of {need} sessions", file=sys.stderr)
        print("Refresh the crawl, then re-run:\n"
              "  python -m v3.underlying --symbols SPY,QQQ --start-year 2026",
              file=sys.stderr)
        return 1
    print("\nOK — both proxies cover the option window")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
