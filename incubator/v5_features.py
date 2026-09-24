"""Opt-in capture and daily sealing of genuine V5 scanner feature batches."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .forward import _sha256

KEYS = ["symbol", "strategy", "dte", "entry_ts"]


class V5CaptureError(ValueError):
    """V5 scanner features are missing, ambiguous, or changed after sealing."""


def _config(config: dict[str, Any]) -> tuple[list[str], str]:
    features = config.get("features")
    if (config.get("family") != "nn" or config.get("mode") != "ev" or
            not isinstance(features, list) or not features or len(set(features)) != len(features)):
        raise V5CaptureError("V5 capture requires the active NN/EV feature contract")
    digest = hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":"),
                                       allow_nan=False).encode()).hexdigest()
    return features, digest


def _normalize(batch: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    missing = sorted(set(KEYS + features) - set(batch.columns))
    if missing:
        raise V5CaptureError(f"V5 batch is missing columns: {missing}")
    frame = batch[KEYS + features].copy()
    frame["entry_ts"] = pd.to_datetime(frame["entry_ts"], utc=True, errors="coerce")
    if frame.empty or frame[KEYS].isna().any().any():
        raise V5CaptureError("V5 batch has no complete candidate identities")
    frame["dte"] = pd.to_numeric(frame["dte"], errors="coerce")
    if frame["dte"].isna().any() or (frame["dte"] < 1).any() or (frame["dte"] % 1).any():
        raise V5CaptureError("V5 batch has invalid target DTE identities")
    frame["dte"] = frame["dte"].astype(int)
    values = frame[features].apply(pd.to_numeric, errors="coerce")
    if (values.isna() & frame[features].notna()).any().any():
        raise V5CaptureError("V5 features contain non-numeric values")
    if np.isinf(values.to_numpy(dtype=float)).any():
        raise V5CaptureError("V5 features contain infinity")
    frame[features] = values.astype(float)
    frame = frame.sort_values(KEYS, kind="stable").reset_index(drop=True)
    if frame.duplicated(KEYS).any():
        raise V5CaptureError("V5 candidate identities are duplicated")
    return frame


def capture_v5_pass(batch: pd.DataFrame, capture_root: Path, model_config: dict[str, Any],
                    *, observed_at: str) -> dict:
    """Seal one scored signal-bar batch; never mutate live paper state."""
    features, config_sha = _config(model_config)
    frame = _normalize(batch, features)
    bars = frame["entry_ts"].drop_duplicates()
    if len(bars) != 1:
        raise V5CaptureError("a V5 capture pass must contain one signal bar")
    bar = bars.iloc[0]
    observed = pd.Timestamp(observed_at)
    if observed.tzinfo is None or observed.tz_convert("UTC") < bar:
        raise V5CaptureError("V5 capture clock is missing or predates the signal")
    through = bar.date().isoformat()
    directory = Path(capture_root) / through / bar.strftime("%Y%m%dT%H%M%SZ")
    if directory.exists():
        manifest = json.loads((directory / "feature-manifest.json").read_text())
        matrix = directory / "features.parquet"
        if (manifest.get("generation") != "v5" or manifest.get("model_config_sha256") != config_sha or
                manifest.get("files", {}).get("features.parquet") != _sha256(matrix) or
                not pd.read_parquet(matrix).equals(frame)):
            raise V5CaptureError("V5 pass changed after sealing; refusing overwrite")
        return manifest
    directory.mkdir(parents=True, exist_ok=False)
    matrix = directory / "features.parquet"
    frame.to_parquet(matrix, index=False)
    manifest = {"schema": "incubator-live-feature-matrix-v1", "generation": "v5",
                "through": through, "signal_bar": bar.isoformat(),
                "observed_at": observed.tz_convert("UTC").isoformat(),
                "model_config_sha256": config_sha,
                "feature_columns": features, "outcome_column": "net_return",
                "outcome_status": "pending", "missing_value_policy": "model_scaler_mean_impute",
                "rows": len(frame), "files": {"features.parquet": _sha256(matrix)},
                "sources": [{"type": "v5-live-scanner-batch", "signal_bar": bar.isoformat()}]}
    (directory / "feature-manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    return manifest


def assemble_v5_day(capture_root: Path, output_dir: Path, model_config: dict[str, Any],
                    *, through: str) -> dict:
    """Combine verified, distinct V5 signal bars into one daily replay matrix."""
    date.fromisoformat(through)
    features, config_sha = _config(model_config)
    directories = sorted((Path(capture_root) / through).glob("*/feature-manifest.json"))
    if not directories:
        raise V5CaptureError(f"no genuine V5 scanner passes for {through}")
    frames, sources = [], []
    for manifest_path in directories:
        manifest = json.loads(manifest_path.read_text())
        matrix = manifest_path.parent / "features.parquet"
        if (manifest.get("schema") != "incubator-live-feature-matrix-v1" or
                manifest.get("generation") != "v5" or manifest.get("through") != through or
                manifest.get("model_config_sha256") != config_sha or
                manifest.get("feature_columns") != features or
                manifest.get("files", {}).get("features.parquet") != _sha256(matrix)):
            raise V5CaptureError(f"V5 pass seal/contract mismatch: {manifest_path}")
        frame = _normalize(pd.read_parquet(matrix), features)
        if (len(frame) != manifest.get("rows") or
                frame["entry_ts"].nunique() != 1 or
                frame["entry_ts"].iloc[0].isoformat() != manifest.get("signal_bar")):
            raise V5CaptureError(f"V5 pass row/bar mismatch: {manifest_path}")
        frames.append(frame)
        sources.append({"path": str(matrix.resolve()), "sha256": _sha256(matrix),
                        "manifest_path": str(manifest_path.resolve()),
                        "manifest_sha256": _sha256(manifest_path)})
    daily = _normalize(pd.concat(frames, ignore_index=True), features)
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        old = json.loads((output_dir / "feature-manifest.json").read_text())
        matrix = output_dir / "features.parquet"
        if (old.get("generation") != "v5" or old.get("through") != through or
                old.get("sources") != sources or old.get("model_config_sha256") != config_sha or
                old.get("files", {}).get("features.parquet") != _sha256(matrix) or
                not pd.read_parquet(matrix).equals(daily)):
            raise V5CaptureError("V5 daily matrix changed after sealing; refusing overwrite")
        return old
    output_dir.mkdir(parents=True, exist_ok=True)
    matrix = output_dir / "features.parquet"
    daily.to_parquet(matrix, index=False)
    manifest = {"schema": "incubator-live-feature-matrix-v1", "generation": "v5",
                "through": through, "model_config_sha256": config_sha,
                "feature_columns": features, "outcome_column": "net_return",
                "outcome_status": "pending", "missing_value_policy": "model_scaler_mean_impute",
                "rows": len(daily), "files": {"features.parquet": _sha256(matrix)},
                "sources": sources}
    (output_dir / "feature-manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    return manifest
