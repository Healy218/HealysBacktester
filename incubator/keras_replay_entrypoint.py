#!/usr/bin/env python3
"""Standalone entrypoint copied into Keras incubator bundles."""

from __future__ import annotations

import json
import os
from pathlib import Path


def main() -> int:
    import pandas as pd

    request = json.loads(Path(os.environ["AI_INCUBATOR_REQUEST"]).read_text())
    output = Path(os.environ["AI_INCUBATOR_OUTPUT"])
    root = Path(request["snapshot_root"]).resolve()
    feature_path = Path(request["feature_path"])
    if not root.is_dir() or feature_path.is_absolute() or ".." in feature_path.parts:
        raise ValueError("invalid forward feature path")
    source = (root / feature_path).resolve()
    if root not in source.parents or not source.is_file() or source.is_symlink():
        raise ValueError("forward feature table is unavailable")
    config = json.loads(Path("ensemble_config.json").read_text())
    columns = config.get("features")
    outcome = request.get("outcome_column")
    if not isinstance(columns, list) or not columns or not isinstance(outcome, str):
        raise ValueError("incomplete replay contract")
    frame = pd.read_parquet(source)
    missing = sorted(set(columns + [outcome]) - set(frame.columns))
    if missing or frame.empty or frame[columns + [outcome]].isna().any().any():
        raise ValueError(f"forward feature table is incomplete: {missing}")
    import numpy as np
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(1)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    values = frame[columns].to_numpy(dtype=np.float32)
    predictions = []
    for run_id in config["run_ids"]:
        member = Path(run_id)
        scaler = json.loads((member / "scaler.json").read_text())
        mean = np.asarray([scaler["mean"][column] for column in columns], dtype=np.float32)
        scale = np.asarray([scaler.get("scale", {}).get(column, 1.0) for column in columns], dtype=np.float32)
        if np.any(scale == 0) or not np.isfinite(np.concatenate((mean, scale))).all():
            raise ValueError(f"invalid scaler: {run_id}")
        model = tf.keras.models.load_model(member / "model.keras", compile=False)
        predictions.append(np.asarray(model.predict((values - mean) / scale, verbose=0)).reshape(-1))
    ensemble = np.mean(np.vstack(predictions), axis=0)
    if not np.isfinite(ensemble).all():
        raise ValueError("non-finite ensemble prediction")
    output.mkdir(parents=True, exist_ok=True)
    with (output / "results.jsonl").open("w") as handle:
        for prediction, actual in zip(ensemble, frame[outcome]):
            handle.write(json.dumps({"prediction": float(prediction), "outcome": float(actual)}) + "\n")
    print(json.dumps({"status": "replayed", "rows": len(frame), "members": len(predictions)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
