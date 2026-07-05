# nn_meta/student/evaluate_student.py
"""Student go/no-go, baseline-gated selection, one-shot test.

Protocol (fixed before test):
  1. CLONE PARITY (go/no-go): each run's stage-1 clone generates trades on
     VALIDATION; its pooled option return must land within
     CLONE_PARITY_TOLERANCE of the frozen baseline's (or beat it). A student
     that cannot reproduce its teacher is broken — if every run fails, stop.
  2. Fine-tuned models are evaluated on validation through the same pipeline:
     per-bar probs → hysteresis states → trades → option execution at the
     frozen DTE. Gate: beat the frozen baseline + guardrails.
  3. Config (lr) eligible if >= MIN_PASSING_SEEDS seeds pass; winner by
     median val return; seed-ensemble (mean probs) runs ONCE on test.

Run:  python -m nn_meta.student.evaluate_student
"""
import json
import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import numpy as np
import pandas as pd
import tensorflow as tf

from nn_meta.providers import get_provider
from nn_meta import config
from nn_meta.baseline import (equity_metrics, execute_at_dte, load_spec,
                              load_underlying_15m, top_k_contribution)
from nn_meta.select_meta import basket_buy_hold, fmt, frozen_rows, spy_buy_hold
from nn_meta.student.dataset import STUDENT_FEATURES
from nn_meta.student.policy import states_from_probs, trades_from_states


def _load_run(run_id: str, clone: bool):
    run_dir = config.RUNS_DIR / run_id
    scaler = json.loads((run_dir / "scaler.json").read_text())
    mu = pd.Series(scaler["mean"])[STUDENT_FEATURES]
    sd = pd.Series(scaler["std"])[STUDENT_FEATURES]
    name = "model_clone.keras" if clone else "model.keras"
    return tf.keras.models.load_model(run_dir / name), mu, sd


def _probs(model, mu, sd, rows: pd.DataFrame) -> np.ndarray:
    X = ((rows[STUDENT_FEATURES].fillna(mu) - mu) / sd).values.astype("float32")
    return model.predict(X, batch_size=8192, verbose=0)


def eval_policy(run_ids: list[str], panel: pd.DataFrame, split: str,
                spec: dict, provider, bars_cache: dict, clone: bool = False) -> dict:
    """probs (ensemble mean) → states → trades → option P&L, pooled."""
    models = [_load_run(rid, clone) for rid in run_ids]
    all_records = []
    n_trades = 0
    for sym, entry in spec["symbols"].items():
        rows = panel[(panel["symbol"] == sym) & (panel["split"] == split)]
        rows = rows.sort_values("bar_ts")
        if rows.empty:
            continue
        p = np.mean([_probs(m, mu, sd, rows) for m, mu, sd in models], axis=0)
        states = states_from_probs(p)
        trades = trades_from_states(states, pd.DatetimeIndex(rows["bar_ts"]))
        if not trades:
            continue
        n_trades += len(trades)
        if sym not in bars_cache:
            bars_cache[sym] = load_underlying_15m(sym)
        records, _ = execute_at_dte(sym, trades, bars_cache[sym], entry["dte"],
                                    provider, config.WINDOW_END)
        all_records.extend(r for r in records if r["executed"])

    all_records.sort(key=lambda r: r["fill_entry_ts"])
    rets = [r["net_return"] for r in all_records]
    m = equity_metrics(rets)
    m["n_signals"] = n_trades
    m["total_ex_top3"] = top_k_contribution(rets)["total_ex_topk"]
    return m


def passes(m: dict, baseline_return: float, bh_return: float) -> bool:
    return (m["n"] >= config.MIN_KEPT_TRADES
            and m["total_return"] is not None
            and (m["max_drawdown"] or 0) <= config.MAX_DRAWDOWN_CAP
            and m["total_return"] > baseline_return
            and m["total_return"] > bh_return)


