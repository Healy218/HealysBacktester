"""Publish current V6 candidate features before their outcomes mature."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


class LiveFeatureError(ValueError):
    """Raised when current V6 features cannot be published safely."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def publish_v6_features(sources: Iterable[Path], output_dir: Path,
                        model_config: Path | dict[str, Any], through: str) -> dict[str, Any]:
    """Publish complete current candidate features with outcomes pending.

    This is intentionally a different contract from the replay matrix: a
    current candidate has features now, but its realized outcome is only
    knowable after its forward horizon. The output is therefore not admitted
    to replay until an explicit outcome join produces the separate outcome
    column and updates the manifest.
    """
    config = json.loads(Path(model_config).read_text()) if isinstance(model_config, (str, Path)) else model_config
    features = config.get("features") if isinstance(config, dict) else None
    if not isinstance(features, list) or not features or len(set(features)) != len(features):
        raise LiveFeatureError("model config has no valid feature contract")
    allow_missing = config.get("family") == "gbt"
    files = sorted({Path(path).resolve() for path in sources})
    if not files or any(not path.is_file() or path.suffix != ".parquet" for path in files):
        raise LiveFeatureError("all live feature sources must be parquet files")
    frames = []
    for path in files:
        columns = set(pd.read_parquet(path, engine="pyarrow").columns)
        missing = sorted(set(features) - columns)
        if missing:
            raise LiveFeatureError(f"{path}: missing {len(missing)} model columns: {missing}")
        if "entry_ts" not in columns:
            raise LiveFeatureError(f"{path}: no entry_ts identity column")
        frame = pd.read_parquet(path, columns=["symbol", "strategy", "dte", "entry_ts", *features])
        frame["entry_ts"] = pd.to_datetime(frame["entry_ts"], errors="coerce", utc=True)
        if frame["entry_ts"].isna().any():
            raise LiveFeatureError(f"{path}: invalid entry_ts")
        frame = frame[frame["entry_ts"].dt.date.astype(str) <= through]
        values = frame[features].apply(pd.to_numeric, errors="coerce")
        if (not allow_missing and values.isna().any().any()) or np.isinf(values.to_numpy(dtype=float)).any():
            raise LiveFeatureError(f"{path}: model features contain missing or non-finite values")
        frame[features] = values.astype(float)
        frames.append(frame)
    result = pd.concat(frames, ignore_index=True).sort_values(
        ["entry_ts", "symbol", "strategy", "dte"], kind="stable").reset_index(drop=True)
    if result.empty:
        raise LiveFeatureError("no current candidate features remain through cutoff")
    if result.duplicated(["symbol", "strategy", "dte", "entry_ts"]).any():
        raise LiveFeatureError("duplicate live candidate identities")
    output_dir = Path(output_dir).resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise LiveFeatureError("output directory must be new and empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    matrix = output_dir / "features.parquet"
    temp = output_dir / "features.parquet.tmp"
    result.to_parquet(temp, index=False)
    temp.replace(matrix)
    manifest = {
        "schema": "incubator-live-feature-matrix-v1",
        "generation": "v6",
        "through": through,
        "feature_columns": features,
        "outcome_column": "net_return",
        "outcome_status": "pending",
        "missing_value_policy": "model_native_nan" if allow_missing else "complete_rows_only",
        "rows": len(result),
        "files": {"features.parquet": _sha256(matrix)},
        "sources": [{"path": str(path), "sha256": _sha256(path)} for path in files],
    }
    (output_dir / "feature-manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    return manifest
