"""Immutable artifact bundle creation and verification.

The incubator deliberately treats model bundles as opaque until their
manifest, file inventory and compatibility declaration pass verification.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Mapping


SCHEMA_VERSION = 1
_ARTIFACT_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{1,95}$")


class BundleError(ValueError):
    """Raised when an artifact bundle cannot be admitted."""


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_member(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise BundleError(f"unsafe bundle member: {name!r}")
    return path


def _validate_manifest(manifest: Mapping[str, Any]) -> None:
    required = {
        "schema_version",
        "artifact_id",
        "artifact_version",
        "artifact_kind",
        "created_at",
        "compatibility",
        "files",
    }
    missing = sorted(required - set(manifest))
    if missing:
        raise BundleError(f"manifest missing fields: {', '.join(missing)}")
    if manifest["schema_version"] != SCHEMA_VERSION:
        raise BundleError(f"unsupported manifest schema: {manifest['schema_version']!r}")
    artifact_id = manifest["artifact_id"]
    if not isinstance(artifact_id, str) or not _ARTIFACT_ID.fullmatch(artifact_id):
        raise BundleError(f"invalid artifact_id: {artifact_id!r}")
    if not isinstance(manifest["compatibility"], dict):
        raise BundleError("compatibility must be an object")
    if "entrypoint" in manifest:
        entrypoint = manifest["entrypoint"]
        if not isinstance(entrypoint, list) or not entrypoint or not all(isinstance(item, str) and item for item in entrypoint):
            raise BundleError("entrypoint must be a non-empty string list")
        _relative_member(entrypoint[0])
    files = manifest["files"]
    if not isinstance(files, list) or not files:
        raise BundleError("manifest files must be a non-empty list")
    seen: set[str] = set()
    for item in files:
        if not isinstance(item, dict) or set(item) != {"path", "size", "sha256"}:
            raise BundleError("each manifest file must contain path, size and sha256")
        path = str(_relative_member(item["path"]))
        if path == "manifest.json" or path in seen:
            raise BundleError(f"invalid or duplicate manifest file: {path}")
        seen.add(path)
        if not isinstance(item["size"], int) or item["size"] < 0:
            raise BundleError(f"invalid size for {path}")
        if not isinstance(item["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise BundleError(f"invalid sha256 for {path}")


def _manifest_without_digest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(manifest)
    result.pop("manifest_sha256", None)
    return result


def manifest_digest(manifest: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_json(_manifest_without_digest(manifest)))


def _inventory(root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            if path.is_symlink():
                raise BundleError(f"symlinks are not allowed in artifact source: {path}")
            continue
        relative = path.relative_to(root).as_posix()
        if relative == "manifest.json":
            continue
        entries.append({"path": relative, "size": path.stat().st_size, "sha256": sha256_file(path)})
    return entries


def create_manifest(source_dir: Path, *, artifact_id: str, artifact_version: str,
                    artifact_kind: str, created_at: str,
                    compatibility: Mapping[str, Any],
                    metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source_dir = source_dir.resolve()
    if not source_dir.is_dir():
        raise BundleError(f"artifact source is not a directory: {source_dir}")
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "artifact_id": artifact_id,
        "artifact_version": artifact_version,
        "artifact_kind": artifact_kind,
        "created_at": created_at,
        "compatibility": dict(compatibility),
        "files": _inventory(source_dir),
        "read_only": True,
    }
    if metadata:
        manifest["metadata"] = dict(metadata)
    _validate_manifest(manifest)
    manifest["manifest_sha256"] = manifest_digest(manifest)
    return manifest


def pack_directory(source_dir: Path, output_bundle: Path, *, manifest: Mapping[str, Any]) -> Path:
    """Write a gzip tar bundle without modifying ``source_dir``."""
    _validate_manifest(manifest)
    source_dir = source_dir.resolve()
    output_bundle = output_bundle.resolve()
    output_bundle.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="incubator-pack-") as temp_name:
        staging = Path(temp_name) / "artifact"
        shutil.copytree(source_dir, staging, symlinks=False)
        (staging / "manifest.json").write_bytes(canonical_json(dict(manifest)))
        with tarfile.open(output_bundle, "w:gz") as archive:
            for path in sorted(staging.rglob("*")):
                if path.is_file():
                    archive.add(path, arcname=path.relative_to(staging).as_posix(), recursive=False)
    return output_bundle


def _safe_extract(archive: tarfile.TarFile, destination: Path) -> set[str]:
    members = archive.getmembers()
    names: set[str] = set()
    for member in members:
        relative = _relative_member(member.name)
        name = str(relative)
        if name in names:
            raise BundleError(f"duplicate bundle member: {name}")
        names.add(name)
        if member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
            raise BundleError(f"unsupported bundle member type: {name}")
        archive.extractall(destination, members=members, filter="data")
    return names


def verify_bundle(bundle: Path, *, expected_artifact_id: str | None = None) -> dict[str, Any]:
    """Verify and return a manifest; never executes bundle contents."""
    bundle = bundle.resolve()
    if not bundle.is_file():
        raise BundleError(f"bundle does not exist: {bundle}")
    with tempfile.TemporaryDirectory(prefix="incubator-verify-") as temp_name:
        root = Path(temp_name)
        with tarfile.open(bundle, "r:gz") as archive:
            names = _safe_extract(archive, root)
        if "manifest.json" not in names:
            raise BundleError("bundle has no manifest.json")
        try:
            manifest = json.loads((root / "manifest.json").read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise BundleError(f"invalid manifest.json: {exc}") from exc
        if not isinstance(manifest, dict):
            raise BundleError("manifest.json must contain an object")
        _validate_manifest(manifest)
        if manifest.get("manifest_sha256") != manifest_digest(manifest):
            raise BundleError("manifest digest mismatch")
        if expected_artifact_id and manifest["artifact_id"] != expected_artifact_id:
            raise BundleError("artifact_id does not match expected id")
        expected = {item["path"]: item for item in manifest["files"]}
        actual = names - {"manifest.json"}
        if actual != set(expected):
            raise BundleError(f"bundle inventory mismatch: missing={sorted(set(expected) - actual)}, extra={sorted(actual - set(expected))}")
        for name, item in expected.items():
            path = root / name
            if path.stat().st_size != item["size"] or sha256_file(path) != item["sha256"]:
                raise BundleError(f"file digest mismatch: {name}")
        return manifest
