# nn_meta/select_meta.py
"""Validation-based selection with a BASELINE GATE, one-shot test evaluation.

v2.1 protocol (fixed before test is touched):
  1. Baseline = every proposal strategy's trades at its own frozen params/DTE
     (from the v2 spec), pooled chronologically — the "take everything"
     mechanical strategy. Underlying-basket buy & hold is the second gate bar.
  2. Every trained run (arch × lr × LABEL) is evaluated on VALIDATION under
     every mode × threshold:
       filter : keep proposals at their strategy-frozen DTE with score >= thr
                (sequential compounding, v1 semantics)
       rank   : cross-sectional top-K portfolio — same-bar candidates compete
                on score, DTE variants of one trade dedupe to the best-scored,
                up to MAX_CONCURRENT concurrent slots at PORTFOLIO_FRACTION
                of equity each, P&L applied at each exit
     Gate: >= MIN_KEPT_TRADES, maxDD cap, beat baseline AND basket B&H.
  3. Config eligible if >= MIN_PASSING_SEEDS seeds pass; winner = highest
     median val return; seed ensemble runs ONCE on test. A rank-calibration
     table (score quintile vs realized return) shows whether "best initial
     choice" actually was "best performing".

Run:  python -m nn_meta.select_meta
"""
import json
import os
import shutil
from pathlib import Path

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import numpy as np
import pandas as pd
import tensorflow as tf

from nn_meta import config
from nn_meta.baseline import load_spec, load_underlying_15m
from nn_meta.build_meta_dataset import META_FEATURES
from nn_meta.train_meta import prepare_matrix

_C1 = config.FEES_PERCENT + config.SLIPPAGE_PERCENT


# ── row selection helpers ─────────────────────────────────────────────────────

def _frozen_dte_map(spec: dict) -> dict:
    return {(sym, strat): e["dte"]
            for sym, entry in spec["symbols"].items()
            for strat, e in entry["strategies"].items()}


def frozen_mask(rows: pd.DataFrame, spec: dict) -> np.ndarray:
    """True where a row's DTE equals its (symbol, strategy)'s frozen DTE."""
    fmap = _frozen_dte_map(spec)
    target = [fmap.get((s, st)) for s, st in zip(rows["symbol"], rows["strategy"])]
    return np.array([d == t for d, t in zip(rows["dte"], target)], dtype=bool)


def frozen_rows(ds: pd.DataFrame, spec: dict, split: str) -> pd.DataFrame:
    """Executed rows at each (symbol, strategy)'s frozen DTE, chronological."""
    m = (ds["split"] == split) & ds["executed"] & ds["net_return"].notna()
    sub = ds[m]
    return sub[frozen_mask(sub, spec)].sort_values("entry_ts").reset_index(drop=True)


def all_rows(ds: pd.DataFrame, split: str) -> pd.DataFrame:
    """Every executed row (all DTE variants) — the rank mode's candidate pool."""
    m = (ds["split"] == split) & ds["executed"] & ds["net_return"].notna()
    return ds[m].sort_values("entry_ts").reset_index(drop=True)


# ── cost restatement ─────────────────────────────────────────────────────────

def stress_returns(net: pd.Series, n_fills: pd.Series, mult: float) -> pd.Series:
    """Exact per-fill cost restatement (each fill carries (1-c)/(1+c))."""
    c1, c2 = _C1, _C1 * mult
    k = ((1 - c2) * (1 + c1)) / ((1 + c2) * (1 - c1))
    return (1.0 + net) * np.power(k, n_fills) - 1.0


# ── model scoring ─────────────────────────────────────────────────────────────

def resolve_run_dir(run_id: str) -> Path:
    """runs/ when training artifacts exist, else the committed model_final/
    copy — deployed hosts only carry the latter (live scanner hit this)."""
    run_dir = config.RUNS_DIR / run_id
    if not (run_dir / "scaler.json").exists():
        run_dir = config.MODEL_FINAL_DIR / run_id
    return run_dir


def predict_rows(run_id: str, rows: pd.DataFrame) -> np.ndarray:
    run_dir = resolve_run_dir(run_id)
    scaler = json.loads((run_dir / "scaler.json").read_text())
    mu = pd.Series(scaler["mean"])[META_FEATURES]
    sd = pd.Series(scaler["std"])[META_FEATURES]
    X = prepare_matrix(rows, mu, sd)
    model = tf.keras.models.load_model(run_dir / "model.keras")
    return model.predict(X, batch_size=4096, verbose=0).flatten()


