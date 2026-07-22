# nn_meta/v4_finalize.py
"""Train and persist the deployable v4 ensemble (Option A).

Tonight's nested walk-forward (v4_evaluate.py --folds 3) validated the v4
causal contract (feature_contract.py's schema, temporal_validation.py's
purged splits + embargo) across three OOS windows — but nested selection
means each fold independently picked its own winning family/mode/threshold
(fold 1: nn/filter/0.55, fold 2: gbt/filter/0.50, fold 3: nn/rank/0.50).
There is no single "the config" to retrain and deploy from that alone.

This script runs ONE more nested-selection pass — same methodology, but on
a window that covers ALL available data as train, with a validation tail
for early-stopping/threshold selection and NO held-out test partition
(this pass isn't measuring OOS performance; the three-fold walk-forward
already did that). Whichever family/mode/threshold wins on that validation
tail gets trained as a full SEEDS-size ensemble and persisted to
model_final_v4/, mirroring the legacy train_meta.py/select_meta.py
persistence pattern (model.keras + scaler.json + params.json per NN seed,
joblib dump per GBT seed) plus a v4 artifact manifest.

Does NOT use v4_accounting.py's mark-to-market ledger — still the shared
select_meta.py portfolio simulator, same as the walk-forward that validated
this methodology tonight. Wiring the ledger in is a separate follow-up
(Option B), not blocking this run.

Run: NN_META_POOL=v31 python -m nn_meta.v4_finalize [--val-fraction 0.15]
     [--seeds 0,1,...,39] [--epochs 60] [--gbt-estimators 600]
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from nn_meta import config
from nn_meta.baseline import load_spec
from nn_meta.build_meta_dataset import META_FEATURES, V4_META_FEATURES
from nn_meta.select_meta import _EVALUATORS, all_rows, frozen_mask
from nn_meta.temporal_validation import assign_purged_splits
from nn_meta.v4_artifacts import create_manifest, write_manifest
from nn_meta.v4_evaluate import choose_policy, fit_gbt, fit_nn, _labeled, _matrix

FINAL_DIR = config.ROOT / "model_final_v4"


def _final_split(ds: pd.DataFrame, val_fraction: float, embargo: str) -> pd.Series:
    """All data as train, most recent tail as val, nothing held out as test —
    this pass exists to pick+train the deployable config, not measure OOS."""
    entry = pd.to_datetime(ds["entry_ts"]).dt.normalize()
    days = entry.dropna().sort_values().unique()
    val_start = days[int(len(days) * (1 - val_fraction))]
    window_end = pd.Timestamp(config.WINDOW_END)
    return assign_purged_splits(
        ds, train_start=config.WINDOW_START, val_start=val_start,
        test_start=window_end, test_end=window_end, embargo=embargo)


def _save_nn_seed(train, val, *, features, label, seed, epochs, run_id) -> dict:
    import tensorflow as tf
    train_l, val_l = _labeled(train, label), _labeled(val, label)
    mean = train_l[features].mean()
    std = train_l[features].std().replace(0, 1.0)
    x_train = _matrix(train_l, features, mean, std)
    x_val = _matrix(val_l, features, mean, std)
    y_train = train_l[label].astype("float32").values
    y_val = val_l[label].astype("float32").values

    tf.keras.utils.set_random_seed(seed)
    from nn_meta.model import build_meta_mlp
    model = build_meta_mlp(len(features), config.ARCHITECTURES[0], config.LEARNING_RATES[0])
    early = tf.keras.callbacks.EarlyStopping(
        monitor="val_loss", patience=max(3, min(12, epochs // 4)),
        restore_best_weights=True)
    hist = model.fit(x_train, y_train, validation_data=(x_val, y_val),
                     epochs=epochs, batch_size=config.BATCH_SIZE,
                     callbacks=[early], verbose=0)

    run_dir = FINAL_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    model.save(run_dir / "model.keras")
    (run_dir / "scaler.json").write_text(json.dumps(
        {"mean": mean.to_dict(), "std": std.to_dict()}))
    (run_dir / "params.json").write_text(json.dumps(
        {"family": "nn", "seed": seed, "label": label, "features": features,
         "arch": config.ARCHITECTURES[0], "lr": config.LEARNING_RATES[0]}))
    return {"run_id": run_id, "val_loss": float(min(hist.history["val_loss"]))}


def _save_gbt_seed(train, val, *, features, label, seed, n_estimators, run_id) -> dict:
    from lightgbm import LGBMClassifier, early_stopping, log_evaluation
    train_l, val_l = _labeled(train, label), _labeled(val, label)
    model = LGBMClassifier(
        n_estimators=n_estimators, learning_rate=0.02, num_leaves=31,
        subsample=0.8, colsample_bytree=0.8, min_child_samples=200,
        reg_lambda=1.0, random_state=seed, n_jobs=-1, verbosity=-1)
    model.fit(train_l[features], train_l[label].astype(int),
             eval_set=[(val_l[features], val_l[label].astype(int))],
             eval_metric="auc",
             callbacks=[early_stopping(max(10, n_estimators // 10)), log_evaluation(0)])

    run_dir = FINAL_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, run_dir / "model.joblib")
    (run_dir / "params.json").write_text(json.dumps(
        {"family": "gbt", "seed": seed, "label": label, "features": features,
         "n_estimators": n_estimators}))
    return {"run_id": run_id}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--val-fraction", type=float, default=0.15)
    ap.add_argument("--embargo", default="1D")
    ap.add_argument("--label", default="label_excess", choices=["label", "label_excess"])
    ap.add_argument("--models", default="nn,gbt")
    ap.add_argument("--select-seeds", default="0,1,2,3,4",
                    help="seeds used only to PICK the winning config")
    ap.add_argument("--final-seeds", default=None,
                    help="seeds for the persisted ensemble (default: config.SEEDS, 40)")
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--gbt-estimators", type=int, default=600)
    args = ap.parse_args()

    select_seeds = [int(s) for s in args.select_seeds.split(",") if s.strip()]
    final_seeds = ([int(s) for s in args.final_seeds.split(",")] if args.final_seeds
                   else list(config.SEEDS))
    models = [m.strip() for m in args.models.split(",") if m.strip()]

    print(f"loading dataset + spec...", flush=True)
    ds = pd.read_parquet(config.META_DATASET_PARQUET)
    spec = load_spec()
    split = _final_split(ds, args.val_fraction, args.embargo)
    d = ds.copy()
    d["split"] = split
    features = V4_META_FEATURES
    print(f"split sizes: {split.value_counts().to_dict()}", flush=True)

    train = d[d["split"] == "train"]
    val_rows = all_rows(d, "val").reset_index(drop=True)
    if train.empty or val_rows.empty:
        raise SystemExit("empty train or val partition — check --val-fraction/--embargo")

    # ── 1) pick the winning family/mode/threshold on validation (cheap seeds) ──
    print(f"\n=== selecting config (seeds={select_seeds}) ===", flush=True)
    candidates = []
    for family in models:
        t0 = time.time()
        if family == "nn":
            predictor = fit_nn(train, d[d["split"] == "val"], features=features,
                              label=args.label, seed=select_seeds[0], epochs=args.epochs)
            preds = [predictor.predict(val_rows)]
            for s in select_seeds[1:]:
                p = fit_nn(train, d[d["split"] == "val"], features=features,
                          label=args.label, seed=s, epochs=args.epochs)
                preds.append(p.predict(val_rows))
            pred = np.mean(preds, axis=0)
        else:
            predictor = fit_gbt(train, d[d["split"] == "val"], features=features,
                               label=args.label, n_estimators=args.gbt_estimators)
            pred = predictor.predict(val_rows)
        policy = choose_policy(val_rows, pred, spec)
        policy["family"] = family
        candidates.append(policy)
        ret = policy["metrics"]["total_return"]
        print(f"  {family}: best {policy['mode']}@{policy['threshold']} "
              f"val_return={ret} ({time.time()-t0:.0f}s)", flush=True)

    winner = max(candidates, key=lambda c: c["metrics"]["total_return"]
                if c["metrics"]["total_return"] is not None else -np.inf)
    family, mode, threshold = winner["family"], winner["mode"], winner["threshold"]
    print(f"\nWINNER: {family} / {mode} / thr={threshold} "
          f"(val_return={winner['metrics']['total_return']})", flush=True)

    # ── 2) train + persist the full ensemble for the winning family ─────────
    if FINAL_DIR.exists():
        shutil.rmtree(FINAL_DIR)
    FINAL_DIR.mkdir(parents=True)

    print(f"\n=== training final {family} ensemble, {len(final_seeds)} seeds ===",
          flush=True)
    run_ids = []
    val_split_df = d[d["split"] == "val"]
    for seed in final_seeds:
        t0 = time.time()
        lab_tag = "win" if args.label == "label" else "xs"
        run_id = f"v4-{family}-{lab_tag}-s{seed}"
        if family == "nn":
            info = _save_nn_seed(train, val_split_df, features=features,
                                 label=args.label, seed=seed, epochs=args.epochs,
                                 run_id=run_id)
        else:
            info = _save_gbt_seed(train, val_split_df, features=features,
                                  label=args.label, seed=seed,
                                  n_estimators=args.gbt_estimators, run_id=run_id)
        run_ids.append(run_id)
        print(f"  seed {seed}: saved {run_id} ({time.time()-t0:.0f}s)", flush=True)

    (FINAL_DIR / "ensemble_config.json").write_text(json.dumps({
        "run_ids": run_ids, "family": family, "mode": mode, "threshold": threshold,
        "label": args.label, "features": features,
        "val_return": winner["metrics"]["total_return"],
        "baseline_config_hash": spec["config_hash"],
        "schema": "v4", "purged": True, "embargo": args.embargo,
    }, indent=2))

    manifest = create_manifest(
        dataset_path=config.META_DATASET_PARQUET,
        baseline_spec_path=config.BASELINE_SPEC_JSON,
        feature_names=features,
        provider_metadata={"pool": config.POOL, "interval": config.INTERVAL,
                           "options_history_constraint": "15m; approximately two years"},
        code_root=config.ROOT.parent)
    write_manifest(manifest, FINAL_DIR / "manifest.json")

    print(f"\nDONE. {family}/{mode}/thr={threshold}, {len(run_ids)} seeds -> {FINAL_DIR}")


if __name__ == "__main__":
    main()
