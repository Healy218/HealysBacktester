# nn_options_signal/select_and_evaluate.py
"""Validation-based selection, one-shot test evaluation, final report — for
three single-leg strategies driven by the SAME trained models:

  long      : buy the top-predicted contract        (pred > +threshold)
  short     : sell the bottom-predicted contract    (pred < -threshold, margin-sized)
  longshort : buy top + short bottom                (pred spread > pair threshold)

Protocol per strategy (fixed before test is touched):
  1. Backtest every trained run on the VALIDATION period.
  2. Guardrails per run: >= MIN_TRADES decisions, maxDD <= cap, PF >= floor.
     A config is eligible if >= MIN_PASSING_SEEDS of its seeds pass.
  3. Among eligible configs, pick the highest MEDIAN validation P/L%.
  4. Final signal = mean prediction across the winning config's seeds.
     Run ONCE on test, at 1x and stressed costs. Report per-seed dispersion.
  5. Benchmarks through the same simulator on SPY only: buy-and-hold,
     mechanical ATM-call buy, mechanical ATM-call sell, mechanical ATM-put sell.

Run:  python -m nn_options_signal.select_and_evaluate
"""
import json
import os
import shutil

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import numpy as np
import pandas as pd
import tensorflow as tf

from nn_options_signal import config
from nn_options_signal.build_dataset import FEATURES
from nn_options_signal.backtest import run_backtest, mechanical_atm_score

STRATEGIES = ["long", "short", "longshort"]


def predict_run(run_id: str, rows: pd.DataFrame) -> np.ndarray:
    run_dir = config.RUNS_DIR / run_id
    scaler = json.loads((run_dir / "scaler.json").read_text())
    mu = pd.Series(scaler["mean"])[FEATURES]
    sd = pd.Series(scaler["std"])[FEATURES]
    X = ((rows[FEATURES] - mu) / sd).values.astype("float32")
    model = tf.keras.models.load_model(run_dir / "model.keras")
    return model.predict(X, batch_size=4096, verbose=0).flatten()


def passes_guardrails(m: dict) -> bool:
    return (m["n_trades"] >= config.MIN_TRADES
            and m["max_drawdown"] <= config.MAX_DRAWDOWN_CAP
            and m["profit_factor"] >= config.MIN_PROFIT_FACTOR)


def fmt_pct(x: float) -> str:
    return f"{x:+.1%}"


def benchmarks_section(test: pd.DataFrame, spy: pd.DataFrame, H: int) -> list[str]:
    s = spy[(spy["date"] >= config.TEST_START) & (spy["date"] <= config.TEST_END)]
    spy_bh = float(s["close"].iloc[-1] / s["close"].iloc[0] - 1)
    t = test[test["underlying"] == "SPY"].copy() if "underlying" in test.columns else test.copy()
    rows = [("SPY buy & hold", fmt_pct(spy_bh))]
    for label, right, mode in [("Mechanical ATM-call BUY", "call", "long"),
                               ("Mechanical ATM-call SELL", "call", "short"),
                               ("Mechanical ATM-put SELL", "put", "short")]:
        score = mechanical_atm_score(t, right)
        t["bench"] = score if mode == "long" else -score
        thr = 1.0 if mode == "long" else -1.0
        b = run_backtest(t, "bench", H, mode=mode, threshold=thr)
        rows.append((label, f"{fmt_pct(b['total_return'])} ({b['n_trades']} trades, "
                            f"dd {b['max_drawdown']:.0%})"))
    return ["| strategy | test P/L% |", "|---|---|"] + [f"| {a} | {b} |" for a, b in rows]