# ── slot-portfolio evaluation (baseline / filter / rank all share this) ──────

def _portfolio_sim(cands: pd.DataFrame, k: int, f: float):
    """Slot-based portfolio. Candidates sharing an entry bar compete on ``pred``
    for up to ``k`` concurrent slots (one position per symbol), each sized
    f × equity-at-entry; P&L is realized at each position's exit. This bounds
    exposure to k·f of equity — the sane way to aggregate thousands of trades
    across 55 names (naive sequential compounding of a pooled stream explodes).

    Returns (total_return, max_drawdown, [(row_index, net_return), ...])."""
    open_pos: list = []          # (exit_ts, amount, ret, symbol)
    open_syms: set = set()
    equity, peak, max_dd = 1.0, 1.0, 0.0
    entered: list = []

    def _close_due(now):
        nonlocal equity, peak, max_dd
        for p in sorted([p for p in open_pos if p[0] <= now], key=lambda x: x[0]):
            open_pos.remove(p)
            open_syms.discard(p[3])
            equity += p[1] * p[2]
            peak = max(peak, equity)
            max_dd = max(max_dd, (peak - equity) / peak)

    for ts, grp in cands.groupby("entry_ts", sort=True):
        _close_due(ts)
        for r in grp.sort_values("pred", ascending=False).itertuples():
            if len(open_pos) >= k or r.symbol in open_syms:
                continue
            open_pos.append((pd.Timestamp(r.exit_ts), f * equity,
                             float(r.net_return), r.symbol))
            open_syms.add(r.symbol)
            entered.append((r.Index, float(r.net_return)))
    _close_due(pd.Timestamp.max)
    return equity - 1.0, max_dd, entered


def portfolio_metrics(cands: pd.DataFrame, n_proposals: int | None = None,
                      k: int = config.MAX_CONCURRENT,
                      f: float = config.PORTFOLIO_FRACTION) -> dict:
    """Slot-portfolio metrics for a candidate set (used by baseline, filter and
    rank alike so all three are directly comparable)."""
    cands = cands.dropna(subset=["entry_ts", "exit_ts", "net_return"])
    if "pred" not in cands.columns:
        cands = cands.assign(pred=0.0)
    empty = {"n": 0, "n_kept": 0, "n_proposals": n_proposals or len(cands),
             "total_return": None, "max_drawdown": None, "win_rate": None,
             "mean_return": None, "per_trade_sharpe": None, "total_ex_top3": None}
    if cands.empty:
        return empty
    total, max_dd, entered = _portfolio_sim(cands, k, f)
    if not entered:
        return empty
    rets = np.array([e[1] for e in entered])
    if len(entered) > 3:
        top_idx = [e[0] for e in sorted(entered, key=lambda x: -x[1])[:3]]
        ex_total, _, _ = _portfolio_sim(cands.drop(index=top_idx), k, f)
    else:
        ex_total = 0.0
    return {
        "n": len(entered), "n_kept": len(entered),
        "n_proposals": n_proposals if n_proposals is not None else len(cands),
        "total_return": total, "max_drawdown": max_dd,
        "win_rate": float((rets > 0).mean()),
        "mean_return": float(rets.mean()),
        "per_trade_sharpe": float(rets.mean() / rets.std(ddof=1))
        if len(rets) > 1 and rets.std(ddof=1) > 0 else None,
        "total_ex_top3": ex_total,
    }


def _apply_threshold_and_cost(rows, pred, threshold, cost_mult):
    cands = rows.assign(pred=pred)
    cands = cands[cands["pred"] >= threshold]
    if cost_mult != 1.0 and not cands.empty:
        cands = cands.assign(net_return=stress_returns(
            cands["net_return"], cands["n_fills"], cost_mult))
    return cands


def evaluate_rank(rows: pd.DataFrame, pred: np.ndarray, threshold: float,
                  cost_mult: float = 1.0) -> dict:
    """Cross-sectional: the model also picks the DTE — variants of one proposal
    dedupe to the best-scored — then compete for slots."""
    cands = _apply_threshold_and_cost(rows, pred, threshold, cost_mult)
    cands = cands.sort_values("pred", ascending=False) \
        .drop_duplicates(["symbol", "strategy", "trade_idx"])
    return portfolio_metrics(cands, n_proposals=len(rows))


