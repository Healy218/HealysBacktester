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
from nn_meta.feature_contract import assert_decision_safe
from nn_meta.model import build_meta_mlp
from nn_meta.select_meta import (_EVALUATORS, all_rows, frozen_mask,
                                 portfolio_metrics)
from nn_meta.temporal_validation import (FoldWindow, assign_purged_splits,
                                         expanding_folds, split_summary)


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
    return max(pool, key=lambda c: c["metrics"]["total_return"]
               if c["metrics"]["total_return"] is not None else -np.inf)


def _rows_for_split(ds: pd.DataFrame, split: str) -> pd.DataFrame:
    return all_rows(ds, split).reset_index(drop=True)


def evaluate_window(ds: pd.DataFrame, window: FoldWindow, *, spec: dict,
                    schema: str, purged: bool, label: str,
                    models: Iterable[str], seeds: Iterable[int], epochs: int,
                    gbt_estimators: int, embargo: str) -> dict:
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
    fmask = frozen_mask(test_rows, spec)
    test_eval_rows = test_rows[fmask].reset_index(drop=True) if winner["mode"] == "filter" else test_rows
    test_eval_pred = test_pred[fmask] if winner["mode"] == "filter" else test_pred
    winner_test = _EVALUATORS[winner["mode"]](test_eval_rows, test_eval_pred,
                                                winner["threshold"])

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
                   "test": winner_test},
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
             "Each row uses fold-local model/policy selection and the shared slot portfolio.", "",
             "| run | schema | purged | winner | mode / threshold | test return | maxDD |", "|---|---|---|---|---|---|---|"]
    for i, result in enumerate(results, 1):
        win, test = result["winner"], result["winner"]["test"]
        ret = test["total_return"]
        dd = test["max_drawdown"]
        lines.append(
            f"| {i} | {result['schema']} | {result['purged']} | {win['family']} | "
            f"{win['mode']} / {win['threshold']:.2f} | "
            f"{'n/a' if ret is None else f'{ret:+.1%}'} | "
            f"{'n/a' if dd is None else f'{dd:.1%}'} |"
        )
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
    ap.add_argument("--ablation", action="store_true",
                    help="run legacy/v4 schemas with and without exit-time purging")
    ap.add_argument("--output", type=Path, default=None)
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    if args.folds and args.ablation:
        raise SystemExit("choose either --folds or --ablation")
    if args.smoke:
        args.seeds, args.epochs, args.gbt_estimators = "0", 5, 50

    ds = pd.read_parquet(args.dataset)
    spec = load_spec()
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
            ))
    else:
        folds = expanding_folds(ds["entry_ts"], n_folds=args.folds or 3)
        for i, window in enumerate(folds, 1):
            print(f"running nested fold {i}/{len(folds)}", flush=True)
            results.append(evaluate_window(
                ds, window, spec=spec, schema="v4", purged=True,
                label=args.label, models=models, seeds=seeds, epochs=args.epochs,
                gbt_estimators=args.gbt_estimators, embargo=args.embargo,
            ))
    _write_report(results, output)
    print(f"wrote {output} and {output.with_suffix('.json')}")


if __name__ == "__main__":
    main()
