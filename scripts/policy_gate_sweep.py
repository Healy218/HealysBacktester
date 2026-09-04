"""Offline policy × gate sweep on a finalize run's saved validation predictions.

The ensemble is trained once (deterministic); every threshold, mode and gate
parameter is a POST-HOC policy on its predictions. So instead of one finalize
run per idea, this sweeps them all from `finalize_val_predictions.parquet`
(written by v4_finalize since 2026-09-04) in minutes:

  * P(win) cuts 0.20 … 0.90 for filter and rank modes (the "confidence" axis)
  * the EV grid (thresholds × drawdown brakes) exactly as choose_policy tries
  * every gate variant (config.GATE_BARS) with its parameters varied:
      risk         — DD floor {0.02, 0.05, 0.10}
      median_draws — draws {8, 16}
      ex_topk_pct  — k = {2%, 5%, 10%} of the entered book

    NN_META_POOL=v5 ./venv/bin/python scripts/policy_gate_sweep.py \
        [--predictions nn_meta/reports_v5/finalize_val_predictions.parquet] \
        [--pred-col pred_ensemble --ev-col ev_ensemble] [--thresholds 0.2:0.9:0.05]

Writes <reports>/policy_gate_sweep.{md,csv}.
"""
from __future__ import annotations
import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # repo root
import numpy as np
import pandas as pd
from nn_meta import config, v4_evaluate as E, v4_finalize as F
from nn_meta.mark_stream import load_mark_stream, stable_trade_id
from nn_meta.select_meta import all_rows


def _parse_thresholds(spec: str) -> list[float]:
    if ":" in spec:
        lo, hi, step = (float(x) for x in spec.split(":"))
        n = int(round((hi - lo) / step)) + 1
        return [round(lo + i * step, 4) for i in range(n)]
    return [float(t) for t in spec.split(",") if t.strip()]