def main() -> None:
    config.ensure_dirs()
    spec = load_spec()
    panel = pd.read_parquet(config.STUDENT_DATASET_PARQUET)
    meta_ds = pd.read_parquet(config.META_DATASET_PARQUET)
    runs = pd.read_csv(config.STUDENT_RUNS_CSV)
    provider = get_provider()
    bars_cache: dict = {}

    base_val = equity_metrics(frozen_rows(meta_ds, spec, "val")["net_return"].tolist())
    base_test_rows = frozen_rows(meta_ds, spec, "test")
    base_test = equity_metrics(base_test_rows["net_return"].tolist())
    bh_val = basket_buy_hold(spec, config.VAL_START, config.VAL_END)
    bh_test = basket_buy_hold(spec, config.TEST_START, config.TEST_END)
    print(f"baseline val {fmt(base_val['total_return'])} | "
          f"test {fmt(base_test['total_return'])} | "
          f"underlying B&H val {fmt(bh_val)} | test {fmt(bh_test)}")

    # ── 1) clone parity + 2) fine-tuned val, per run ──────────────────────────
    rows = []
    for r in runs.itertuples():
        clone_m = eval_policy([r.run_id], panel, "val", spec, provider,
                              bars_cache, clone=True)
        parity = (clone_m["total_return"] is not None
                  and clone_m["total_return"] >=
                  (base_val["total_return"] or 0) - config.CLONE_PARITY_TOLERANCE)
        ft_m = eval_policy([r.run_id], panel, "val", spec, provider, bars_cache)
        ok = parity and passes(ft_m, base_val["total_return"] or -np.inf, bh_val)
        rows.append({"run_id": r.run_id, "lr": r.lr, "seed": int(r.seed),
                     "clone_val_return": clone_m["total_return"],
                     "clone_parity": parity,
                     "val_return": ft_m["total_return"], "n_trades": ft_m["n"],
                     "max_dd": ft_m["max_drawdown"], "passes": ok})
        print(f"  {r.run_id}: clone {fmt(clone_m['total_return'])} "
              f"({'parity OK' if parity else 'PARITY FAIL'}) | "
              f"fine-tuned {fmt(ft_m['total_return'])} "
              f"({ft_m['n']} trades){' PASS' if ok else ''}", flush=True)
    vdf = pd.DataFrame(rows)
    vdf.to_csv(config.RUNS_DIR / "runs_student_val.csv", index=False)

    lines = ["# Student (teacher→student) — Evaluation", "",
             f"Frozen baseline: val {fmt(base_val['total_return'])}, "
             f"test {fmt(base_test['total_return'])} | clone parity tolerance "
             f"{config.CLONE_PARITY_TOLERANCE:.0%}", ""]

    # ── go/no-go ──────────────────────────────────────────────────────────────
    if not vdf["clone_parity"].any():
        lines += ["**GO/NO-GO: STOP — no run's clone reproduced the teacher on "
                  "validation.** Fine-tuning a broken student is meaningless; "
                  "fix cloning first (features, hysteresis, capacity).", ""]
        (config.REPORTS_DIR / "student_report.md").write_text("\n".join(lines))
        print("\nGO/NO-GO: STOP — cloning failed for every run")
        return

    grp = vdf.groupby("lr").agg(median_val=("val_return", "median"),
                                passing=("passes", "sum"),
                                parity_ok=("clone_parity", "sum"),
                                seeds=("seed", "count")).reset_index()
    grp = grp.sort_values("median_val", ascending=False)
    eligible = grp[grp["passing"] >= config.MIN_PASSING_SEEDS]
    lines += ["## Validation (per lr, median across seeds)", "",
              grp.to_markdown(index=False, floatfmt=".3f"), ""]

    if eligible.empty:
        lines += ["**Result: no eligible config — the student did not beat the "
                  "frozen baseline on validation. Test not evaluated.**", ""]
        (config.REPORTS_DIR / "student_report.md").write_text("\n".join(lines))
        print("\nNO ELIGIBLE CONFIG — test untouched")
        return

    best = eligible.iloc[0]
    win_ids = vdf[vdf["lr"] == best["lr"]]["run_id"].tolist()
    print(f"\nwinner: lr={best['lr']:g} (median val {fmt(best['median_val'])}, "
          f"{int(best['passing'])}/{len(config.SEEDS)} pass)")

    # ── one-shot test ─────────────────────────────────────────────────────────
    res = eval_policy(win_ids, panel, "test", spec, provider, bars_cache)
    spy_bh = spy_buy_hold(config.TEST_START, config.TEST_END)
    lines += [
        f"## Test (one shot) — ensemble of {len(win_ids)} seeds", "",
        "| strategy | return | trades | maxDD | win rate | ex-top3 |",
        "|---|---|---|---|---|---|",
        f"| **Student (own signals)** | **{fmt(res['total_return'])}** | "
        f"{res['n']} | {fmt(res['max_drawdown'])} | {fmt(res['win_rate'])} | "
        f"{fmt(res['total_ex_top3'])} |",
        f"| Frozen baseline | {fmt(base_test['total_return'])} | "
        f"{base_test['n']} | {fmt(base_test['max_drawdown'])} | "
        f"{fmt(base_test['win_rate'])} | "
        f"{fmt(top_k_contribution(base_test_rows['net_return'].tolist())['total_ex_topk'])} |",
        f"| Underlying B&H basket | {fmt(bh_test)} | — | — | — | — |",
        f"| SPY buy & hold | {fmt(spy_bh)} | — | — | — | — |", "",
        "Same conventions as the meta report: next-bar fills, pooled sequential "
        f"compounding @ {config.POSITION_FRACTION:.0%}, one macro regime.",
    ]
    (config.REPORTS_DIR / "student_report.md").write_text("\n".join(lines))
    print(f"\nTEST: student {fmt(res['total_return'])} vs baseline "
          f"{fmt(base_test['total_return'])} vs SPY {fmt(spy_bh)}")
    print(f"report: {config.REPORTS_DIR / 'student_report.md'}")


if __name__ == "__main__":
    main()
