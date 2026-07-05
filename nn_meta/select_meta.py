# nn_meta/select_meta.py
"""Validation-based selection with a BASELINE GATE, one-shot test evaluation.

Protocol (fixed before test is touched):
  1. Baseline = the frozen spec's trades at each symbol's frozen DTE, taken
     from the SAME meta-dataset rows the NN filters — identical trade universe
     on both sides of every comparison.
  2. Every trained run × keep-threshold is evaluated on VALIDATION: keep rows
     with P(win) >= threshold, compound pooled per-trade returns
     chronologically at POSITION_FRACTION.
     Guardrails: >= MIN_KEPT_TRADES kept, maxDD <= cap, and THE GATE:
     filtered val return > baseline val return.
  3. A config (arch × lr × threshold) is eligible if >= MIN_PASSING_SEEDS of
     its seeds pass. Winner = highest median val return among eligible.
  4. The winning config's seeds form the final ensemble (mean P(win)).
     Run ONCE on TEST at 1x and stressed costs; report vs baseline and
     SPY buy & hold. Model bundle → model_final/.

Run:  python -m nn_meta.select_meta
"""
import json
import os
import shutil

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import numpy as np
import pandas as pd
import tensorflow as tf

from nn_meta import config
from nn_meta.baseline import equity_metrics, load_spec, load_underlying_15m
from nn_meta.build_meta_dataset import META_FEATURES
from nn_meta.train_meta import prepare_matrix

_C1 = config.FEES_PERCENT + config.SLIPPAGE_PERCENT


# ── helpers ──────────────────────────────────────────────────────────────────

def frozen_rows(ds: pd.DataFrame, spec: dict, split: str) -> pd.DataFrame:
    """Executed dataset rows at each symbol's frozen DTE, chronological."""
    keep = []
    for sym, entry in spec["symbols"].items():
        m = (ds["symbol"] == sym) & (ds["dte"] == entry["dte"]) \
            & (ds["split"] == split) & ds["executed"] & ds["net_return"].notna()
        keep.append(ds[m])
    out = pd.concat(keep) if keep else pd.DataFrame(columns=ds.columns)
    return out.sort_values("entry_ts").reset_index(drop=True)


def stress_returns(net: pd.Series, n_fills: pd.Series, mult: float) -> pd.Series:
    """Exact per-fill cost restatement: each fill's growth carries
    (1-c)/(1+c); replacing c with mult*c multiplies each fill's growth by
    ((1-c2)(1+c1)) / ((1+c2)(1-c1))."""
    c1, c2 = _C1, _C1 * mult
    k = ((1 - c2) * (1 + c1)) / ((1 + c2) * (1 - c1))
    return (1.0 + net) * np.power(k, n_fills) - 1.0


def predict_rows(run_id: str, rows: pd.DataFrame) -> np.ndarray:
    run_dir = config.RUNS_DIR / run_id
    scaler = json.loads((run_dir / "scaler.json").read_text())
    mu = pd.Series(scaler["mean"])[META_FEATURES]
    sd = pd.Series(scaler["std"])[META_FEATURES]
    X = prepare_matrix(rows, mu, sd)
    model = tf.keras.models.load_model(run_dir / "model.keras")
    return model.predict(X, batch_size=4096, verbose=0).flatten()


def evaluate_filter(rows: pd.DataFrame, pred: np.ndarray, threshold: float,
                    cost_mult: float = 1.0) -> dict:
    kept = rows[pred >= threshold].sort_values("entry_ts")
    net = kept["net_return"]
    if cost_mult != 1.0 and not kept.empty:
        net = stress_returns(net, kept["n_fills"], cost_mult)
    m = equity_metrics(net.tolist())
    m["n_kept"] = len(kept)
    m["n_proposals"] = len(rows)
    return m


def passes(m: dict, baseline_return: float) -> bool:
    return (m["n_kept"] >= config.MIN_KEPT_TRADES
            and m["total_return"] is not None
            and (m["max_drawdown"] or 0) <= config.MAX_DRAWDOWN_CAP
            and m["total_return"] > baseline_return)


def spy_buy_hold(start: str, end: str) -> float:
    bars = load_underlying_15m("SPY").loc[start:end]
    return float(bars["Close"].iloc[-1] / bars["Close"].iloc[0] - 1)


