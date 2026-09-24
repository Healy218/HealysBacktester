"""Join explicit matured forward outcomes to published live features."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


class OutcomeJoinError(ValueError):
    """Raised when outcomes are ambiguous or cannot be joined safely."""


KEYS = ["symbol", "strategy", "dte", "entry_ts"]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def join_matured_outcomes(feature_dir: Path, outcome_sources: Iterable[Path],
                          output_dir: Path) -> dict:
    """Publish a replay-ready matrix only for exact, matured outcome matches."""
    feature_dir = Path(feature_dir).resolve()
    manifest_path = feature_dir / "feature-manifest.json"
    matrix_path = feature_dir / "features.parquet"
    if not manifest_path.is_file() or not matrix_path.is_file():
        raise OutcomeJoinError("feature directory is missing its matrix or manifest")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("schema") != "incubator-live-feature-matrix-v1":
        raise OutcomeJoinError("feature directory is not a live pending matrix")
    features = manifest.get("feature_columns")
    if not isinstance(features, list) or not features:
        raise OutcomeJoinError("live matrix has no feature contract")
    feature_frame = pd.read_parquet(matrix_path)
    missing_keys = sorted(set(KEYS) - set(feature_frame.columns))
    if missing_keys:
        raise OutcomeJoinError(f"live matrix is missing identity columns: {missing_keys}")
    sources = sorted({Path(path).resolve() for path in outcome_sources})
    if not sources or any(not path.is_file() or path.suffix != ".parquet" for path in sources):
        raise OutcomeJoinError("outcome sources must be parquet files")
    outcomes = []
    for path in sources:
        columns = set(pd.read_parquet(path, engine="pyarrow").columns)
        missing = sorted(set(KEYS + ["net_return"]) - columns)
        if missing:
            raise OutcomeJoinError(f"{path}: missing outcome columns: {missing}")
        frame = pd.read_parquet(path, columns=KEYS + ["net_return"])
        frame["entry_ts"] = pd.to_datetime(frame["entry_ts"], errors="coerce", utc=True)
        frame["net_return"] = pd.to_numeric(frame["net_return"], errors="coerce")
        outcomes.append(frame)
    outcome_frame = pd.concat(outcomes, ignore_index=True)
    if outcome_frame[KEYS].isna().any().any():
        raise OutcomeJoinError("outcome source contains invalid identity values")
    if outcome_frame.duplicated(KEYS).any():
        raise OutcomeJoinError("outcome sources contain duplicate identity keys")
    feature_frame["entry_ts"] = pd.to_datetime(feature_frame["entry_ts"], errors="coerce", utc=True)
    if feature_frame[KEYS].isna().any().any():
        raise OutcomeJoinError("live matrix contains invalid identity values")
    merged = feature_frame.merge(outcome_frame, on=KEYS, how="left", validate="one_to_one")
    matched = merged["net_return"].notna()
    pending = int((~matched).sum())
    if matched.sum() == 0:
        return {"schema": "incubator-outcome-join-v1", "status": "pending",
                "feature_rows": len(feature_frame), "matched_rows": 0,
                "pending_rows": pending, "output": None,
                "outcome_sources": [{"path": str(path), "sha256": _sha256(path)} for path in sources]}
    selected = merged.loc[matched].copy()
    if not np.isfinite(selected["net_return"].to_numpy(dtype=float)).all():
        raise OutcomeJoinError("matched outcomes contain non-finite values")
    output_dir = Path(output_dir).resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise OutcomeJoinError("output directory must be new and empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "features.parquet"
    temp = output_dir / "features.parquet.tmp"
    selected.to_parquet(temp, index=False)
    temp.replace(output_path)
    result = {
        "schema": "incubator-feature-matrix-v1", "status": "replay_ready",
        "generation": manifest.get("generation"),
        "through": manifest.get("through"), "feature_columns": features,
        "outcome_column": "net_return", "outcome_status": "matured",
        "rows": len(selected), "feature_rows": len(feature_frame),
        "matched_rows": int(matched.sum()), "pending_rows": pending,
        "files": {"features.parquet": _sha256(output_path)},
        "sources": manifest.get("sources", []),
        "outcome_sources": [{"path": str(path), "sha256": _sha256(path)} for path in sources],
    }
    (output_dir / "feature-manifest.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    return result