def evaluate_filter(rows: pd.DataFrame, pred: np.ndarray, threshold: float,
                    cost_mult: float = 1.0) -> dict:
    """Frozen-DTE rows kept at score >= threshold, run through the portfolio."""
    cands = _apply_threshold_and_cost(rows, pred, threshold, cost_mult)
    return portfolio_metrics(cands, n_proposals=len(rows))


_EVALUATORS = {"filter": evaluate_filter, "rank": evaluate_rank}


# ── diagnostics / gates / benchmarks ─────────────────────────────────────────

def rank_calibration(rows: pd.DataFrame, pred: np.ndarray,
                     q: int = config.RANK_QUINTILES) -> pd.DataFrame:
    """Score quintile vs realized outcome: was 'best initial choice' actually
    'best performing'? Monotonic mean returns = the ranking is real."""
    d = rows.assign(pred=pred)
    d["bucket"] = pd.qcut(d["pred"].rank(method="first"), q,
                          labels=[f"Q{i + 1}" for i in range(q)])
    out = d.groupby("bucket", observed=True).agg(
        n=("net_return", "size"), mean_score=("pred", "mean"),
        mean_return=("net_return", "mean"),
        win_rate=("net_return", lambda s: (s > 0).mean()))
    return out.round(3)


def passes(m: dict, baseline_return: float, bh_return: float) -> bool:
    return (m["n_kept"] >= config.MIN_KEPT_TRADES
            and m["total_return"] is not None
            and (m["max_drawdown"] or 0) <= config.MAX_DRAWDOWN_CAP
            and m["total_return"] > baseline_return
            and m["total_return"] > bh_return)


def spy_buy_hold(start: str, end: str) -> float:
    bars = load_underlying_15m("SPY").loc[start:end]
    return float(bars["Close"].iloc[-1] / bars["Close"].iloc[0] - 1)


def basket_buy_hold(spec: dict, start: str, end: str) -> float:
    """Equal-weight buy & hold of the SAME names the strategy trades."""
    rets = []
    for sym in spec["symbols"]:
        bars = load_underlying_15m(sym).loc[start:end]
        if len(bars) >= 2:
            rets.append(float(bars["Close"].iloc[-1] / bars["Close"].iloc[0] - 1))
    return float(np.mean(rets)) if rets else 0.0


