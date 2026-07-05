# nn_meta/train_meta.py
"""Train the meta-classifier grid: architectures × learning rates × seeds.

Mirrors nn_options_signal/train.py: scaler fit on train only (NaNs imputed
with the train mean → zero post-scaling), full epoch budget with the
best-validation-epoch weights kept, one row per run in runs/runs.csv.

Run:  python -m nn_meta.train_meta [--smoke]
"""
import argparse
import json
import os
import time

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import numpy as np
import pandas as pd
import tensorflow as tf

from nn_meta import config
from nn_meta.build_meta_dataset import META_FEATURES
from nn_meta.model import build_meta_mlp


def prepare_matrix(rows: pd.DataFrame, mu: pd.Series, sd: pd.Series) -> np.ndarray:
    X = rows[META_FEATURES].copy()
    X = X.fillna(mu)                       # train-mean imputation
    return ((X - mu) / sd).values.astype("float32")


def sample_weights(net_return: pd.Series) -> np.ndarray:
    w = net_return.abs().clip(upper=config.SAMPLE_WEIGHT_CLIP).values
    w = np.where(np.isfinite(w), w, 0.0).astype("float32")
    mean = w.mean() if w.size else 1.0
    return w / mean if mean > 0 else np.ones_like(w)


def run_one(panel: pd.DataFrame, arch: list[int], lr: float, seed: int,
            max_epochs: int, label_col: str = "label") -> dict:
    tr = panel[(panel["split"] == "train") & panel[label_col].notna()]
    va = panel[(panel["split"] == "val") & panel[label_col].notna()]

    mu = tr[META_FEATURES].mean()
    sd = tr[META_FEATURES].std().replace(0, 1.0)
    Xtr, ytr = prepare_matrix(tr, mu, sd), tr[label_col].values.astype("float32")
    Xva, yva = prepare_matrix(va, mu, sd), va[label_col].values.astype("float32")
    wtr = sample_weights(tr["net_return"])
    wva = sample_weights(va["net_return"])

    tf.keras.utils.set_random_seed(seed)
    model = build_meta_mlp(len(META_FEATURES), arch, lr)

    lab_tag = "win" if label_col == "label" else "xs"
    run_id = f"a{'x'.join(map(str, arch))}-lr{lr:g}-{lab_tag}-s{seed}"
    run_dir = config.RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    ckpt_path = run_dir / "best.weights.h5"
    ckpt = tf.keras.callbacks.ModelCheckpoint(str(ckpt_path), monitor="val_loss",
                                              save_best_only=True,
                                              save_weights_only=True)
    t0 = time.time()
    hist = model.fit(Xtr, ytr, sample_weight=wtr,
                     validation_data=(Xva, yva, wva),
                     epochs=max_epochs, batch_size=config.BATCH_SIZE,
                     callbacks=[ckpt], verbose=0)
    if ckpt_path.exists():
        model.load_weights(ckpt_path)
        ckpt_path.unlink()
    model.save(run_dir / "model.keras")
    (run_dir / "scaler.json").write_text(json.dumps(
        {"mean": mu.to_dict(), "std": sd.to_dict()}))
    (run_dir / "params.json").write_text(json.dumps(
        {"arch": arch, "lr": lr, "seed": seed, "label": label_col,
         "features": META_FEATURES}))

    best_epoch = int(np.argmin(hist.history["val_loss"]))
    return {"run_id": run_id, "arch": "x".join(map(str, arch)), "lr": lr,
            "label": label_col,
            "seed": seed, "epochs_ran": len(hist.history["loss"]),
            "best_epoch": best_epoch + 1,
            "train_loss": float(hist.history["loss"][-1]),
            "val_loss": float(hist.history["val_loss"][best_epoch]),
            "val_auc": float(hist.history["val_auc"][best_epoch]),
            "train_rows": len(tr), "val_rows": len(va),
            "seconds": round(time.time() - t0, 1)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="1 config, 2 seeds, few epochs")
    args = ap.parse_args()

    panel = pd.read_parquet(config.META_DATASET_PARQUET)
    config.ensure_dirs()

    archs = config.ARCHITECTURES[:1] if args.smoke else config.ARCHITECTURES
    lrs = config.LEARNING_RATES[:1] if args.smoke else config.LEARNING_RATES
    seeds = config.SEEDS[:2] if args.smoke else config.SEEDS
    labels = ["label"] if args.smoke else \
        ["label" if lt == "win" else "label_excess" for lt in config.LABEL_TYPES]
    max_epochs = 5 if args.smoke else config.MAX_EPOCHS

    n_lab = panel["label"].notna().sum()
    total = len(archs) * len(lrs) * len(seeds) * len(labels)
    print(f"training {total} runs on {n_lab} labeled rows "
          f"({'SMOKE' if args.smoke else 'FULL'})", flush=True)

    rows, i = [], 0
    for label_col in labels:
        for arch in archs:
            for lr in lrs:
                for seed in seeds:
                    i += 1
                    r = run_one(panel, arch, lr, seed, max_epochs, label_col)
                    rows.append(r)
                    print(f"  [{i}/{total}] {r['run_id']}: "
                          f"val_loss={r['val_loss']:.4f} "
                          f"val_auc={r['val_auc']:.3f} ({r['seconds']}s)", flush=True)
                    pd.DataFrame(rows).to_csv(config.RUNS_CSV, index=False)

    print(f"done — registry at {config.RUNS_CSV}")


if __name__ == "__main__":
    main()
