"""Sealed, generation-specific inputs for an after-close incubator run."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from .forward import _sha256
from .live_features import publish_v6_features


class DailyInputError(ValueError):
    """A daily input is unavailable or cannot be trusted."""


def load_feature_request(directory: Path, *, generation: str, as_of: str) -> dict[str, Any]:
    """Verify a sealed matrix and build a pending/scored replay request."""
    directory = Path(directory).resolve()
    manifest_path = directory / "feature-manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, ValueError) as exc:
        raise DailyInputError(f"{generation}: missing or invalid feature manifest: {exc}") from exc
    if manifest.get("schema") not in {"incubator-live-feature-matrix-v1", "incubator-feature-matrix-v1"}:
        raise DailyInputError(f"{generation}: unsupported feature manifest schema")
    if manifest.get("generation") != generation or manifest.get("through") != as_of:
        raise DailyInputError(f"{generation}: generation/date mismatch in feature manifest")
    columns = manifest.get("feature_columns")
    if not isinstance(columns, list) or not columns or len(set(columns)) != len(columns):
        raise DailyInputError(f"{generation}: invalid feature columns")
    status = manifest.get("outcome_status")
    if status not in {"pending", "matured"}:
        raise DailyInputError(f"{generation}: unsupported outcome status {status!r}")
    matrix = directory / "features.parquet"
    if not matrix.is_file() or _sha256(matrix) != manifest.get("files", {}).get("features.parquet"):
        raise DailyInputError(f"{generation}: feature matrix hash mismatch or missing file")
    frame = pd.read_parquet(matrix)
    if len(frame) != manifest.get("rows") or not set(columns).issubset(frame):
        raise DailyInputError(f"{generation}: feature matrix row/column contract mismatch")
    outcome = manifest.get("outcome_column")
    if status == "pending" and outcome in frame:
        raise DailyInputError(f"{generation}: pending matrix already contains outcomes")
    if status == "matured" and (not isinstance(outcome, str) or outcome not in frame):
        raise DailyInputError(f"{generation}: ready matrix has no outcomes")
    request = {"schema": "paper-forward-request-v1", "artifact_id": generation,
               "as_of": as_of, "forward_data_contract": "paper_forward_v1",
               "snapshot_root": str(directory), "snapshot_manifest_sha256": _sha256(manifest_path),
               "snapshot_through": as_of, "feature_path": "features.parquet",
               "feature_columns": columns, "read_only": True,
               "campaign_mode": "after-close-read-only"}
    if status == "matured":
        request["outcome_column"] = outcome
    return request


def capture_v6_day(candidates_root: Path, model_config: Path, feature_root: Path,
                   as_of: str) -> Path:
    """Capture only the named session's real V6 candidate parquets."""
    date.fromisoformat(as_of)
    stamp = as_of.replace("-", "")
    sources = sorted(Path(candidates_root).glob(f"{stamp}T*/candidates.parquet"))
    if not sources:
        raise DailyInputError(f"v6: no candidate parquets for {as_of}")
    for source in sources:
        dates = pd.to_datetime(pd.read_parquet(source, columns=["entry_ts"])["entry_ts"],
                               utc=True, errors="coerce").dt.date.astype(str)
        if dates.empty or dates.isna().any() or (dates != as_of).any():
            raise DailyInputError(f"v6: candidate dates do not match {as_of}: {source}")
    directory = Path(feature_root) / f"v6-{stamp}"
    if directory.exists():
        request = load_feature_request(directory, generation="v6", as_of=as_of)
        manifest = json.loads((directory / "feature-manifest.json").read_text())
        recorded = {item["path"]: item["sha256"] for item in manifest.get("sources", [])}
        current = {str(path.resolve()): _sha256(path) for path in sources}
        if recorded != current or request.get("outcome_column") is not None:
            raise DailyInputError("v6: captured inputs changed; refusing to overwrite sealed matrix")
        return directory
    config = json.loads(Path(model_config).read_text())
    publish_v6_features(sources, directory, config, as_of)
    return directory
