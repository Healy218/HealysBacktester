"""Read-only adapters for sealed paper-forward data snapshots."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


class ForwardDataError(ValueError):
    """Raised when forward data is missing, stale or tampered."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ForwardDataError(f"invalid JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ForwardDataError(f"JSON document must be an object: {path}")
    return value


@dataclass(frozen=True)
class ForwardSnapshot:
    root: Path
    through: str
    manifest_sha256: str
    manifest: dict[str, Any]

    @property
    def files(self) -> tuple[Path, ...]:
        return tuple(self.root / name for name in self.manifest["files"])

    def request(self, *, artifact_id: str, as_of: str | None = None) -> dict[str, Any]:
        """Return a serializable request without copying or mutating source data."""
        cutoff = as_of or self.through
        if cutoff > self.through:
            raise ForwardDataError(f"requested cutoff {cutoff} exceeds snapshot through {self.through}")
        request = {
            "schema": "paper-forward-request-v1",
            "artifact_id": artifact_id,
            "as_of": cutoff,
            "forward_data_contract": "paper_forward_v1",
            "snapshot_root": str(self.root),
            "snapshot_manifest_sha256": self.manifest_sha256,
            "snapshot_through": self.through,
            "read_only": True,
        }
        feature_matrix = self.manifest.get("feature_matrix")
        if isinstance(feature_matrix, dict):
            path = feature_matrix.get("path")
            columns = feature_matrix.get("feature_columns")
            outcome = feature_matrix.get("outcome_column")
            if (isinstance(path, str) and isinstance(columns, list) and columns
                    and all(isinstance(item, str) for item in columns)
                    and isinstance(outcome, str) and outcome not in columns):
                request.update(feature_path=path, feature_columns=columns,
                               outcome_column=outcome)
        return request


def load_v6_snapshot(index_path: Path, *, as_of: str | None = None, verify_files: bool = True) -> ForwardSnapshot:
    """Load and verify the immutable V6 forward-data pointer and snapshot."""
    index_path = index_path.resolve()
    index = _read_json(index_path)
    if index.get("schema") != "v6-forward-data-index-v1":
        raise ForwardDataError(f"unsupported V6 index schema: {index.get('schema')!r}")
    root = Path(index.get("path", "")).resolve()
    if not root.is_dir() or root == index_path.parent:
        raise ForwardDataError(f"forward snapshot root is unavailable: {root}")
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise ForwardDataError(f"forward snapshot has no manifest: {root}")
    manifest_digest = _sha256(manifest_path)
    if manifest_digest != index.get("sha256"):
        raise ForwardDataError("data-index manifest hash mismatch")
    manifest = _read_json(manifest_path)
    if manifest.get("schema") != "v6-forward-data-v1":
        raise ForwardDataError(f"unsupported V6 forward schema: {manifest.get('schema')!r}")
    through = manifest.get("through")
    if not isinstance(through, str):
        raise ForwardDataError("forward manifest has no through date")
    date.fromisoformat(through)
    if index.get("through") != through:
        raise ForwardDataError(f"data-index through {index.get('through')!r} disagrees with manifest through {through!r}")
    if as_of is not None:
        date.fromisoformat(as_of)
        if as_of > through:
            raise ForwardDataError(f"requested cutoff {as_of} exceeds snapshot through {through}")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise ForwardDataError("forward manifest has no file inventory")
    for relative, expected in files.items():
        path = (root / relative).resolve()
        if path.parent != root and root not in path.parents:
            raise ForwardDataError(f"unsafe forward file path: {relative}")
        if not path.is_file():
            raise ForwardDataError(f"forward file is missing: {relative}")
        if verify_files and _sha256(path) != expected:
            raise ForwardDataError(f"forward file hash mismatch: {relative}")
    return ForwardSnapshot(root=root, through=through, manifest_sha256=manifest_digest, manifest=manifest)
