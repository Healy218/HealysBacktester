"""Fail-closed discovery of verified incubator bundles."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from .bundles import BundleError, verify_bundle


def bundle_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover(roots: Iterable[Path], *, forward_data_contract: str = "paper_forward_v1") -> list[dict[str, Any]]:
    """Find and verify all bundles below roots, refusing any bad candidate."""
    candidates = sorted({path.resolve() for root in roots for path in root.rglob("*.tar.gz") if path.is_file()})
    entries: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for path in candidates:
        manifest = verify_bundle(path)
        artifact_id = manifest["artifact_id"]
        if artifact_id in seen_ids:
            raise BundleError(f"duplicate artifact_id discovered: {artifact_id}")
        if manifest["compatibility"].get("forward_data_contract") != forward_data_contract:
            raise BundleError(f"incompatible forward data contract: {artifact_id}")
        seen_ids.add(artifact_id)
        entries.append({
            "artifact_id": artifact_id,
            "artifact_version": manifest["artifact_version"],
            "artifact_kind": manifest["artifact_kind"],
            "bundle": str(path),
            "bundle_sha256": bundle_sha256(path),
            "manifest_sha256": manifest["manifest_sha256"],
            "compatibility": manifest["compatibility"],
        })
    return entries


def write_registry(entries: list[dict[str, Any]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"schema_version": 1, "artifacts": entries}, sort_keys=True, indent=2) + "\n")