def _fmt(v, pct=True, signed=True):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "n/a"
    if not pct:
        return f"{v:.2f}"
    return f"{v:+.1%}" if signed else f"{v:.1%}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--predictions", type=Path,
                    default=config.REPORTS_DIR / "finalize_val_predictions.parquet")
    ap.add_argument("--pred-col", default="pred_ensemble")
    ap.add_argument("--ev-col", default="ev_ensemble")
    ap.add_argument("--val-fraction", type=float, default=0.15)
    ap.add_argument("--embargo", default="1D")
    ap.add_argument("--thresholds", default="0.2:0.9:0.05")
    ap.add_argument("--ev-thresholds", default=",".join(str(t) for t in config.EV_THRESHOLDS))
    ap.add_argument("--draws", default="8,16")
    ap.add_argument("--topk-pcts", default="0.02,0.05,0.10")
    ap.add_argument("--dd-floors", default="0.02,0.05,0.10")
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()

    preds = pd.read_parquet(args.predictions)
    ds = pd.read_parquet(config.META_DATASET_PARQUET)
    spec = E.load_spec()
    marks = load_mark_stream(config.META_DATASET_PARQUET.with_suffix(".marks.parquet"))
    d = ds.copy()
    d["split"] = F._final_split(ds, args.val_fraction, args.embargo)
    val = all_rows(d, "val")                       # the rows finalize scored
    tid = stable_trade_id(val)
    if "trade_id" in preds.columns and len(preds) == len(val) and (preds["trade_id"].to_numpy() == tid.to_numpy()).all():
        pred = preds[args.pred_col].to_numpy(float)
        ev = preds[args.ev_col].to_numpy(float) if args.ev_col in preds.columns else None
    else:                                           # align by trade id
        m = preds.set_index("trade_id")
        pred = m.loc[tid, args.pred_col].to_numpy(float)
        ev = m.loc[tid, args.ev_col].to_numpy(float) if args.ev_col in preds.columns else None
    if ev is not None and np.isnan(ev).all():
        ev = None
    print(f"validation tail: {val['entry_ts'].min()} .. {val['entry_ts'].max()} "
          f"({len(val)} rows) | pred={args.pred_col} | ev={'yes' if ev is not None else 'no'}")
    q = np.quantile(pred, [0.5, 0.9, 0.99, 1.0])
    print(f"P(win) score quantiles: p50 {q[0]:.3f} p90 {q[1]:.3f} p99 {q[2]:.3f} max {q[3]:.3f}")

    # ── the frozen book once, plus every gate parameterisation of it ─────────
    fmask = E.frozen_mask(val, spec)
    base_rows = val[fmask].reset_index(drop=True)
    baseline = E._ledger_policy_metrics(base_rows, np.zeros(len(base_rows)), "filter", 0.0,
                                        marks, costs=E.BASE_COSTS)
    print(f"frozen book: n={baseline['n']} return={_fmt(baseline['total_return'])} "
          f"maxDD={_fmt(baseline['max_drawdown'], signed=False)} ex_top3={_fmt(baseline['total_ex_top3'])} "
          f"(ex-top3 book maxDD {_fmt(baseline.get('ex_top3_max_drawdown'), signed=False)})")
    draws_list = [int(x) for x in args.draws.split(",")]
    pcts = [float(x) for x in args.topk_pcts.split(",")]
    floors = [float(x) for x in args.dd_floors.split(",")]
    bars: dict[str, dict] = {}                     # gate label -> baseline dict variant
    bars["gate:ex_top3"] = dict(baseline)
    for fl in floors:
        bars[f"gate:risk(floor={fl:.2f})"] = dict(baseline, _floor=fl)
    extras_by_draws = {}
    for n in draws_list:
        ex = E._baseline_gate_extras(base_rows, marks, costs=E.BASE_COSTS, draws=n,
                                     topk_pct=pcts[0])
        extras_by_draws[n] = ex
        bars[f"gate:median_draws(n={n})"] = dict(baseline, **ex)
        print(f"  median ex-top3 over {n} draws: {_fmt(ex['ex_top3_median_draws'])} "
              f"(draws: {', '.join(_fmt(v) for v in ex['ex_top3_draws'])})")
    for pct in pcts:
        ex = E._baseline_gate_extras(base_rows, marks, costs=E.BASE_COSTS, draws=1, topk_pct=pct)
        bars[f"gate:ex_topk({pct:.0%}, k={ex['ex_topk_k']})"] = dict(baseline, **ex)
        print(f"  ex-top-k at {pct:.0%} of the book (k={ex['ex_topk_k']}): {_fmt(ex['total_ex_topk'])}")

    def verdict(metrics: dict, label: str) -> bool:
        b = bars[label]
        label = label.removeprefix("gate:")
        if label.startswith("risk"):
            old = config.GATE_DD_FLOOR
            config.GATE_DD_FLOOR = b["_floor"]
            try:
                return E._passes_gate(metrics, b, gate_bar="risk")
            finally:
                config.GATE_DD_FLOOR = old
        if label.startswith("median"):
            return E._passes_gate(metrics, b, gate_bar="median_draws")
        if label.startswith("ex_topk"):
            return E._passes_gate(metrics, b, gate_bar="ex_topk_pct")
        return E._passes_gate(metrics, b, gate_bar="ex_top3")

    # ── candidates: the confidence axis + the EV grid ────────────────────────
    rows = []
    thresholds = _parse_thresholds(args.thresholds)
    for mode in config.EVAL_MODES:
        eval_rows = base_rows if mode == "filter" else val
        eval_pred = pred[fmask] if mode == "filter" else pred
        for t in thresholds:
            m = E._ledger_policy_metrics(eval_rows, eval_pred, mode, t, marks, costs=E.BASE_COSTS)
            rows.append(("%s/%.2f" % (mode, t), mode, t, None, m))
    if ev is not None:
        for t in _parse_thresholds(args.ev_thresholds):
            for brake in config.EV_DD_BRAKES:
                m = E._ledger_policy_metrics(val, ev, config.EV_MODE, t, marks,
                                             costs=E.BASE_COSTS, dd_brake=brake)
                rows.append((E.policy_label({"mode": "ev", "threshold": t, "dd_brake": brake}),
                             "ev", t, brake, m))

    gate_labels = list(bars)
    table = []
    for label, mode, t, brake, m in rows:
        rec = {"policy": label, "mode": mode, "threshold": t, "brake": brake,
               "kept": m["n_kept"], "return": m["total_return"], "maxDD": m["max_drawdown"],
               "cand_ex_top3": m.get("total_ex_top3"),
               "ret_per_dd": None if m["total_return"] is None else
               E._risk_ratio(m["total_return"], m["max_drawdown"])}
        for g in gate_labels:
            rec[g] = verdict(m, g) if m["total_return"] is not None else False
        table.append(rec)
    df = pd.DataFrame(table)
    out = args.output or (config.REPORTS_DIR / "policy_gate_sweep.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out.with_suffix(".csv"), index=False)

    lines = ["# Policy × gate sweep (validation tail, finalize predictions)", "",
             f"Predictions: `{args.predictions.name}` column `{args.pred_col}`; "
             f"window {val['entry_ts'].min().date()} → {val['entry_ts'].max().date()}; "
             f"{len(val)} executed proposals.", "",
             f"Frozen book: n={baseline['n']}, return {_fmt(baseline['total_return'])}, "
             f"maxDD {_fmt(baseline['max_drawdown'], signed=False)}, ex-top3 {_fmt(baseline['total_ex_top3'])}.", "",
             "## Gate bars", "", "| gate | bar |", "|---|---|"]
    for g in gate_labels:
        b = bars[g]
        if g.startswith("risk"):
            bar = f"return/maxDD > {E._risk_ratio(b['total_ex_top3'], b.get('ex_top3_max_drawdown') or b['max_drawdown']):.2f} (floor {b['_floor']:.2f})"
        elif g.startswith("median"):
            bar = f"return > {_fmt(b['ex_top3_median_draws'])}"
        elif g.startswith("ex_topk"):
            bar = f"return > {_fmt(b['total_ex_topk'])}"
        else:
            bar = f"return > {_fmt(b['total_ex_top3'])}"
        lines.append(f"| {g} | {bar} |")
    lines += ["", "Every gate also requires kept ≥ %d and maxDD ≤ %.0f%%." % (config.MIN_KEPT_TRADES, 100 * config.MAX_DRAWDOWN_CAP), "",
              "## Candidates", "",
              "| policy | kept | return | maxDD | ret/DD | ex-top3 | " + " | ".join(gate_labels) + " |",
              "|---|---|---|---|---|---|" + "---|" * len(gate_labels)]
    for r in table:
        cells = [r["policy"], str(r["kept"]), _fmt(r["return"]), _fmt(r["maxDD"], signed=False),
                 _fmt(r["ret_per_dd"], pct=False), _fmt(r["cand_ex_top3"])]
        cells += ["✓" if r[g] else "·" for g in gate_labels]
        lines.append("| " + " | ".join(cells) + " |")
    out.write_text("\n".join(lines) + "\n")
    print(f"\nwrote {out} and {out.with_suffix('.csv')}")
    print("\n".join(lines[lines.index("## Candidates"):]))


if __name__ == "__main__":
    main()
