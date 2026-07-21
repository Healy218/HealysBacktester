"""Nested, purged V4 evaluation and v31 ablation runner.

This is intentionally parallel to the legacy training/select/walk-forward
commands.  It can evaluate a completed v31 ``meta_dataset.parquet`` without
changing the running v31 pipeline, while enforcing the v4 feature contract and
using one portfolio simulator for NN and LightGBM.

Examples:

    NN_META_POOL=v31 python -m nn_meta.v4_evaluate --ablation
    NN_META_POOL=v31 python -m nn_meta.v4_evaluate --folds 3 --seeds 0,1,2,3,4
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
import pandas as pd

from nn_meta import config
from nn_meta.baseline import load_spec
from nn_meta.build_meta_dataset import META_FEATURES, V4_META_FEATURES
from nn_meta.calibration import calibration_summary
from nn_meta.diagnostics import decile_diagnostic
from nn_meta.feature_contract import assert_decision_safe
from nn_meta.mark_stream import execution_frames, load_mark_stream
from nn_meta.model import build_meta_mlp
from nn_meta.multiple_testing import deflated_sharpe_from_trials
from nn_meta.select_meta import (_EVALUATORS, _portfolio_sim, all_rows,
                                 frozen_mask, portfolio_metrics)
from nn_meta.temporal_validation import (FoldWindow, assign_purged_splits,
                                         expanding_folds, split_summary)
from nn_meta.v4_accounting import (BASE_COSTS, CostScenario,
                                   mark_to_market_portfolio)
from nn_meta.v4_artifacts import (create_manifest, write_manifest,
                                  write_metadata_bundle)


@dataclass
class Predictor:
    family: str
    predict: Callable[[pd.DataFrame], np.ndarray]


def schema_features(schema: str) -> list[str]:
    """Return the requested persisted schema and verify its timing contract."""
    if schema == "v4":
        assert_decision_safe(V4_META_FEATURES)
        return V4_META_FEATURES
    if schema == "legacy":
        return META_FEATURES
    raise ValueError("schema must be 'legacy' or 'v4'")


def legacy_splits(rows: pd.DataFrame, window: FoldWindow) -> pd.Series:
    """Historical entry-only assignment, retained only for ablation controls."""
    entry = pd.to_datetime(rows["entry_ts"]).dt.normalize()
    split = pd.Series("purged", index=rows.index, dtype="object")
    split.loc[(entry >= window.train_start) & (entry < window.val_start)] = "train"
    split.loc[(entry >= window.val_start) & (entry < window.test_start)] = "val"
    split.loc[(entry >= window.test_start) & (entry <= window.test_end)] = "test"
    return split


def _matrix(rows: pd.DataFrame, features: list[str], mean: pd.Series,
            std: pd.Series) -> np.ndarray:
    values = rows[features].copy().fillna(mean)
    return ((values - mean) / std).values.astype("float32")


def _labeled(rows: pd.DataFrame, label: str) -> pd.DataFrame:
    return rows[rows[label].notna()].copy()


def fit_nn(train: pd.DataFrame, val: pd.DataFrame, *, features: list[str],
           label: str, seed: int, epochs: int) -> Predictor:
    """Fit one fold-local MLP; no artifacts are written during an ablation."""
    import tensorflow as tf

    train, val = _labeled(train, label), _labeled(val, label)
    if train.empty or val.empty:
        raise ValueError("NN requires non-empty labeled train and validation rows")
    mean = train[features].mean()
    std = train[features].std().replace(0, 1.0)
    x_train, x_val = _matrix(train, features, mean, std), _matrix(val, features, mean, std)
    y_train, y_val = train[label].astype("float32").values, val[label].astype("float32").values
    tf.keras.utils.set_random_seed(seed)
    model = build_meta_mlp(len(features), config.ARCHITECTURES[0], config.LEARNING_RATES[0])
    early = tf.keras.callbacks.EarlyStopping(
        monitor="val_loss", patience=max(3, min(12, epochs // 4)),
        restore_best_weights=True,
    )
    model.fit(x_train, y_train, validation_data=(x_val, y_val),
              epochs=epochs, batch_size=config.BATCH_SIZE, callbacks=[early], verbose=0)

    def predict(rows: pd.DataFrame) -> np.ndarray:
        return model.predict(_matrix(rows, features, mean, std), batch_size=4096,
                             verbose=0).flatten()

    return Predictor("nn", predict)


def fit_gbt(train: pd.DataFrame, val: pd.DataFrame, *, features: list[str],
            label: str, n_estimators: int) -> Predictor:
    """Fit the tree baseline with the same fold-local labels and features."""
    try:
        from lightgbm import LGBMClassifier, early_stopping, log_evaluation
    except ImportError as exc:
        raise RuntimeError("LightGBM is required for --models gbt; install requirements.txt") from exc

    train, val = _labeled(train, label), _labeled(val, label)
    if train.empty or val.empty:
        raise ValueError("GBT requires non-empty labeled train and validation rows")
    model = LGBMClassifier(
        n_estimators=n_estimators, learning_rate=0.02, num_leaves=31,
        subsample=0.8, colsample_bytree=0.8, min_child_samples=200,
        reg_lambda=1.0, random_state=0, n_jobs=-1, verbosity=-1,
    )
    model.fit(train[features], train[label].astype(int),
              eval_set=[(val[features], val[label].astype(int))], eval_metric="auc",
              callbacks=[early_stopping(max(10, n_estimators // 10)), log_evaluation(0)])
    return Predictor("gbt", lambda rows: model.predict_proba(rows[features])[:, 1])


def fit_family(family: str, train: pd.DataFrame, val: pd.DataFrame, *,
               features: list[str], label: str, seeds: Iterable[int],
               epochs: int, gbt_estimators: int) -> Predictor:
    """Return a fold-local predictor; NN seeds are averaged before policy selection."""
    if family == "gbt":
        return fit_gbt(train, val, features=features, label=label,
                       n_estimators=gbt_estimators)
    if family != "nn":
        raise ValueError(f"unknown model family '{family}'")
    models = [fit_nn(train, val, features=features, label=label, seed=seed,
                     epochs=epochs) for seed in seeds]
    if not models:
        raise ValueError("NN requires at least one seed")
    return Predictor("nn", lambda rows: np.mean([m.predict(rows) for m in models], axis=0))


def choose_policy(rows: pd.DataFrame, predictions: np.ndarray, spec: dict,
                  thresholds: Iterable[float] = config.KEEP_THRESHOLDS) -> dict:
    """Choose mode and threshold on validation only, using shared portfolio logic."""
    if len(rows) != len(predictions):
        raise ValueError("row/prediction length mismatch")
    fmask = frozen_mask(rows, spec)
    baseline = portfolio_metrics(rows[fmask])
    candidates = []
    for mode in config.EVAL_MODES:
        eval_rows = rows[fmask].reset_index(drop=True) if mode == "filter" else rows.reset_index(drop=True)
        eval_pred = predictions[fmask] if mode == "filter" else predictions
        for threshold in thresholds:
            metrics = _EVALUATORS[mode](eval_rows, eval_pred, float(threshold))
            candidates.append({
                "mode": mode,
                "threshold": float(threshold),
                "metrics": metrics,
                "baseline_return": baseline["total_return"],
                "eligible": (
                    metrics["n_kept"] >= config.MIN_KEPT_TRADES
                    and metrics["total_return"] is not None
                    and (
                        baseline["total_return"] is None
                        or metrics["total_return"] > baseline["total_return"]
                    )
                    and (metrics["max_drawdown"] or 0) <= config.MAX_DRAWDOWN_CAP
                ),
            })
    eligible = [c for c in candidates if c["eligible"]]
    pool = eligible or candidates
    winner = max(pool, key=lambda c: c["metrics"]["total_return"]
                 if c["metrics"]["total_return"] is not None else -np.inf)
    # Every candidate is a "trial"; its Sharpe feeds the deflation later.
    winner["candidate_sharpes"] = [c["metrics"]["per_trade_sharpe"] for c in candidates]
    return winner


def _candidate_rows(rows: pd.DataFrame, pred: np.ndarray, mode: str,
                    threshold: float) -> pd.DataFrame:
    """Thresholded (and, for rank, DTE-deduped) candidate pool for one policy,
    matching the shared filter/rank evaluators."""
    cands = rows.assign(pred=pred)
    cands = cands[cands["pred"] >= threshold]
    if mode == "rank":
        cands = cands.sort_values("pred", ascending=False) \
            .drop_duplicates(["symbol", "strategy", "trade_idx"])
    return cands


def _selected_rows(cands: pd.DataFrame) -> pd.DataFrame:
    """Rows the shared slot portfolio actually enters (its own slot decision)."""
    cands = cands.dropna(subset=["entry_ts", "exit_ts", "net_return"])
    if cands.empty:
        return cands
    _, _, entered = _portfolio_sim(cands, config.MAX_CONCURRENT,
                                   config.PORTFOLIO_FRACTION)
    return cands.loc[[e[0] for e in entered]]


def marked_metrics(rows: pd.DataFrame, pred: np.ndarray, mode: str,
                   threshold: float, mark_stream: pd.DataFrame, *,
                   costs: CostScenario = BASE_COSTS) -> dict | None:
    """Mark-to-market metrics for the trades this policy enters.

    The shared slot portfolio makes the entry/exit decisions (skip semantics);
    only those entered trades and their observed marks are then routed through
    the fail-closed ledger, which re-derives drawdown and exposure from the
    per-contract mark path rather than the final ``net_return``.  Returns
    ``None`` when the portfolio enters nothing.
    """
    selected = _selected_rows(_candidate_rows(rows, pred, mode, threshold))
    if selected.empty:
        return None
    trades, marks = execution_frames(selected, mark_stream)
    metrics, _ = mark_to_market_portfolio(
        trades, marks, max_concurrent=config.MAX_CONCURRENT,
        position_fraction=config.PORTFOLIO_FRACTION, costs=costs)
    return metrics


def _rows_for_split(ds: pd.DataFrame, split: str) -> pd.DataFrame:
    return all_rows(ds, split).reset_index(drop=True)


def evaluate_window(ds: pd.DataFrame, window: FoldWindow, *, spec: dict,
                    schema: str, purged: bool, label: str,
                    models: Iterable[str], seeds: Iterable[int], epochs: int,
                    gbt_estimators: int, embargo: str,
                    mark_stream: pd.DataFrame | None = None) -> dict:
    """Nested temporal evaluation for one fold or global ablation window."""
    ds = ds.copy()
    split = assign_purged_splits(
        ds, train_start=window.train_start, val_start=window.val_start,
        test_start=window.test_start, test_end=window.test_end, embargo=embargo,
    ) if purged else legacy_splits(ds, window)
    ds["split"] = split
    features = schema_features(schema)
    missing = set(features) - set(ds.columns)
    if missing:
        raise ValueError(f"dataset missing model features: {sorted(missing)}")
    train = ds[ds["split"] == "train"]
    val_rows, test_rows = _rows_for_split(ds, "val"), _rows_for_split(ds, "test")
    if train.empty or val_rows.empty or test_rows.empty:
        raise ValueError("purging left an empty train, validation, or test partition")

    fitted: dict[str, Predictor] = {}
    selected: list[dict] = []
    for family in models:
        predictor = fit_family(family, train, ds[ds["split"] == "val"],
                               features=features, label=label, seeds=seeds,
                               epochs=epochs, gbt_estimators=gbt_estimators)
        policy = choose_policy(val_rows, predictor.predict(val_rows), spec)
        policy["family"] = family
        fitted[family] = predictor
        selected.append(policy)

    winner = max(selected, key=lambda p: p["metrics"]["total_return"]
                 if p["metrics"]["total_return"] is not None else -np.inf)
    family = winner["family"]
    test_pred = fitted[family].predict(test_rows)
    # Calibration is fit on the winner's validation predictions only, then
    # scored on test — the test labels never inform the mapping.
    calibration = calibration_summary(
        val_rows[label], fitted[family].predict(val_rows),
        test_rows[label], test_pred, method="isotonic")
    fmask = frozen_mask(test_rows, spec)
    test_eval_rows = test_rows[fmask].reset_index(drop=True) if winner["mode"] == "filter" else test_rows
    test_eval_pred = test_pred[fmask] if winner["mode"] == "filter" else test_pred
    winner_test = _EVALUATORS[winner["mode"]](test_eval_rows, test_eval_pred,
                                                winner["threshold"])
    winner_marked = (marked_metrics(test_eval_rows, test_eval_pred,
                                    winner["mode"], winner["threshold"], mark_stream)
                     if mark_stream is not None else None)
    # Deflate the winner's test Sharpe by the whole grid of tried configurations.
    trial_sharpes = [s for p in selected for s in p.get("candidate_sharpes", [])]
    entered_test = _selected_rows(_candidate_rows(
        test_eval_rows, test_eval_pred, winner["mode"], winner["threshold"]))
    deflated = deflated_sharpe_from_trials(
        entered_test["net_return"] if len(entered_test) else [], trial_sharpes)
    # Track the v3.1 top-decile inversion (win rate up, mean return down) on
    # the full test candidate pool for the winning family.
    score_deciles = decile_diagnostic(test_pred, test_rows["net_return"])

    by_model = {}
    for policy in selected:
        family = policy["family"]
        pred = fitted[family].predict(test_rows)
        frows = test_rows[fmask].reset_index(drop=True) if policy["mode"] == "filter" else test_rows
        fpred = pred[fmask] if policy["mode"] == "filter" else pred
        by_model[family] = {
            "mode": policy["mode"], "threshold": policy["threshold"],
            "validation": policy["metrics"],
            "test": _EVALUATORS[policy["mode"]](frows, fpred, policy["threshold"]),
        }
    return {
        "schema": schema, "purged": purged, "embargo": embargo,
        "window": {k: str(v.date()) for k, v in window.__dict__.items()},
        "split_summary": split_summary(ds, split).to_dict(orient="records"),
        "winner": {"family": winner["family"], "mode": winner["mode"],
                   "threshold": winner["threshold"], "validation": winner["metrics"],
                   "test": winner_test, "marked": winner_marked,
                   "calibration": calibration, "deflated_sharpe": deflated,
                   "score_deciles": score_deciles},
        "models": by_model,
    }


def _json_default(value):
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    raise TypeError(type(value).__name__)


def _window_from_config() -> FoldWindow:
    return FoldWindow(
        train_start=pd.Timestamp(config.TRAIN_START),
        val_start=pd.Timestamp(config.VAL_START),
        test_start=pd.Timestamp(config.TEST_START),
        test_end=pd.Timestamp(config.TEST_END),
    )


def _write_report(results: list[dict], output: Path) -> None:
    lines = ["# V4 causal evaluation", "",
             "Each row uses fold-local model/policy selection and the shared slot portfolio.",
             "The marked column is the mark-to-market ledger result and is `pending` "
             "until a per-contract mark stream is supplied via `--marks`.", "",
             "| run | schema | purged | winner | mode / threshold | test return | maxDD | marked return / maxDD |",
             "|---|---|---|---|---|---|---|---|"]
    for i, result in enumerate(results, 1):
        win, test = result["winner"], result["winner"]["test"]
        ret = test["total_return"]
        dd = test["max_drawdown"]
        marked = win.get("marked")
        if marked is None:
            marked_cell = "pending"
        else:
            marked_cell = f"{marked['total_return']:+.1%} / {marked['max_drawdown']:.1%}"
        lines.append(
            f"| {i} | {result['schema']} | {result['purged']} | {win['family']} | "
            f"{win['mode']} / {win['threshold']:.2f} | "
            f"{'n/a' if ret is None else f'{ret:+.1%}'} | "
            f"{'n/a' if dd is None else f'{dd:.1%}'} | {marked_cell} |"
        )
    cal_rows = [(i, r["winner"]["calibration"]) for i, r in enumerate(results, 1)
                if r["winner"].get("calibration")]
    if cal_rows:
        lines += ["", "## Calibration (winner, test — fit on validation only)", "",
                  "| run | method | Brier raw | Brier calibrated |",
                  "|---|---|---|---|"]
        for i, cal in cal_rows:
            lines.append(f"| {i} | {cal['method']} | {cal['brier_raw']:.4f} | "
                         f"{cal['brier_calibrated']:.4f} |")
    dsr_rows = [(i, r["winner"]["deflated_sharpe"]) for i, r in enumerate(results, 1)
                if r["winner"].get("deflated_sharpe")]
    if dsr_rows:
        lines += ["", "## Deflated Sharpe (winner, test — deflated by the policy grid)", "",
                  "| run | Sharpe | trials | E[max Sharpe] | deflated Sharpe |",
                  "|---|---|---|---|---|"]
        for i, d in dsr_rows:
            lines.append(f"| {i} | {d['sharpe']:.3f} | {d['n_trials']} | "
                         f"{d['expected_max_sharpe']:.3f} | {d['deflated_sharpe']:.3f} |")
    for i, result in enumerate(results, 1):
        diag = result["winner"].get("score_deciles")
        if not diag:
            continue
        flag = " ⚠ top-decile inversion" if diag["inverted"] else ""
        lines += ["", f"## Score deciles (run {i}, winner test){flag}", "",
                  "| decile | n | mean score | win rate | mean return |",
                  "|---|---|---|---|---|"]
        for d in diag["deciles"]:
            lines.append(f"| {d['decile']} | {d['n']} | {d['mean_score']:.3f} | "
                         f"{d['win_rate']:.3f} | {d['mean_return']:+.4f} |")
    output.write_text("\n".join(lines) + "\n")
    output.with_suffix(".json").write_text(json.dumps(results, indent=2, default=_json_default))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=config.META_DATASET_PARQUET)
    ap.add_argument("--label", default="label_excess", choices=["label", "label_excess"])
    ap.add_argument("--models", default="nn,gbt", help="comma-separated: nn,gbt")
    ap.add_argument("--seeds", default="0,1,2,3,4", help="NN ensemble seeds")
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--gbt-estimators", type=int, default=600)
    ap.add_argument("--embargo", default="1D")
    ap.add_argument("--folds", type=int, default=0, help="expanding nested folds")
    ap.add_argument("--marks", type=Path, default=None,
                    help="per-contract 15m mark stream; enables mark-to-market "
                         "accounting of the winning policy's trades")
    ap.add_argument("--ablation", action="store_true",
                    help="run legacy/v4 schemas with and without exit-time purging")
    ap.add_argument("--output", type=Path, default=None)
    ap.add_argument("--manifest", type=Path, default=None,
                    help="write a verifiable input manifest next to the report")
    ap.add_argument("--metadata-bundle", type=Path, default=None,
                    help="optional portable zip of manifest, baseline spec, and reports")
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    if args.folds and args.ablation:
        raise SystemExit("choose either --folds or --ablation")
    if args.smoke:
        args.seeds, args.epochs, args.gbt_estimators = "0", 5, 50

    ds = pd.read_parquet(args.dataset)
    spec = load_spec()
    mark_stream = load_mark_stream(args.marks) if args.marks else None
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    seeds = [int(seed) for seed in args.seeds.split(",") if seed.strip()]
    output = args.output or config.REPORTS_DIR / (
        "v4_ablation_report.md" if args.ablation else "v4_walkforward_report.md")
    output.parent.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []

    if args.ablation:
        window = _window_from_config()
        for schema, purged in (("legacy", False), ("v4", False),
                               ("legacy", True), ("v4", True)):
            print(f"running schema={schema} purged={purged}", flush=True)
            results.append(evaluate_window(
                ds, window, spec=spec, schema=schema, purged=purged,
                label=args.label, models=models, seeds=seeds, epochs=args.epochs,
                gbt_estimators=args.gbt_estimators, embargo=args.embargo,
                mark_stream=mark_stream,
            ))
    else:
        folds = expanding_folds(ds["entry_ts"], n_folds=args.folds or 3)
        for i, window in enumerate(folds, 1):
            print(f"running nested fold {i}/{len(folds)}", flush=True)
            results.append(evaluate_window(
                ds, window, spec=spec, schema="v4", purged=True,
                label=args.label, models=models, seeds=seeds, epochs=args.epochs,
                gbt_estimators=args.gbt_estimators, embargo=args.embargo,
                mark_stream=mark_stream,
            ))
    _write_report(results, output)
    manifest_path = args.manifest or output.with_suffix(".manifest.json")
    manifest = create_manifest(
        dataset_path=args.dataset, baseline_spec_path=config.BASELINE_SPEC_JSON,
        feature_names=schema_features("v4" if not args.ablation else "legacy"),
        provider_metadata={"pool": config.POOL, "interval": config.INTERVAL,
                           "options_history_constraint": "15m; approximately two years"},
        code_root=config.ROOT.parent,
    )
    write_manifest(manifest, manifest_path)
    if args.metadata_bundle:
        write_metadata_bundle(args.metadata_bundle, manifest_path=manifest_path,
                              baseline_spec_path=config.BASELINE_SPEC_JSON,
                              reports=[output, output.with_suffix(".json")])
    print(f"wrote {output}, {output.with_suffix('.json')}, and {manifest_path}")


if __name__ == "__main__":
    main()
