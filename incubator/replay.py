"""Fail-closed replay adapter for bundled Keras ensembles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


class ReplayError(ValueError):
    """Raised when a forward replay cannot be performed without fabrication."""


def _safe_snapshot_file(request: dict[str, Any], name: str) -> Path:
    root = Path(request.get("snapshot_root", "")).resolve()
    relative = Path(name)
    if not root.is_dir() or relative.is_absolute() or ".." in relative.parts:
        raise ReplayError("invalid forward snapshot root or feature path")
    path = (root / relative).resolve()
    if root not in path.parents or not path.is_file() or path.is_symlink():
        raise ReplayError(f"forward feature file is unavailable: {name}")
    return path


def load_feature_frame(request: dict[str, Any]) -> tuple[pd.DataFrame, str]:
    """Load an explicitly captured feature table; never synthesize columns."""
    name = request.get("feature_path")
    columns = request.get("feature_columns")
    outcome = request.get("outcome_column")
    if not isinstance(name, str) or not isinstance(columns, list) or not columns:
        raise ReplayError("replay request must declare feature_path and feature_columns")
    if not isinstance(outcome, str) or outcome in columns:
        raise ReplayError("replay request must declare a separate outcome_column")
    frame = pd.read_parquet(_safe_snapshot_file(request, name))
    missing = sorted(set(columns + [outcome]) - set(frame.columns))
    if missing:
        raise ReplayError(f"forward feature table is missing {len(missing)} columns: {missing}")
    selected = frame[columns + [outcome]].copy()
    if selected.empty or selected[columns + [outcome]].isna().any().any():
        raise ReplayError("forward feature table is empty or contains missing values")
    values = selected[columns + [outcome]].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ReplayError("forward feature table contains non-finite values")
    return selected, outcome


def replay_keras_ensemble(bundle_root: Path, request: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    """Load every bundled Keras member, score captured rows, and write JSONL."""
    try:
        import tensorflow as tf
    except ImportError as exc:  # pragma: no cover - environment-specific
        raise ReplayError("TensorFlow is required for Keras replay") from exc
    bundle_root = Path(bundle_root).resolve()
    config_path = bundle_root / "ensemble_config.json"
    if not config_path.is_file():
        raise ReplayError("bundle has no ensemble_config.json")
    config = json.loads(config_path.read_text())
    columns = config.get("features")
    if not isinstance(columns, list) or not columns:
        raise ReplayError("ensemble config has no feature contract")
    request = dict(request, feature_columns=columns)
    frame, outcome_column = load_feature_frame(request)
    features = frame[columns].to_numpy(dtype=np.float32)
    predictions = []
    for run_id in config.get("run_ids", []):
        member = bundle_root / run_id
        params_path, scaler_path, model_path = member / "params.json", member / "scaler.json", member / "model.keras"
        if not all(path.is_file() for path in (params_path, scaler_path, model_path)):
            raise ReplayError(f"incomplete Keras member: {run_id}")
        scaler = json.loads(scaler_path.read_text())
        mean = np.asarray([scaler["mean"][column] for column in columns], dtype=np.float32)
        scale = np.asarray([scaler.get("scale", {}).get(column, 1.0) for column in columns], dtype=np.float32)
        if np.any(scale == 0) or not np.isfinite(np.concatenate((mean, scale))).all():
            raise ReplayError(f"invalid scaler for {run_id}")
        model = tf.keras.models.load_model(model_path, compile=False)
        values = (features - mean) / scale
        prediction = np.asarray(model.predict(values, verbose=0)).reshape(-1)
        if len(prediction) != len(frame) or not np.isfinite(prediction).all():
            raise ReplayError(f"invalid predictions from {run_id}")
        predictions.append(prediction)
    if not predictions:
        raise ReplayError("ensemble has no model members")
    ensemble = np.mean(np.vstack(predictions), axis=0)
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "results.jsonl"
    with result_path.open("w") as handle:
        for prediction, outcome in zip(ensemble, frame[outcome_column]):
            handle.write(json.dumps({"prediction": float(prediction), "outcome": float(outcome)}) + "\n")
    return {"status": "replayed", "rows": len(frame), "members": len(predictions),
            "results": str(result_path), "outcome_column": outcome_column}
