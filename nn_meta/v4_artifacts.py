"""Immutable, verifiable metadata for V4 research artifacts.

The manifest deliberately records hashes and coverage, not the multi-gigabyte
market cache.  It can therefore travel with a v31 result bundle and fail
closed if a dataset, baseline specification, or feature contract changes.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path
from typing import Iterable

import pandas as pd

from nn_meta.feature_contract import CONTRACT_VERSION, manifest as feature_manifest


class ArtifactValidationError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_revision(root: Path | None = None) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def dataset_coverage(dataset: pd.DataFrame) -> dict:
    """Small JSON-safe coverage report; absent optional columns stay absent."""
    out = {"rows": int(len(dataset)), "columns": sorted(map(str, dataset.columns))}
    for col in ("symbol", "strategy", "contract"):
        if col in dataset:
            out[f"unique_{col}s"] = int(dataset[col].nunique(dropna=True))
    for col in ("entry_ts", "exit_ts"):
        if col in dataset and dataset[col].notna().any():
            ts = pd.to_datetime(dataset[col])
            out[f"{col}_min"] = ts.min().isoformat()
            out[f"{col}_max"] = ts.max().isoformat()
    if "executed" in dataset:
        out["executed_rows"] = int(dataset["executed"].fillna(False).sum())
    return out


def create_manifest(*, dataset_path: Path, baseline_spec_path: Path,
                    feature_names: Iterable[str], provider_metadata: dict,
                    config_hash: str | None = None, code_root: Path | None = None,
                    output_artifacts: Iterable[Path] | None = None,
                    mark_stream_path: Path | None = None,
                    evaluation_config: dict | None = None) -> dict:
    """Build a manifest from the exact input files used for an experiment.

    ``output_artifacts`` optionally extends the integrity envelope to files
    the experiment PRODUCED (trained models, an ensemble config) — so a
    persisted bundle's manifest covers what it ships, not only its inputs.
    Paths are stored relative to their common parent when they share one
    (a model bundle directory), else by name.
    """
    dataset_path, baseline_spec_path = Path(dataset_path), Path(baseline_spec_path)
    if not dataset_path.exists() or not baseline_spec_path.exists():
        raise ArtifactValidationError("dataset and baseline spec must both exist")
    spec = json.loads(baseline_spec_path.read_text())
    ds = pd.read_parquet(dataset_path)
    manifest = {
        "manifest_version": 2,
        "feature_contract_version": CONTRACT_VERSION,
        "evaluation_config": evaluation_config or {},
        "code_revision": git_revision(code_root),
        "config_hash": config_hash or spec.get("config_hash"),
        "dataset": {"path": dataset_path.name, "sha256": sha256_file(dataset_path),
                    "coverage": dataset_coverage(ds)},
        "baseline_spec": {"path": baseline_spec_path.name,
                          "sha256": sha256_file(baseline_spec_path)},
        "feature_schema": feature_manifest(feature_names),
        "provider_metadata": provider_metadata,
    }
    if mark_stream_path is not None:
        manifest["mark_stream"] = {"path": Path(mark_stream_path).name,
                                   "sha256": sha256_file(Path(mark_stream_path))}
    if output_artifacts is not None:
        paths = [Path(p) for p in output_artifacts]
        missing = [str(p) for p in paths if not p.is_file()]
        if missing:
            raise ArtifactValidationError(f"cannot hash missing artifacts: {missing}")
        base = _common_base(paths)
        manifest["output_artifacts"] = {
            (str(p.relative_to(base)) if base else p.name): sha256_file(p)
            for p in sorted(paths)
        }
    return manifest


def _common_base(paths: list[Path]) -> Path | None:
    """Deepest directory containing every path, or None if they don't share one."""
    try:
        import os
        common = os.path.commonpath([str(p) for p in paths])
    except ValueError:  # mixed drives / empty
        return None
    base = Path(common)
    return base if base.is_dir() else base.parent


def write_manifest(manifest: dict, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return path


def validate_manifest(manifest_path: Path, *, dataset_path: Path,
                      baseline_spec_path: Path, feature_names: Iterable[str],
                      mark_stream_path: Path | None = None) -> dict:
    """Fail closed when the manifest's files or ordered feature schema differ."""
    data = json.loads(Path(manifest_path).read_text())
    if data.get("feature_contract_version") != CONTRACT_VERSION:
        raise ArtifactValidationError("stale feature contract; rebuild artifacts")
    if data.get("mark_stream") is not None or mark_stream_path is not None:
        if mark_stream_path is None or data.get("mark_stream", {}).get("sha256") != sha256_file(mark_stream_path):
            raise ArtifactValidationError("mark stream hash does not match its manifest")
    for key, path in (("dataset", dataset_path), ("baseline_spec", baseline_spec_path)):
        actual = sha256_file(Path(path))
        if data.get(key, {}).get("sha256") != actual:
            raise ArtifactValidationError(f"{key} hash does not match its manifest")
    expected = feature_manifest(feature_names)
    if data.get("feature_schema") != expected:
        raise ArtifactValidationError("feature schema does not match its manifest")
    return data


def write_metadata_bundle(output: Path, *, manifest_path: Path,
                          baseline_spec_path: Path, reports: Iterable[Path] = ()) -> Path:
    """Create a portable zip containing metadata, never raw market data."""
    files = [Path(manifest_path), Path(baseline_spec_path), *map(Path, reports)]
    missing = [str(path) for path in files if not path.exists()]
    if missing:
        raise ArtifactValidationError(f"cannot bundle missing files: {missing}")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, arcname=path.name)
    return output