def fmt(x) -> str:
    return "n/a" if x is None else f"{x:+.1%}"


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    config.ensure_dirs()
    spec = load_spec()
    ds = pd.read_parquet(config.META_DATASET_PARQUET)
    runs = pd.read_csv(config.RUNS_CSV)

    val_rows = frozen_rows(ds, spec, "val")
    test_rows = frozen_rows(ds, spec, "test")
    base_val = equity_metrics(val_rows["net_return"].tolist())
    base_test = equity_metrics(test_rows["net_return"].tolist())
    base_test_2x = equity_metrics(
        stress_returns(test_rows["net_return"], test_rows["n_fills"],
                       config.COST_STRESS_MULT).tolist())
    print(f"baseline val: {fmt(base_val['total_return'])} ({base_val['n']} trades) | "
          f"test: {fmt(base_test['total_return'])} ({base_test['n']} trades)")

    # ── validation: every run × threshold ────────────────────────────────────
    results = []
    for r in runs.itertuples():
        pred = predict_rows(r.run_id, val_rows)
        for thr in config.KEEP_THRESHOLDS:
            m = evaluate_filter(val_rows, pred, thr)
            results.append({
                "run_id": r.run_id, "arch": r.arch, "lr": r.lr,
                "seed": int(r.seed), "threshold": thr,
                "val_return": m["total_return"], "n_kept": m["n_kept"],
                "max_dd": m["max_drawdown"], "win_rate": m["win_rate"],
                "passes": passes(m, base_val["total_return"] or -np.inf)})
        best = max((x for x in results if x["run_id"] == r.run_id),
                   key=lambda x: x["val_return"] if x["val_return"] is not None else -np.inf)
        print(f"  val {r.run_id}: best thr={best['threshold']} "
              f"{fmt(best['val_return'])} ({best['n_kept']} kept)"
              f"{' PASS' if best['passes'] else ''}", flush=True)
    vdf = pd.DataFrame(results)
    vdf.to_csv(config.RUNS_DIR / "runs_val.csv", index=False)

    # ── config eligibility + winner ──────────────────────────────────────────
    grp = vdf.groupby(["arch", "lr", "threshold"]).agg(
        median_val_return=("val_return", "median"),
        passing_seeds=("passes", "sum"),
        seeds=("seed", "count")).reset_index()
    grp = grp.sort_values("median_val_return", ascending=False)
    eligible = grp[grp["passing_seeds"] >= config.MIN_PASSING_SEEDS]

    lines = [
        "# NN Meta Filter — Selection Report", "",
        f"Dataset: {len(ds)} rows | frozen baseline: {len(spec['symbols'])} symbols "
        f"(hash `{spec['config_hash']}`) | interval {config.INTERVAL}", "",
        f"Baseline (frozen-DTE trades, pooled sequential @ "
        f"{config.POSITION_FRACTION:.0%} fraction):", "",
        "| window | return | trades | maxDD | win rate |", "|---|---|---|---|---|",
        f"| val | {fmt(base_val['total_return'])} | {base_val['n']} | "
        f"{fmt(base_val['max_drawdown'])} | {fmt(base_val['win_rate'])} |",
        f"| test | {fmt(base_test['total_return'])} | {base_test['n']} | "
        f"{fmt(base_test['max_drawdown'])} | {fmt(base_test['win_rate'])} |", "",
        f"Gate per run: kept >= {config.MIN_KEPT_TRADES}, "
        f"maxDD <= {config.MAX_DRAWDOWN_CAP:.0%}, val return > baseline val; "
        f"config eligible if >= {config.MIN_PASSING_SEEDS}/{len(config.SEEDS)} seeds pass.", "",
        "## Validation leaderboard (median across seeds)", "",
        grp.head(6).to_markdown(index=False, floatfmt=".3f"), "",
    ]

    if eligible.empty:
        lines += ["**Result: NO eligible config — the NN filter did not beat the "
                  "frozen baseline on validation. Test not evaluated.**", ""]
        (config.REPORTS_DIR / "meta_report.md").write_text("\n".join(lines))
        print("\nNO ELIGIBLE CONFIG — report written, test untouched")
        return

    best = eligible.iloc[0]
    win_ids = vdf[(vdf["arch"] == best["arch"]) & (vdf["lr"] == best["lr"])
                  & (vdf["threshold"] == best["threshold"])]["run_id"].unique().tolist()
    thr = float(best["threshold"])
    print(f"\nwinner: {best['arch']} lr={best['lr']:g} thr={thr} "
          f"(median val {fmt(best['median_val_return'])}, "
          f"{int(best['passing_seeds'])}/{len(config.SEEDS)} pass)")

    # ── final bundle ─────────────────────────────────────────────────────────
    final_dir = config.MODEL_FINAL_DIR
    if final_dir.exists():
        shutil.rmtree(final_dir)
    final_dir.mkdir(parents=True)
    for rid in win_ids:
        shutil.copytree(config.RUNS_DIR / rid, final_dir / rid)
    (final_dir / "ensemble_config.json").write_text(json.dumps({
        "run_ids": win_ids, "threshold": thr, "features": META_FEATURES,
        "arch": best["arch"], "lr": float(best["lr"]),
        "median_val_return": float(best["median_val_return"]),
        "baseline_config_hash": spec["config_hash"],
    }, indent=2))

    # ── one-shot test ────────────────────────────────────────────────────────
    preds = [predict_rows(rid, test_rows) for rid in win_ids]
    ens = np.mean(preds, axis=0)
    res_1x = evaluate_filter(test_rows, ens, thr)
    res_2x = evaluate_filter(test_rows, ens, thr, cost_mult=config.COST_STRESS_MULT)
    per_seed = [evaluate_filter(test_rows, p, thr)["total_return"] for p in preds]
    spy_bh = spy_buy_hold(config.TEST_START, config.TEST_END)

    kept_mask = ens >= thr
    test_rows.assign(pred=ens, kept=kept_mask).to_csv(
        config.REPORTS_DIR / "test_trades_meta.csv", index=False)

    lines += [
        f"## Test (one shot) — ensemble of {len(win_ids)} seeds, thr={thr}", "",
        "| strategy | return | trades | maxDD | win rate |", "|---|---|---|---|---|",
        f"| **NN-filtered (1x costs)** | **{fmt(res_1x['total_return'])}** | "
        f"{res_1x['n_kept']}/{res_1x['n_proposals']} kept | "
        f"{fmt(res_1x['max_drawdown'])} | {fmt(res_1x['win_rate'])} |",
        f"| NN-filtered ({config.COST_STRESS_MULT:.0f}x costs) | "
        f"{fmt(res_2x['total_return'])} | {res_2x['n_kept']} kept | "
        f"{fmt(res_2x['max_drawdown'])} | {fmt(res_2x['win_rate'])} |",
        f"| Frozen baseline (1x) | {fmt(base_test['total_return'])} | "
        f"{base_test['n']} | {fmt(base_test['max_drawdown'])} | "
        f"{fmt(base_test['win_rate'])} |",
        f"| Frozen baseline ({config.COST_STRESS_MULT:.0f}x) | "
        f"{fmt(base_test_2x['total_return'])} | {base_test_2x['n']} | "
        f"{fmt(base_test_2x['max_drawdown'])} | {fmt(base_test_2x['win_rate'])} |",
        f"| SPY buy & hold | {fmt(spy_bh)} | — | — | — |", "",
        f"Per-seed test return: {', '.join(fmt(x) for x in sorted(per_seed, key=lambda v: v or 0))} "
        f"(median {fmt(float(np.median([x for x in per_seed if x is not None])) if any(x is not None for x in per_seed) else None)})", "",
        "## Caveats", "",
        "- Both sides share the engine's fill convention (entry at the signal "
        "bar's option OPEN): optimistic vs live trading, identical for baseline "
        "and NN — internal comparisons remain fair.",
        "- Pooled sequential compounding ignores capital overlap across symbols;"
        " applied identically to baseline and NN.",
        f"- Costs: {_C1:.2%}/side proxy; {config.COST_STRESS_MULT:.0f}x stress "
        "restated exactly per fill.",
        "- One macro regime; val is a single ~58-day window. Walk-forward folds "
        "(walkforward_meta) are the robustness check.",
    ]
    (config.REPORTS_DIR / "meta_report.md").write_text("\n".join(lines))
    print(f"\nTEST: NN {fmt(res_1x['total_return'])} vs baseline "
          f"{fmt(base_test['total_return'])} vs SPY B&H {fmt(spy_bh)}")
    print(f"report: {config.REPORTS_DIR / 'meta_report.md'}")


if __name__ == "__main__":
    main()
