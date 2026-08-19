"""Column-level diff of two meta_dataset builds, with correct row alignment.

WHY THIS EXISTS
    Comparing two builds is the gate on every rebuild, and doing it naively
    gives CONFIDENTLY WRONG answers. On 2026-08-19, sorting both frames by
    `contract` and walking them in parallel reported 845 differing `dte` values
    on AAPL. The real number was zero: the frames contain duplicate keys, so
    sorted-order walking pairs row i of one build with an unrelated row i of
    the other, and every such mis-pair reads as a difference.

    Worse, the obvious keys are the WRONG keys. `contract`, `strike` and
    `expiration` are exactly the columns a cache change moves, so keying on
    them mis-pairs precisely the rows you are trying to measure -- the
    comparison hides the thing it exists to find.

THE KEY
    Align on the SIGNAL, never on the chosen contract:

        symbol, strategy, entry_ts, direction, right, dte, trade_idx

    `dte` is the target bucket (1/5/10/30/45), not days-to-expiry, and was
    stable across the 2026-08-19 rebuild, so it is safe to key on. Dropping
    `dte` and `trade_idx` matches ZERO rows, because each (strategy, entry_ts)
    carries five DTE buckets and a bucket can hold several trades.

    Uniqueness is CHECKED, not assumed. A duplicated key aborts the run rather
    than silently mis-pairing -- the whole point of this module.

WHAT IT REPORTS
    Rows only in one side (a build legitimately gains entry-days the frozen
    spec later drops), then a per-column count of differences over the rows
    both sides share. `--expect-identical` turns any difference into exit 1,
    which is what a post-rebuild verification wants.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

# Align on the signal, never on the contract the signal selected.
KEY = ["symbol", "strategy", "entry_ts", "direction", "right", "dte",
       "trade_idx"]

# Float comparisons need a tolerance: parquet round-trips and differing pandas
# versions perturb the last bits without anything having actually changed.
ATOL = 1e-9


def _key(df: pd.DataFrame) -> pd.Series:
    missing = [c for c in KEY if c not in df.columns]
    if missing:
        raise KeyError("frame is missing key column(s): " + ", ".join(missing))
    return df[KEY].astype(str).agg("\x1f".join, axis=1)


def align(a: pd.DataFrame, b: pd.DataFrame):
    """Pair rows of `a` and `b` by KEY. Returns (A, B, only_a, only_b).

    Raises ValueError if either side has a duplicated key — mis-paired rows
    produce fabricated differences, so refusing is the only safe answer.
    """
    ka, kb = _key(a), _key(b)
    for name, k in (("baseline", ka), ("candidate", kb)):
        dup = int(k.duplicated().sum())
        if dup:
            raise ValueError(
                f"{name} has {dup} duplicated key(s) on {KEY} — refusing to "
                "align, because sorted-order pairing would invent differences")
    common = set(ka).intersection(set(kb))
    A = a[ka.isin(common)].assign(_k=ka[ka.isin(common)]).sort_values("_k")
    B = b[kb.isin(common)].assign(_k=kb[kb.isin(common)]).sort_values("_k")
    return (A.reset_index(drop=True), B.reset_index(drop=True),
            int((~ka.isin(common)).sum()), int((~kb.isin(common)).sum()))


def diff_columns(A: pd.DataFrame, B: pd.DataFrame) -> list[tuple[str, int]]:
    """Per-column count of differing values over aligned rows, worst first."""
    out = []
    for c in [c for c in A.columns if c in B.columns and c != "_k"]:
        x, y = A[c], B[c]
        if x.dtype.kind in "fc" or y.dtype.kind in "fc":
            n = int((((x - y).abs() > ATOL) | (x.isna() != y.isna())).sum())
        else:
            n = int((~((x == y) | (x.isna() & y.isna()))).sum())
        if n:
            out.append((c, n))
    out.sort(key=lambda t: -t[1])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--expect-identical", action="store_true",
                    help="exit 1 if any shared column differs")
    args = ap.parse_args()

    a = pd.read_parquet(Path(args.baseline))
    b = pd.read_parquet(Path(args.candidate))
    print(f"baseline : {len(a)} rows x {len(a.columns)} cols")
    print(f"candidate: {len(b)} rows x {len(b.columns)} cols")

    try:
        A, B, only_a, only_b = align(a, b)
    except (ValueError, KeyError) as e:
        print(f"FATAL: {e}", file=sys.stderr)
        return 2

    print(f"aligned  : {len(A)} rows "
          f"(baseline-only {only_a}, candidate-only {only_b})")
    for side, cols in (("candidate", [c for c in b.columns
                                      if c not in a.columns]),
                       ("baseline", [c for c in a.columns
                                     if c not in b.columns])):
        if cols:
            print(f"columns only in {side}: {', '.join(cols)}")

    rows = diff_columns(A, B)
    if not rows:
        print("IDENTICAL — every shared column matches on every aligned row")
        return 0
    print(f"{len(rows)} shared column(s) differ:")
    for c, n in rows:
        print(f"   {c:<18} {n:>8} rows  {100.0 * n / max(len(A), 1):>6.2f}%")
    return 1 if args.expect_identical else 0


if __name__ == "__main__":
    raise SystemExit(main())