def main() -> None:
    panel = pd.read_parquet(config.DATASET_PARQUET)
    runs = pd.read_csv(config.RUNS_CSV)
    val = panel[panel["split"] == "val"].copy()
    test = panel[panel["split"] == "test"].copy()
    und = pd.read_parquet(config.UNDERLYING_PARQUET)
    spy = und[und["underlying"] == "SPY"] if "underlying" in und.columns else und

    # ── validation backtests: predict once per run, evaluate all strategies ──
    val_rows = []
    for r in runs.itertuples():
        val["pred"] = predict_run(r.run_id, val)
        for strat in STRATEGIES:
            m = run_backtest(val, "pred", int(r.horizon), mode=strat)
            val_rows.append({"strategy": strat, "run_id": r.run_id, "arch": r.arch,
                             "lr": r.lr, "horizon": int(r.horizon), "seed": int(r.seed),
                             "val_return": m["total_return"], "n_trades": m["n_trades"],
                             "max_dd": m["max_drawdown"],
                             "profit_factor": m["profit_factor"],
                             "win_rate": m["win_rate"], "passes": passes_guardrails(m)})
        done = [x for x in val_rows if x["run_id"] == r.run_id]
        print(f"  val {r.run_id}: " + " | ".join(
            f"{d['strategy']} {d['val_return']:+.1%} ({d['n_trades']}t, "
            f"pf {d['profit_factor']:.2f}){' PASS' if d['passes'] else ''}"
            for d in done), flush=True)
    vdf = pd.DataFrame(val_rows)
    vdf.to_csv(config.RUNS_DIR / "runs_val.csv", index=False)

    lines = ["# Options NN Signal — Final Report (long / short / long-short)", "",
             f"Window {config.WINDOW_START} → {config.WINDOW_END} | "
             f"train {config.TRAIN_START}→{config.TRAIN_END}, "
             f"val {config.VAL_START}→{config.VAL_END}, "
             f"test {config.TEST_START}→{config.TEST_END} (purged splits)", "",
             f"Panel: {len(panel)} rows, {panel['ticker'].nunique()} contracts, "
             f"{panel['underlying'].nunique()} underlyings | {len(runs)} training runs "
             f"(150 epochs, best-val-epoch weights) | same models drive all strategies", "",
             f"Guardrails per run: decisions >= {config.MIN_TRADES}, "
             f"maxDD <= {config.MAX_DRAWDOWN_CAP:.0%}, PF >= {config.MIN_PROFIT_FACTOR}; "
             f"config eligible if >= {config.MIN_PASSING_SEEDS}/5 seeds pass.", ""]

    test_pred_cache: dict[str, np.ndarray] = {}
    summary = []

    for strat in STRATEGIES:
        sv = vdf[vdf["strategy"] == strat]
        grp = sv.groupby(["arch", "lr", "horizon"]).agg(
            median_val_return=("val_return", "median"),
            passing_seeds=("passes", "sum"), seeds=("seed", "count")).reset_index()
        grp = grp.sort_values("median_val_return", ascending=False)
        eligible = grp[grp["passing_seeds"] >= config.MIN_PASSING_SEEDS]

        lines += [f"## Strategy: {strat.upper()}", "",
                  "Validation leaderboard (median across seeds):", "",
                  grp.head(4).to_markdown(index=False, floatfmt=".3f"), ""]

        if eligible.empty:
            lines += [f"**Result: no eligible config for {strat}** — test not evaluated.", ""]
            summary.append((strat, None))
            print(f"\n[{strat}] NO ELIGIBLE CONFIG")
            continue

        best = eligible.iloc[0]
        win_ids = sv[(sv["arch"] == best["arch"]) & (sv["lr"] == best["lr"])
                     & (sv["horizon"] == best["horizon"])]["run_id"].tolist()
        H = int(best["horizon"])
        print(f"\n[{strat}] winner: {best['arch']} lr={best['lr']:g} h={H} "
              f"(median val {best['median_val_return']:+.1%}, "
              f"{int(best['passing_seeds'])}/5 pass)")

        # final model bundle for this strategy
        final_dir = config.ROOT / "model_final" / strat
        if final_dir.exists():
            shutil.rmtree(final_dir)
        final_dir.mkdir(parents=True)
        for rid in win_ids:
            shutil.copytree(config.RUNS_DIR / rid, final_dir / rid)
        (final_dir / "ensemble_config.json").write_text(json.dumps({
            "strategy": strat, "run_ids": win_ids, "horizon": H,
            "arch": best["arch"], "lr": float(best["lr"]),
            "threshold": {"long": config.PRED_THRESHOLD,
                          "short": config.SHORT_PRED_THRESHOLD,
                          "longshort": config.PRED_SPREAD_THRESHOLD}[strat],
            "features": FEATURES,
            "median_val_return": float(best["median_val_return"]),
        }, indent=2))

        # one-shot test: seed ensemble + dispersion
        for rid in win_ids:
            if rid not in test_pred_cache:
                test_pred_cache[rid] = predict_run(rid, test)
        test["pred"] = np.mean([test_pred_cache[rid] for rid in win_ids], axis=0)
        res_1x = run_backtest(test, "pred", H, mode=strat, cost_mult=1.0)
        res_2x = run_backtest(test, "pred", H, mode=strat,
                              cost_mult=config.COST_STRESS_MULT)
        per_seed = []
        for rid in win_ids:
            test["pred_seed"] = test_pred_cache[rid]
            per_seed.append(run_backtest(test, "pred_seed", H, mode=strat)["total_return"])

        res_1x["trades"].to_csv(config.REPORTS_DIR / f"test_trades_{strat}.csv", index=False)
        res_1x["equity_curve"].to_csv(
            config.REPORTS_DIR / f"test_equity_curve_{strat}.csv", index=False)

        lines += [
            f"Selected config: `{best['arch']} lr={best['lr']:g} h={H}` — "
            f"ensemble of 5 seeds, model bundle in `model_final/{strat}/`", "",
            "| metric | value |", "|---|---|",
            f"| **Test P/L% (1x costs)** | **{fmt_pct(res_1x['total_return'])}** |",
            f"| Test P/L% ({config.COST_STRESS_MULT:.0f}x costs) | {fmt_pct(res_2x['total_return'])} |",
            f"| Decisions / legs | {res_1x['n_trades']} / {res_1x['n_legs']} |",
            f"| Win rate (legs) | {res_1x['win_rate']:.0%} |",
            f"| Profit factor | {res_1x['profit_factor']:.2f} |",
            f"| Max drawdown | {res_1x['max_drawdown']:.1%} |",
            "",
            f"Per-seed test P/L: {', '.join(fmt_pct(x) for x in sorted(per_seed))} "
            f"(median {fmt_pct(float(np.median(per_seed)))})", "",
            "Benchmarks (SPY-only, same simulator):", ""]
        lines += benchmarks_section(test, spy, H) + [""]
        summary.append((strat, res_1x["total_return"]))
        print(f"[{strat}] TEST P/L: {fmt_pct(res_1x['total_return'])} (1x) | "
              f"{fmt_pct(res_2x['total_return'])} "
              f"({config.COST_STRESS_MULT:.0f}x) | per-seed median "
              f"{fmt_pct(float(np.median(per_seed)))}")

    lines += [
        "## Caveats", "",
        "- One macro regime, ~360 trading days: each test number is a single draw.",
        "- Daily bars: next-open fills, horizon-close exits, no intrabar stops;",
        "  results are optimistic by construction.",
        "- Short legs: naked-margin formula approximates broker requirements off",
        "  the decision-day spot; early-assignment risk on American options is",
        "  NOT modeled — real short-side results will be worse around dividends",
        "  and deep-ITM moves.",
        "- Selection ran three strategies in parallel; all three verdicts are",
        "  reported (no picking the best strategy after the fact and hiding the",
        "  others).",
    ]
    (config.REPORTS_DIR / "final_report.md").write_text("\n".join(lines))
    print(f"\nreport: {config.REPORTS_DIR / 'final_report.md'}")
    for strat, ret in summary:
        print(f"  {strat:10s}: {'NO ELIGIBLE CONFIG' if ret is None else fmt_pct(ret)}")


if __name__ == "__main__":
    main()
