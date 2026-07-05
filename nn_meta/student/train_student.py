# nn_meta/student/train_student.py
"""Two-stage student training: behavior cloning, then counterfactual fine-tune.

Stage 1 (clone):   3-class softmax on teacher_state, class-balanced.
Stage 2 (finetune): same net, ft_label/ft_weight (winning trade bars keep
                    their direction, losing trade bars relabeled FLAT), at a
                    reduced learning rate. Both stages keep the best-val-loss
                    epoch's weights. Saves model_clone.keras AND model.keras
                    per run so the parity gate can score the clone alone.

Run:  python -m nn_meta.student.train_student [--smoke]
"""
import argparse
import json
import os
import time

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow.keras import layers, regularizers  # type: ignore

from nn_meta import config
from nn_meta.student.dataset import STUDENT_FEATURES


def build_student_mlp(n_features: int, hidden: list[int], lr: float) -> tf.keras.Model:
    inp = layers.Input(shape=(n_features,))
    x = inp
    for units in hidden:
        x = layers.Dense(units, activation="relu",
                         kernel_regularizer=regularizers.l2(config.L2_REG))(x)
        x = layers.Dropout(config.DROPOUT)(x)
    out = layers.Dense(3, activation="softmax")(x)
    model = tf.keras.Model(inp, out)
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=lr),
                  loss=tf.keras.losses.SparseCategoricalCrossentropy())
    return model


def _matrix(rows: pd.DataFrame, mu: pd.Series, sd: pd.Series) -> np.ndarray:
    X = rows[STUDENT_FEATURES].fillna(mu)
    return ((X - mu) / sd).values.astype("float32")


def _fit_best(model, Xtr, ytr, wtr, Xva, yva, wva, epochs, ckpt_path):
    ckpt = tf.keras.callbacks.ModelCheckpoint(str(ckpt_path), monitor="val_loss",
                                              save_best_only=True,
                                              save_weights_only=True)
    hist = model.fit(Xtr, ytr, sample_weight=wtr,
                     validation_data=(Xva, yva, wva),
                     epochs=epochs, batch_size=config.BATCH_SIZE,
                     callbacks=[ckpt], verbose=0)
    if ckpt_path.exists():
        model.load_weights(ckpt_path)
        ckpt_path.unlink()
    return float(np.min(hist.history["val_loss"]))


def run_one(panel: pd.DataFrame, lr: float, seed: int,
            clone_epochs: int, ft_epochs: int) -> dict:
    tr = panel[panel["split"] == "train"]
    va = panel[panel["split"] == "val"]
    mu = tr[STUDENT_FEATURES].mean()
    sd = tr[STUDENT_FEATURES].std().replace(0, 1.0)
    Xtr, Xva = _matrix(tr, mu, sd), _matrix(va, mu, sd)

    tf.keras.utils.set_random_seed(seed)
    model = build_student_mlp(len(STUDENT_FEATURES), config.STUDENT_ARCH, lr)

    run_id = f"stud-lr{lr:g}-s{seed}"
    run_dir = config.RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    # ── stage 1: clone (class-balanced weights) ───────────────────────────────
    y1_tr = tr["teacher_state"].values.astype("int32")
    y1_va = va["teacher_state"].values.astype("int32")
    freq = np.bincount(y1_tr, minlength=3).astype(float)
    cls_w = freq.sum() / np.maximum(freq, 1.0)
    cls_w /= cls_w.mean()
    w1_tr = cls_w[y1_tr].astype("float32")
    w1_va = cls_w[y1_va].astype("float32")
    clone_loss = _fit_best(model, Xtr, y1_tr, w1_tr, Xva, y1_va, w1_va,
                           clone_epochs, run_dir / "ck1.weights.h5")
    model.save(run_dir / "model_clone.keras")
    clone_acc = float((model.predict(Xva, batch_size=4096, verbose=0)
                       .argmax(1) == y1_va).mean())

    # ── stage 2: counterfactual fine-tune at reduced LR ───────────────────────
    model.optimizer.learning_rate.assign(lr * config.FINETUNE_LR_SCALE)
    y2_tr = tr["ft_label"].values.astype("int32")
    y2_va = va["ft_label"].values.astype("int32")
    w2_tr = tr["ft_weight"].values.astype("float32")
    w2_va = va["ft_weight"].values.astype("float32")
    ft_loss = _fit_best(model, Xtr, y2_tr, w2_tr, Xva, y2_va, w2_va,
                        ft_epochs, run_dir / "ck2.weights.h5")
    model.save(run_dir / "model.keras")

    (run_dir / "scaler.json").write_text(json.dumps(
        {"mean": mu.to_dict(), "std": sd.to_dict()}))
    (run_dir / "params.json").write_text(json.dumps(
        {"arch": config.STUDENT_ARCH, "lr": lr, "seed": seed,
         "features": STUDENT_FEATURES}))
    return {"run_id": run_id, "lr": lr, "seed": seed,
            "clone_val_loss": clone_loss, "clone_val_acc": clone_acc,
            "ft_val_loss": ft_loss, "train_rows": len(tr), "val_rows": len(va),
            "seconds": round(time.time() - t0, 1)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()

    panel = pd.read_parquet(config.STUDENT_DATASET_PARQUET)
    config.ensure_dirs()
    lrs = config.STUDENT_LRS[:1] if args.smoke else config.STUDENT_LRS
    seeds = config.SEEDS[:2] if args.smoke else config.SEEDS
    c_ep = 4 if args.smoke else config.CLONE_EPOCHS
    f_ep = 4 if args.smoke else config.FINETUNE_EPOCHS

    total = len(lrs) * len(seeds)
    print(f"training {total} student runs on {len(panel)} bars "
          f"({'SMOKE' if args.smoke else 'FULL'})", flush=True)
    rows, i = [], 0
    for lr in lrs:
        for seed in seeds:
            i += 1
            r = run_one(panel, lr, seed, c_ep, f_ep)
            rows.append(r)
            print(f"  [{i}/{total}] {r['run_id']}: clone_acc={r['clone_val_acc']:.2f} "
                  f"ft_val_loss={r['ft_val_loss']:.4f} ({r['seconds']}s)", flush=True)
            pd.DataFrame(rows).to_csv(config.STUDENT_RUNS_CSV, index=False)
    print(f"done — registry at {config.STUDENT_RUNS_CSV}")


if __name__ == "__main__":
    main()
