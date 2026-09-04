"""How stable is the finalize gate's baseline bar? (2026-09-04)

The v4 gate's beat-baseline term compares a candidate's validation return
against the frozen take-everything book's ex-top3 return, both through the
mark-to-market ledger. That book is a SLOT PORTFOLIO (MAX_CONCURRENT=5,
first-come first-served), so which ~200 of ~40k executed proposals it holds
depends on row order — including the arbitrary order of proposals that share
an entry timestamp. This script re-draws the baseline with only the
equal-timestamp ties shuffled and reports the spread of the bar.

    NN_META_POOL=v5 ./venv/bin/python scripts/gate_bar_sensitivity.py [--draws 8]
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # repo root
import numpy as np
import pandas as pd
from nn_meta import config, v4_evaluate as E, v4_finalize as F
from nn_meta.mark_stream import load_mark_stream
from nn_meta.select_meta import all_rows


def baseline(rows: pd.DataFrame, spec: dict, marks) -> tuple[dict, pd.DataFrame]:
    fm = E.frozen_mask(rows, spec)
    base = rows[fm].reset_index(drop=True)
    zeros = np.zeros(len(base))
    m = E._ledger_policy_metrics(base, zeros, "filter", 0.0, marks, costs=E.BASE_COSTS)
    sel = E._selected_rows(E._candidate_rows(base, zeros, "filter", 0.0), "filter")
    return m, sel


def ex_top_k(sel: pd.DataFrame, marks, k: int) -> dict:
    keep = sel.drop(index=sel["net_return"].nlargest(k).index)
    t, mk = E.execution_frames(keep, marks)
    m, _ = E.mark_to_market_portfolio(t, mk, max_concurrent=config.MAX_CONCURRENT,
                                      position_fraction=config.PORTFOLIO_FRACTION,
                                      costs=E.BASE_COSTS)
    return m


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--val-fraction", type=float, default=0.15)
    ap.add_argument("--embargo", default="1D")
    ap.add_argument("--draws", type=int, default=8)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    ds = pd.read_parquet(config.META_DATASET_PARQUET)
    spec = E.load_spec()
    marks = load_mark_stream(config.META_DATASET_PARQUET.with_suffix(".marks.parquet"))
    d = ds.copy()
    d["split"] = F._final_split(ds, args.val_fraction, args.embargo)
    val = all_rows(d, "val")                      # exactly what v4_finalize scores
    print(f"validation tail: {val['entry_ts'].min()} .. {val['entry_ts'].max()} "
          f"({len(val)} executed rows)")

    m, sel = baseline(val, spec, marks)
    print(f"\nfinalize's bar (chronological, ties in dataset order): n={m['n']} "
          f"return={m['total_return']:+.1%} maxDD={m['max_drawdown']:.1%} "
          f"ex_top3={m['total_ex_top3']:+.1%}")
    for k in (1, 3, 5, 10, 25):
        mk = ex_top_k(sel, marks, k)
        print(f"  ex-top{k:<3d}: return={mk['total_return']:+.1%} maxDD={mk['max_drawdown']:.1%}")

    rng = np.random.default_rng(args.seed)
    rows = []
    print(f"\n{args.draws} re-draws, only equal-entry_ts ties shuffled:")
    for i in range(args.draws):
        v = (val.assign(_r=rng.random(len(val))).sort_values(["entry_ts", "_r"])
             .drop(columns="_r").reset_index(drop=True))
        mi, _ = baseline(v, spec, marks)
        rows.append((mi["total_return"], mi["total_ex_top3"], mi["max_drawdown"], mi["n"]))
        print(f"  draw {i}: return={mi['total_return']:+.1%} ex_top3={mi['total_ex_top3']:+.1%} "
              f"maxDD={mi['max_drawdown']:.1%} n={mi['n']}")
    r = np.array(rows)
    print(f"\nex-top3 bar across draws: min {r[:,1].min():+.1%} | median {np.median(r[:,1]):+.1%} "
          f"| max {r[:,1].max():+.1%}   (baseline maxDD median {np.median(r[:,2]):.1%})")


if __name__ == "__main__":
    main()
