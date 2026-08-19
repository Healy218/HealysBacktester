"""Fail-closed coverage check for the flat-file option-bar archive.

WHY THIS EXISTS
    On 2026-08-19 the v4 ledger re-run produced a dataset that differed from
    the stage-0 one on 13 columns and 3.4% of trades, with no error anywhere.
    Cause: 44 of the 486 flat-file day-frames had never reached the GCS bucket,
    and `FlatFilesProvider._day` returns None for a missing day-frame instead
    of raising:

        p = self._ff_dir / f"{day}.parquet"
        return pd.read_parquet(p) if p.exists() else None

    A trade whose window spans a missing day is then silently unpriced --
    `executed` goes False and the row drops out of the book. That is not
    neutral: the dropped trades had mean net_return +0.017 against +0.114 for
    the ones that survived, so an incomplete cache FLATTERS the backtest. Two
    weeks of results had to be discarded.

    The silent-skip itself is deliberate and stays -- market holidays are
    weekdays with no flat file, and the provider cannot tell a holiday from a
    hole. The fix is to check coverage ONCE, up front, against a source that
    knows which days actually traded.

WHAT IT CHECKS
    Every day on which the underlying archive has 15-minute bars must have a
    flat-file day-frame. `underlying_15m.parquet` is the right authority: it is
    the same archive, built from the same vendor pull, and it contains only
    real trading days -- so a day present there and absent here is a hole, not
    a holiday.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from nn_meta import config


def flatfile_days(cache: Path) -> set[str]:
    d = cache / "flatfiles_15m"
    return {p.stem for p in d.glob("*.parquet")} if d.is_dir() else set()


def trading_days(cache: Path) -> set[str]:
    """Trading days according to the underlying 15m archive."""
    ts = pd.read_parquet(cache / "underlying_15m.parquet", columns=["timestamp"])
    return set(pd.DatetimeIndex(ts["timestamp"]).normalize()
               .strftime("%Y-%m-%d").unique())


def check(cache: Path, start: str | None = None,
          end: str | None = None) -> tuple[bool, list[str], dict]:
    """Compare day-frames to trading days over the archive's own window.

    The underlying archive reaches back to 2017 while the flat-file archive is
    a ~2-year slice, so the comparison is scoped. With no explicit bounds the
    window is the span of the day-frames that ARE present, which is
    self-describing and needs no extra config.

    Known limit of that default: a hole at the very first or very last day
    moves the bound and hides itself. Interior holes -- the 44-day gap this
    module exists for, and every realistic partial-upload -- are all caught.
    Pass --start/--end to pin the window when the exact span is known.
    """
    have, want = flatfile_days(cache), trading_days(cache)
    if not have:
        return False, [], {"cache": str(cache), "trading_days": len(want),
                           "flatfile_days": 0, "missing": -1, "extra": 0,
                           "window": "none — no day-frames at all"}
    lo = start or min(have)
    hi = end or max(have)
    want = {d for d in want if lo <= d <= hi}
    missing = sorted(want - have)
    return not missing, missing, {
        "cache": str(cache),
        "window": f"{lo} .. {hi}",
        "trading_days": len(want),
        "flatfile_days": len(have),
        "missing": len(missing),
        # Extra day-frames are harmless (a day the underlying archive does not
        # cover cannot produce a trade), so they are reported, never fatal.
        "extra": len(have - want),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", default=str(config.DATA_CACHE))
    ap.add_argument("--start", default=None, help="pin the window start (YYYY-MM-DD)")
    ap.add_argument("--end", default=None, help="pin the window end (YYYY-MM-DD)")
    args = ap.parse_args()

    ok, missing, stats = check(Path(args.cache), args.start, args.end)
    print(f"flat-file coverage over {stats['window']}: "
          f"{stats['flatfile_days']} day-frames vs "
          f"{stats['trading_days']} trading days "
          f"({stats['missing']} missing, {stats['extra']} extra)")
    if ok:
        print("OK — every trading day has a day-frame")
        return 0
    print(f"FATAL: {len(missing)} trading day(s) have no flat-file day-frame.",
          file=sys.stderr)
    print("Trades spanning these days are silently dropped from the book, and",
          file=sys.stderr)
    print("the drop is biased — see this module's docstring.", file=sys.stderr)
    for day in missing[:60]:
        print(f"  missing {day}", file=sys.stderr)
    if len(missing) > 60:
        print(f"  ... and {len(missing) - 60} more", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