def fmt(x) -> str:
    return "n/a" if x is None else f"{x:+.1%}"


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    config.ensure_dirs()
    spec = load_spec()
    ds = pd.read_parquet(config.META_DATASET_PARQUET)
    runs = pd.read_csv(config.RUNS_CSV)

    val_all = all_rows(ds, "val")
    test_all = all_rows(ds, "test")
    val_frozen_mask = frozen_mask(val_all, spec)
    test_frozen_mask = frozen_mask(test_all, spec)

    # Baseline = take every frozen-DTE proposal into the SAME slot portfolio
    # (no model), so it is directly comparable to the filtered/ranked NN.
    base_val = portfolio_metrics(val_all[val_frozen_mask])
    base_test = portfolio_metrics(test_all[test_frozen_mask])
    bh_val = basket_buy_hold(spec, config.VAL_START, config.VAL_END)
    bh_test = basket_buy_hold(spec, config.TEST_START, config.TEST_END)
    print(f"baseline (all proposals, frozen DTEs) val: "
          f"{fmt(base_val['total_return'])} ({base_val['n']}) | "
          f"test: {fmt(base_test['total_return'])} ({base_test['n']})")
    print(f"underlying B&H basket ({len(spec['symbols'])} names) "
          f"val: {fmt(bh_val)} | test: {fmt(bh_test)}")

    # ── validation: every run × mode × threshold ─────────────────────────────
    results = []
    for r in runs.itertuples():
        pred_all = predict_rows(r.run_id, val_all)
        for mode in config.EVAL_MODES:
            rows_m = val_all[val_frozen_mask] if mode == "filter" else val_all
            pred_m = pred_all[val_frozen_mask] if mode == "filter" else pred_all
            for thr in config.KEEP_THRESHOLDS:
                m = _EVALUATORS[mode](rows_m, pred_m, thr)
                results.append({
                    "run_id": r.run_id, "arch": r.arch, "lr": r.lr,
                    "label": r.label, "seed": int(r.seed),
                    "mode": mode, "threshold": thr,
                    "val_return": m["total_return"], "n_kept": m["n_kept"],
                    "max_dd": m["max_drawdown"],
                    "passes": passes(m, base_val["total_return"] or -np.inf,
                                     bh_val)})
        best = max((x for x in results if x["run_id"] == r.run_id),
                   key=lambda x: x["val_return"] if x["val_return"] is not None
                   else -np.inf)
        print(f"  val {r.run_id}: best {best['mode']}@{best['threshold']} "
              f"{fmt(best['val_return'])} ({best['n_kept']} kept)"
              f"{' PASS' if best['passes'] else ''}", flush=True)
    vdf = pd.DataFrame(results)
    vdf.to_csv(config.RUNS_DIR / "runs_val.csv", index=False)

    grp = vdf.groupby(["mode", "label", "arch", "lr", "threshold"]).agg(
        median_val_return=("val_return", "median"),
        passing_seeds=("passes", "sum"),
        seeds=("seed", "count")).reset_index()
    grp = grp.sort_values("median_val_return", ascending=False)
    eligible = grp[grp["passing_seeds"] >= config.MIN_PASSING_SEEDS]

    lines = [
        "# NN Meta — Selection Report (v2.1)", "",
        f"Dataset: {len(ds)} rows | {len(spec['symbols'])} symbols × "
        f"{len(config.PROPOSAL_STRATEGIES)} proposal strategies × "
        f"{len(config.DTE_GRID)} DTEs (hash `{spec['config_hash']}`)", "",
        "| baseline | val | test |", "|---|---|---|",
        f"| all frozen-DTE proposals | {fmt(base_val['total_return'])} "
        f"({base_val['n']}) | {fmt(base_test['total_return'])} "
        f"({base_test['n']}) |",
        f"| underlying B&H basket | {fmt(bh_val)} | {fmt(bh_test)} |", "",
        f"Gate: kept >= {config.MIN_KEPT_TRADES}, maxDD <= "
        f"{config.MAX_DRAWDOWN_CAP:.0%}, val return > baseline AND > basket "
        f"B&H; eligible if >= {config.MIN_PASSING_SEEDS}/{len(config.SEEDS)} "
        f"seeds pass. Modes: filter (frozen-DTE, sequential) / rank (top-"
        f"{config.MAX_CONCURRENT} slots @ {config.PORTFOLIO_FRACTION:.0%}, "
        f"cross-ticker, model picks the DTE).", "",
        "## Validation leaderboard (median across seeds)", "",
        grp.head(10).to_markdown(index=False, floatfmt=".3f"), "",
    ]

    if eligible.empty:
        lines += ["**Result: NO eligible config — nothing cleared the gate on "
                  "validation. Test not evaluated.**", ""]
        (config.REPORTS_DIR / "meta_report.md").write_text("\n".join(lines))
        print("\nNO ELIGIBLE CONFIG — report written, test untouched")
        return

    best = eligible.iloc[0]
    win_ids = vdf[(vdf["arch"] == best["arch"]) & (vdf["lr"] == best["lr"])
                  & (vdf["label"] == best["label"])]["run_id"].unique().tolist()
    mode, thr = str(best["mode"]), float(best["threshold"])
    print(f"\nwinner: {best['mode']}/{best['label']}/{best['arch']} "
          f"lr={best['lr']:g} thr={thr} "
          f"(median val {fmt(best['median_val_return'])}, "
          f"{int(best['passing_seeds'])}/{len(config.SEEDS)} pass)")

    final_dir = config.MODEL_FINAL_DIR
    if final_dir.exists():
        shutil.rmtree(final_dir)
    final_dir.mkdir(parents=True)
    for rid in win_ids:
        shutil.copytree(config.RUNS_DIR / rid, final_dir / rid)
    (final_dir / "ensemble_config.json").write_text(json.dumps({
        "run_ids": win_ids, "threshold": thr, "mode": mode,
        "label": str(best["label"]), "features": META_FEATURES,
        "arch": best["arch"], "lr": float(best["lr"]),
        "median_val_return": float(best["median_val_return"]),
        "baseline_config_hash": spec["config_hash"],
    }, indent=2))

    # ── one-shot test ────────────────────────────────────────────────────────
    preds = [predict_rows(rid, test_all) for rid in win_ids]
    ens = np.mean(preds, axis=0)
    rows_m = test_all[test_frozen_mask] if mode == "filter" else test_all
    ens_m = ens[test_frozen_mask] if mode == "filter" else ens
    res_1x = _EVALUATORS[mode](rows_m, ens_m, thr)
    res_2x = _EVALUATORS[mode](rows_m, ens_m, thr,
                               cost_mult=config.COST_STRESS_MULT)
    per_seed = [_EVALUATORS[mode](
        rows_m, (p[test_frozen_mask] if mode == "filter" else p), thr)
        ["total_return"] for p in preds]
    spy_bh = spy_buy_hold(config.TEST_START, config.TEST_END)

    calib = rank_calibration(test_all, ens)
    test_all.assign(pred=ens).to_csv(
        config.REPORTS_DIR / "test_trades_meta.csv", index=False)

    lines += [
        f"## Test (one shot) — mode={mode}, ensemble of {len(win_ids)} seeds, "
        f"thr={thr}", "",
        "| strategy | return | trades | maxDD | win rate | ex-top3 |",
        "|---|---|---|---|---|---|",
        f"| **NN {mode} (1x costs)** | **{fmt(res_1x['total_return'])}** | "
        f"{res_1x['n_kept']}/{res_1x['n_proposals']} | "
        f"{fmt(res_1x['max_drawdown'])} | {fmt(res_1x['win_rate'])} | "
        f"{fmt(res_1x['total_ex_top3'])} |",
        f"| NN {mode} ({config.COST_STRESS_MULT:.0f}x costs) | "
        f"{fmt(res_2x['total_return'])} | {res_2x['n_kept']} | "
        f"{fmt(res_2x['max_drawdown'])} | {fmt(res_2x['win_rate'])} | "
        f"{fmt(res_2x['total_ex_top3'])} |",
        f"| Baseline (all frozen-DTE proposals) | "
        f"{fmt(base_test['total_return'])} | {base_test['n']} | "
        f"{fmt(base_test['max_drawdown'])} | {fmt(base_test['win_rate'])} | "
        f"{fmt(base_test['total_ex_top3'])} |",
        f"| **Underlying B&H basket** | **{fmt(bh_test)}** | — | — | — | — |",
        f"| SPY buy & hold | {fmt(spy_bh)} | — | — | — | — |", "",
        f"Per-seed test return: "
        f"{', '.join(fmt(x) for x in sorted(per_seed, key=lambda v: v if v is not None else -9))}",
        "",
        "## Rank calibration (test, all candidates): score quintile → outcome",
        "", calib.to_markdown(), "",
        "Monotonically increasing mean_return from Q1→Q5 means the model's "
        "ranking is informative — 'best initial choice' really was 'best "
        "performing'.", "",
        "## Caveats", "",
        "- Next-bar fills, no lookahead, identical on every side of the "
        "comparison.",
        f"- All rows (baseline, filter, rank) run through ONE slot portfolio: "
        f"up to {config.MAX_CONCURRENT} concurrent positions, one per symbol, "
        f"at {config.PORTFOLIO_FRACTION:.0%} each (max "
        f"{config.MAX_CONCURRENT * config.PORTFOLIO_FRACTION:.0%} deployed) — "
        f"filter picks the frozen DTE, rank lets the model choose the DTE.",
        f"- Exposure differs vs buy & hold (often flat vs 100% invested) — "
        "B&H rows answer 'worth doing at all?', not 'same-risk alpha'.",
        f"- Costs: {_C1:.2%}/side proxy; {config.COST_STRESS_MULT:.0f}x "
        "stress restated exactly per fill.",
        "- Earnings proximity is proxied by |gap| z-score (no offline "
        "earnings calendar); Sentiment strategy excluded (live news feed).",
    ]
    (config.REPORTS_DIR / "meta_report.md").write_text("\n".join(lines))
    print(f"\nTEST ({mode}): NN {fmt(res_1x['total_return'])} vs baseline "
          f"{fmt(base_test['total_return'])} vs basket B&H {fmt(bh_test)} "
          f"vs SPY {fmt(spy_bh)}")
    print(f"report: {config.REPORTS_DIR / 'meta_report.md'}")


if __name__ == "__main__":
    main()
