# nn_options_signal/train.py
"""Train the full grid: architectures x learning rates x horizons x seeds.

Each run: standardize features (scaler fit on train only), fit with early
stopping monitored on the VALIDATION period's loss, save model + scaler,
append a row to runs/runs.csv.

Run:  python -m nn_options_signal.train [--smoke]
"""
import argparse
import json
import os
import time

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import numpy as np
import pandas as pd
import tensorflow as tf

from nn_options_signal import config
from nn_options_signal.build_dataset import DATASET_VERSION, FEATURES, require_current_panel
from nn_options_signal.model import build_mlp


def run_one(panel: pd.DataFrame, arch: list[int], lr: float, horizon: int,
            seed: int, max_epochs: int) -> dict:
    label = f"label_h{horizon}"
    tr = panel[(panel["split"] == "train") & panel[label].notna()]
    va = panel[(panel["split"] == "val") & panel[label].notna()]

    mu = tr[FEATURES].mean()
    sd = tr[FEATURES].std().replace(0, 1.0)
    Xtr = ((tr[FEATURES] - mu) / sd).values.astype("float32")
    ytr = tr[label].values.astype("float32")
    Xva = ((va[FEATURES] - mu) / sd).values.astype("float32")
    yva = va[label].values.astype("float32")

    tf.keras.utils.set_random_seed(seed)
    model = build_mlp(len(FEATURES), arch, lr)

    run_id = f"h{horizon}-a{'x'.join(map(str, arch))}-lr{lr:g}-s{seed}"
    run_dir = config.RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Full epoch budget, no early stop; keep the best-validation epoch's weights.
    ckpt_path = run_dir / "best.weights.h5"
    ckpt = tf.keras.callbacks.ModelCheckpoint(str(ckpt_path), monitor="val_loss",
                                              save_best_only=True,
                                              save_weights_only=True)
    t0 = time.time()
    hist = model.fit(Xtr, ytr, validation_data=(Xva, yva),
                     epochs=max_epochs, batch_size=config.BATCH_SIZE,
                     callbacks=[ckpt], verbose=0)
    if ckpt_path.exists():
        model.load_weights(ckpt_path)
        ckpt_path.unlink()
    model.save(run_dir / "model.keras")
    (run_dir / "scaler.json").write_text(json.dumps(
        {"mean": mu.to_dict(), "std": sd.to_dict()}))
    (run_dir / "params.json").write_text(json.dumps(
        {"arch": arch, "lr": lr, "horizon": horizon, "seed": seed,
         "options_signal_version": DATASET_VERSION}))

    val_loss = float(np.min(hist.history["val_loss"]))
    return {"run_id": run_id, "arch": "x".join(map(str, arch)), "lr": lr,
            "horizon": horizon, "seed": seed,
            "epochs_ran": len(hist.history["loss"]),
            "best_epoch": int(np.argmin(hist.history["val_loss"])) + 1,
            "train_loss": float(hist.history["loss"][-1]),
            "val_loss": val_loss,
            "train_rows": len(tr), "val_rows": len(va),
            "seconds": round(time.time() - t0, 1)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="1 config, 2 seeds, few epochs")
    args = ap.parse_args()

    panel = pd.read_parquet(config.DATASET_PARQUET)
    require_current_panel(panel)
    config.ensure_dirs()

    archs = config.ARCHITECTURES[:1] if args.smoke else config.ARCHITECTURES
    lrs = config.LEARNING_RATES[:1] if args.smoke else config.LEARNING_RATES
    horizons = config.HORIZONS[:1] if args.smoke else config.HORIZONS
    seeds = config.SEEDS[:2] if args.smoke else config.SEEDS
    max_epochs = 5 if args.smoke else config.MAX_EPOCHS

    total = len(archs) * len(lrs) * len(horizons) * len(seeds)
    print(f"training {total} runs on {len(panel)} panel rows "
          f"({'SMOKE' if args.smoke else 'FULL'})", flush=True)

    rows, i = [], 0
    for horizon in horizons:
        for arch in archs:
            for lr in lrs:
                for seed in seeds:
                    i += 1
                    r = run_one(panel, arch, lr, horizon, seed, max_epochs)
                    rows.append(r)
                    print(f"  [{i}/{total}] {r['run_id']}: val_loss={r['val_loss']:.5f} "
                          f"epochs={r['epochs_ran']} ({r['seconds']}s)", flush=True)
                    pd.DataFrame(rows).to_csv(config.RUNS_CSV, index=False)

    print(f"done — registry at {config.RUNS_CSV}")


if __name__ == "__main__":
    main()
