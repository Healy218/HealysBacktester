"""Immutable, point-in-time capture of a model-compatible feature matrix."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


class FeatureCaptureError(ValueError):
    """Raised when a feature matrix cannot be captured without guessing."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_files(sources: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for source in sources:
        source = Path(source).resolve()
        if source.is_file() and source.suffix == ".parquet":
            files.append(source)
        elif source.is_dir():
            files.extend(sorted(source.rglob("*.parquet")))
        else:
            raise FeatureCaptureError(f"feature source is unavailable: {source}")
    unique = sorted(set(files))
    if not unique:
        raise FeatureCaptureError("no parquet feature sources were supplied")
    return unique


def _load_contract(config: Path | dict[str, Any]) -> list[str]:
    document = json.loads(Path(config).read_text()) if isinstance(config, (str, Path)) else config
    features = document.get("features") if isinstance(document, dict) else None
    if not isinstance(features, list) or not features or not all(isinstance(x, str) and x for x in features):
        raise FeatureCaptureError("model config has no valid feature contract")
    if len(set(features)) != len(features):
        raise FeatureCaptureError("model feature contract contains duplicates")
    return features


def capture_feature_matrix(sources: Iterable[Path], output_dir: Path,
                           model_config: Path | dict[str, Any], through: str,
                           outcome_column: str = "net_return",
                           max_rows: int | None = None) -> dict[str, Any]:
    """Capture only rows whose decision date is on or before ``through``.

    The source must already contain the model features. This function performs
    selection, validation and immutable publication; it deliberately does not
    synthesize missing technical, surface or option features.
    """
    try:
        cutoff = pd.Timestamp(date.fromisoformat(through)).normalize()
    except ValueError as exc:
        raise FeatureCaptureError("through must be YYYY-MM-DD") from exc
    features = _load_contract(model_config)
    if not isinstance(outcome_column, str) or not outcome_column or outcome_column in features:
        raise FeatureCaptureError("outcome_column must be separate from model features")
    files = _source_files(sources)
    needed = set(features) | {outcome_column}
    frames: list[pd.DataFrame] = []
    source_rows = 0
    dropped_missing_outcome = 0
    dropped_incomplete_features = 0
    derived_columns: set[str] = set()
    for path in files:
        columns = pd.read_parquet(path, engine="pyarrow").columns
        date_column = next((name for name in ("entry_date", "date", "entry_ts") if name in columns), None)
        if date_column is None:
            raise FeatureCaptureError(f"{path}: no point-in-time date column")
        missing = sorted(needed - set(columns))
        derived = [name for name in missing if name.startswith("strat_")]
        unresolved = sorted(set(missing) - set(derived))
        if derived and "strategy" not in columns:
            unresolved = sorted(set(unresolved) | set(derived))
        if unresolved:
            raise FeatureCaptureError(f"{path}: missing {len(unresolved)} model columns: {unresolved}")
        read_columns = [date_column, *(name for name in features if name not in derived), outcome_column]
        if derived:
            read_columns.append("strategy")
        frame = pd.read_parquet(path, columns=list(dict.fromkeys(read_columns)))
        for name in derived:
            frame[name] = (frame["strategy"].astype(str) == name.removeprefix("strat_")).astype(float)
            derived_columns.add(name)
        source_rows += len(frame)
        dates = pd.to_datetime(frame[date_column], errors="coerce").dt.tz_localize(None).dt.normalize()
        if dates.isna().any():
            raise FeatureCaptureError(f"{path}: invalid point-in-time dates")
        frame = frame.loc[dates <= cutoff].copy()
        eligible = frame[outcome_column].notna()
        dropped_missing_outcome += int((~eligible).sum())
        frame = frame.loc[eligible]
        numeric = frame[features].apply(pd.to_numeric, errors="coerce")
        complete = numeric.notna().all(axis=1)
        dropped_incomplete_features += int((~complete).sum())
        frame = frame.loc[complete]
        if frame.empty:
            continue
        frame["entry_date"] = dates.loc[frame.index].to_numpy()
        frames.append(frame[["entry_date", *features, outcome_column]])
    result = pd.concat(frames, ignore_index=True)
    if result.empty:
        raise FeatureCaptureError("no rows remain at or before through")
    # Identical feature/outcome values can belong to distinct trades (for
    # example, two contracts sharing the same decision bar). Their identity is
    # outside the replay contract, so do not collapse or reject them here.
    values = result[features + [outcome_column]].apply(pd.to_numeric, errors="coerce")
    if values.isna().any().any() or not np.isfinite(values.to_numpy(dtype=float)).all():
        raise FeatureCaptureError("feature capture contains missing or non-finite values")
    result[features + [outcome_column]] = values.astype(float)
    result = result.sort_values("entry_date", kind="stable").reset_index(drop=True)
    if max_rows is not None:
        if max_rows <= 0:
            raise FeatureCaptureError("max_rows must be positive")
        result = result.iloc[:max_rows].copy()

    output_dir = Path(output_dir).resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FeatureCaptureError("output directory must be new and empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    matrix = output_dir / "features.parquet"
    temp = output_dir / "features.parquet.tmp"
    result.to_parquet(temp, index=False)
    temp.replace(matrix)
    manifest = {
        "schema": "incubator-feature-matrix-v1",
        "through": through,
        "feature_columns": features,
        "outcome_column": outcome_column,
        "rows": len(result),
        "max_rows": max_rows,
        "source_rows": source_rows,
        "dropped_missing_outcome": dropped_missing_outcome,
        "dropped_incomplete_features": dropped_incomplete_features,
        "derived_columns": sorted(derived_columns),
        "sources": [{"path": str(path), "sha256": _sha256(path)} for path in files],
        "files": {"features.parquet": _sha256(matrix)},
    }
    manifest_path = output_dir / "feature-manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    return manifest
