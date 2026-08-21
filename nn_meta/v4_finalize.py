# nn_meta/v4_finalize.py
"""Train and persist the deployable v4 ensemble (Option A).

Tonight's nested walk-forward (v4_evaluate.py --folds 3) validated the v4
causal contract (feature_contract.py's schema, temporal_validation.py's
purged splits + embargo) across three OOS windows — but nested selection
means each fold independently picked its own winning family/mode/threshold
(fold 1: nn/filter/0.55, fold 2: gbt/filter/0.50, fold 3: nn/rank/0.50).
There is no single "the config" to retrain and deploy from that alone.

This script runs ONE more selection pass — same methodology, but on a window
that covers ALL available data as train, with a validation tail for
early-stopping/threshold selection and NO held-out test partition (this pass
isn't measuring OOS performance; the three-fold walk-forward already did
that). The pass is two-stage to avoid deploying an operating point tuned on a
model that isn't the one that ships:

  1. FAMILY selection on cheap seeds (5-seed NN mean / 1 GBT) picks nn vs gbt.
  2. The full SEEDS-size ensemble of that family is trained, then the
     mode/threshold is RE-CHOSEN on the ensemble's own validation scores
     (whose distribution differs from the cheap-seed proxy), and the bundle
     is persisted only if that ensemble clears the eligibility gate.

Persistence mirrors the legacy train_meta.py/select_meta.py layout
(model.keras + scaler.json + params.json per NN seed, joblib per GBT seed)
plus an ensemble_config.json (the ensemble's own operating point + metrics)
and a v4 artifact manifest that hashes the trained files, not just the
inputs. Training goes into a .staging sibling and is atomically swapped in
last, so a crash or a gate failure never destroys a previously-validated
model_final_v4/.

With ``--marks`` (Option B) both selection passes — the cheap-seed family
pick and the full-ensemble operating point — run through the mark-to-market
ledger via ``choose_policy(mark_stream=...)``, exactly like
``v4_evaluate --marks``. Without it, the legacy shared-simulator path is
bit-identical to before.

Run: NN_META_POOL=v31 python -m nn_meta.v4_finalize [--val-fraction 0.15]
     [--select-seeds 0,1,2,3,4] [--final-seeds ...] [--epochs 60]
     [--gbt-estimators 600] [--marks .../meta_dataset.marks.parquet]
Exit status: 0 on a persisted bundle, 1 if nothing cleared the gate.
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
from nn_meta.build_meta_dataset import V4_META_FEATURES
from nn_meta.mark_stream import load_mark_stream, option_b_blockers
from nn_meta.select_meta import all_rows
from nn_meta.temporal_validation import assign_purged_splits
from nn_meta.v4_artifacts import create_manifest, write_manifest
from nn_meta.v4_evaluate import (choose_policy, policy_label, fit_gbt, fit_gbt_magnitude, fit_nn,
                                 fit_nn_magnitude, _labeled, _matrix, _select_winner)
from nn_meta.v4_loader import ensemble_ev, ensemble_score

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


def _train_nn_seed(train, val, *, features, label, seed, epochs, run_id,
                   out_dir: Path) -> tuple[dict, dict]:
    """Train + persist one NN seed and return (info, member). ``member`` keeps
    the fitted model and its scaler so the caller can score the val tail with
    the ACTUAL persisted ensemble before locking the operating point."""
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

    # Magnitude head (EV sizing): same scaler, signed-return target.
    mag = fit_nn_magnitude(train, val, features=features, mean=mean, std=std,
                           seed=seed, epochs=epochs)

    run_dir = out_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    model.save(run_dir / "model.keras")
    mag.model.save(run_dir / "magnitude.keras")
    (run_dir / "scaler.json").write_text(json.dumps(
        {"mean": mean.to_dict(), "std": std.to_dict()}))
    (run_dir / "params.json").write_text(json.dumps(
        {"family": "nn", "seed": seed, "label": label, "features": features,
         "arch": config.ARCHITECTURES[0], "lr": config.LEARNING_RATES[0],
         "magnitude_head": {"target": "net_return", "loss": "huber",
                            "winsor_bounds": list(mag.bounds)}}))
    info = {"run_id": run_id, "val_loss": float(min(hist.history["val_loss"])),
            "files": ["model.keras", "magnitude.keras", "scaler.json", "params.json"]}
    return info, {"model": model, "magnitude": mag.model, "mean": mean, "std": std}


def _train_gbt_seed(train, val, *, features, label, seed, n_estimators, run_id,
                    out_dir: Path) -> tuple[dict, dict]:
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

    mag = fit_gbt_magnitude(train, val, features=features, n_estimators=n_estimators,
                            seed=seed)

    run_dir = out_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, run_dir / "model.joblib")
    joblib.dump(mag.model, run_dir / "magnitude.joblib")
    (run_dir / "params.json").write_text(json.dumps(
        {"family": "gbt", "seed": seed, "label": label, "features": features,
         "n_estimators": n_estimators,
         "magnitude_head": {"target": "net_return", "objective": "huber",
                            "winsor_bounds": list(mag.bounds)}}))
    return ({"run_id": run_id, "files": ["model.joblib", "magnitude.joblib", "params.json"]},
            {"model": model, "magnitude": mag.model})


def _ensemble_predict(family: str, members: list[dict], rows: pd.DataFrame,
                      features: list[str]) -> np.ndarray:
    """Mean P(win) across the just-trained ensemble members — the exact score
    the deployed bundle produces. Delegates to the shared ``ensemble_score`` so
    the training-time and load-time scoring paths can never diverge."""
    return ensemble_score(family, members, rows, features)


def _ensemble_ev(family: str, members: list[dict], rows: pd.DataFrame,
                 features: list[str]) -> np.ndarray | None:
    """Mean predicted expected return across the magnitude heads, or ``None``
    when the members carry none (the ``ev`` mode then stays out of the grid)."""
    if not members or any("magnitude" not in m or m["magnitude"] is None for m in members):
        return None
    return ensemble_ev(family, members, rows, features)


def _atomic_swap(staging: Path, final: Path) -> None:
    """Replace ``final`` with ``staging`` via renames only, so a crash never
    leaves the deployable bundle half-written: the previous bundle survives
    until the new one is fully in place."""
    import os
    if not final.exists():
        os.replace(staging, final)
        return
    prev = final.with_name(final.name + ".prev")
    if prev.exists():
        shutil.rmtree(prev)
    os.replace(final, prev)          # current bundle aside (atomic)
    try:
        os.replace(staging, final)   # new bundle into place (atomic)
    except OSError:
        os.replace(prev, final)      # roll back on failure
        raise
    shutil.rmtree(prev, ignore_errors=True)


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
    ap.add_argument("--marks", type=Path, default=None,
                    help="per-contract 15m mark stream; selection (family pick "
                         "AND ensemble operating point) then runs through the "
                         "mark-to-market ledger")
    args = ap.parse_args()

    select_seeds = [int(s) for s in args.select_seeds.split(",") if s.strip()]
    final_seeds = ([int(s) for s in args.final_seeds.split(",")] if args.final_seeds
                   else list(config.SEEDS))
    models = [m.strip() for m in args.models.split(",") if m.strip()]

    print(f"loading dataset + spec...", flush=True)
    ds = pd.read_parquet(config.META_DATASET_PARQUET)
    spec = load_spec()
    if args.marks:
        # Fail closed BEFORE training if the dataset can't support the ledger
        # (same contract as v4_evaluate --marks).
        blockers = option_b_blockers(ds.columns, mark_stream_exists=Path(args.marks).exists())
        if blockers:
            raise SystemExit("cannot run mark-to-market selection (Option B):\n  - "
                             + "\n  - ".join(blockers))
    mark_stream = load_mark_stream(args.marks) if args.marks else None
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
            members_ = [predictor] + [
                fit_nn(train, d[d["split"] == "val"], features=features,
                       label=args.label, seed=s, epochs=args.epochs)
                for s in select_seeds[1:]]
            pred = np.mean([m.predict(val_rows) for m in members_], axis=0)
            ev = (np.mean([m.predict_ev(val_rows) for m in members_], axis=0)
                  if all(getattr(m, "predict_ev", None) for m in members_) else None)
        else:
            predictor = fit_gbt(train, d[d["split"] == "val"], features=features,
                               label=args.label, n_estimators=args.gbt_estimators)
            pred = predictor.predict(val_rows)
            ev_fn = getattr(predictor, "predict_ev", None)
            ev = ev_fn(val_rows) if ev_fn else None
        policy = choose_policy(val_rows, pred, spec, mark_stream=mark_stream,
                               ev_predictions=ev)
        policy["family"] = family
        candidates.append(policy)
        ret = policy["metrics"]["total_return"]
        print(f"  {family}: best {policy_label(policy)} "
              f"val_return={ret} ({time.time()-t0:.0f}s)", flush=True)

    winner = _select_winner(candidates)
    family = winner["family"]
    sel_note = "eligible" if winner.get("eligible") else "INELIGIBLE (cheap-seed)"
    print(f"\nSELECTED FAMILY: {family} "
          f"(cheap-seed {policy_label(winner)}, "
          f"val_return={winner['metrics']['total_return']}, {sel_note})", flush=True)

    # ── 2) train the full ensemble for the winning family INTO A STAGING DIR ──
    # The existing model_final_v4/ is left untouched until the new bundle is
    # trained, gate-checked, and atomically swapped in — a crash or a gate
    # failure never destroys a previously-validated deployable model.
    staging = FINAL_DIR.with_name(FINAL_DIR.name + ".staging")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    print(f"\n=== training final {family} ensemble, {len(final_seeds)} seeds "
          f"(-> {staging.name}) ===", flush=True)
    run_ids, members, artifact_files = [], [], []
    val_split_df = d[d["split"] == "val"]
    for seed in final_seeds:
        t0 = time.time()
        lab_tag = "win" if args.label == "label" else "xs"
        run_id = f"v4-{family}-{lab_tag}-s{seed}"
        if family == "nn":
            info, member = _train_nn_seed(train, val_split_df, features=features,
                                          label=args.label, seed=seed, epochs=args.epochs,
                                          run_id=run_id, out_dir=staging)
        else:
            info, member = _train_gbt_seed(train, val_split_df, features=features,
                                           label=args.label, seed=seed,
                                           n_estimators=args.gbt_estimators,
                                           run_id=run_id, out_dir=staging)
        run_ids.append(run_id)
        members.append(member)
        artifact_files += [staging / run_id / f for f in info["files"]]
        print(f"  seed {seed}: saved {run_id} ({time.time()-t0:.0f}s)", flush=True)

    # ── 3) RE-VALIDATE the operating point with the ACTUAL shipped ensemble ──
    # The cheap-seed selection above only picks the family. The mode/threshold
    # a 40-seed ensemble should deploy at is re-chosen on the ensemble's own
    # val scores, whose distribution differs from the 5-seed proxy's.
    print("\n=== re-validating operating point on the full ensemble ===", flush=True)
    ens_val_pred = _ensemble_predict(family, members, val_rows, features)
    ens_val_ev = _ensemble_ev(family, members, val_rows, features)
    final_policy = choose_policy(val_rows, ens_val_pred, spec, mark_stream=mark_stream,
                                 ev_predictions=ens_val_ev)
    mode, threshold = final_policy["mode"], final_policy["threshold"]
    dd_brake = final_policy.get("dd_brake")
    metrics = final_policy["metrics"]
    flipped = bool(winner.get("eligible")) and not final_policy["eligible"]
    print(f"  ensemble winner: {policy_label(final_policy)} "
          f"val_return={metrics['total_return']} n_kept={metrics['n_kept']} "
          f"eligible={final_policy['eligible']}"
          f"{'  ⚠ FLIPPED from eligible→ineligible' if flipped else ''}", flush=True)

    # ── 4) GATE: refuse to persist a bundle that cleared no gate ─────────────
    if not final_policy["eligible"]:
        shutil.rmtree(staging)
        print("\nNO ELIGIBLE CONFIG — the full ensemble did not clear the gate "
              "(kept >= {}, beat baseline, maxDD <= {:.0%}; modes tried: filter, rank{}). "
              "Nothing persisted; any existing {} is untouched.".format(
                  config.MIN_KEPT_TRADES, config.MAX_DRAWDOWN_CAP,
                  ", ev" if ens_val_ev is not None else "", FINAL_DIR.name))
        raise SystemExit(1)

    # ── 5) write the ensemble config + a manifest covering the trained files ──
    (staging / "ensemble_config.json").write_text(json.dumps({
        "run_ids": run_ids, "family": family, "mode": mode, "threshold": threshold,
        "dd_brake": dd_brake, "label": args.label, "features": features,
        "val_return": metrics["total_return"], "val_n_kept": metrics["n_kept"],
        "val_max_drawdown": metrics["max_drawdown"], "eligible": True,
        "baseline_return": final_policy.get("baseline_return"),
        "operating_point_source": "full-ensemble revalidation",
        "magnitude_head": ens_val_ev is not None,
        "ev_thresholds": list(config.EV_THRESHOLDS),
        "ev_dd_brakes": list(config.EV_DD_BRAKES), "ev_dd_floor": config.EV_DD_FLOOR,
        "selection_basis": final_policy["selection_basis"],
        "select_seeds": select_seeds, "final_seeds": final_seeds,
        "baseline_config_hash": spec["config_hash"],
        "schema": "v4", "purged": True, "embargo": args.embargo,
    }, indent=2))
    artifact_files.append(staging / "ensemble_config.json")

    manifest = create_manifest(
        dataset_path=config.META_DATASET_PARQUET,
        baseline_spec_path=config.BASELINE_SPEC_JSON,
        feature_names=features,
        provider_metadata={"pool": config.POOL, "interval": config.INTERVAL,
                           "options_history_constraint": "15m; approximately two years",
                           "selection_basis": final_policy["selection_basis"],
                           "mark_stream": str(args.marks) if args.marks else None},
        code_root=config.ROOT.parent,
        output_artifacts=artifact_files)
    write_manifest(manifest, staging / "manifest.json")

    # ── 6) atomic swap: the new bundle replaces the old only now ─────────────
    _atomic_swap(staging, FINAL_DIR)

    print(f"\nDONE. {family}/{policy_label(final_policy)} "
          f"(val_return={metrics['total_return']}, {len(run_ids)} seeds) -> {FINAL_DIR}")


if __name__ == "__main__":
    main()
