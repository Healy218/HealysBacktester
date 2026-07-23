# nn_meta/v4_loader.py
"""Load and score a persisted v4 deployable bundle (``model_final_v4/``).

The bundle layout and scoring convention are produced by ``v4_finalize.py``:

    ensemble_config.json   family, mode, threshold, features, run_ids, eligible
    <run_id>/model.keras + scaler.json + params.json   (nn members)
    <run_id>/model.joblib + params.json                (gbt members)

Before this module the scoring convention lived ONLY inside ``v4_evaluate``'s
source, and the one existing loader (``select_meta.predict_rows``) hard-indexed
the legacy ``META_FEATURES`` (incl. ``prem_spot``) and only understood NN
``model.keras`` bundles — so nothing in the repo could actually read a v4 GBT
bundle. This is the single reader that speaks the v4 contract, reused by the
stage-5 live parity path.

Scoring convention (must match ``v4_evaluate``/``v4_finalize`` exactly):

    nn : fillna(train-mean) + standardize by the member's scaler -> model.predict
    gbt: raw features -> predict_proba[:, 1]

then average across the ensemble's seeds. The bundle carries no ``prem_spot``;
its feature list is ``V4_META_FEATURES``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from nn_meta import config
from nn_meta.v4_artifacts import ArtifactValidationError, sha256_file
from nn_meta.v4_evaluate import _matrix

FINAL_DIR = config.ROOT / "model_final_v4"


def ensemble_score(family: str, members: list[dict], rows: pd.DataFrame,
                   features: list[str]) -> np.ndarray:
    """Mean P(win) across ensemble members — the canonical v4 scoring path.

    ``members`` are dicts with a ``model`` (a fitted Keras model for nn, a
    fitted LightGBM classifier for gbt) and, for nn, the ``mean``/``std``
    Series of its training scaler. Shared by ``v4_finalize`` (in-memory,
    just-trained members) and ``load_final_v4`` (members read from disk) so
    the deployed score can never drift from the score the gate approved.
    """
    if not members:
        raise ValueError("cannot score with an empty ensemble")
    if family == "nn":
        preds = [m["model"].predict(_matrix(rows, features, m["mean"], m["std"]),
                                    batch_size=4096, verbose=0).flatten()
                 for m in members]
    elif family == "gbt":
        preds = [m["model"].predict_proba(rows[features])[:, 1] for m in members]
    else:
        raise ValueError(f"unknown model family '{family}'")
    return np.mean(preds, axis=0)


@dataclass
class V4Bundle:
    """A loaded, ready-to-score v4 ensemble."""
    family: str
    mode: str
    threshold: float
    features: list[str]
    eligible: bool
    members: list[dict]
    config: dict

    def score(self, rows: pd.DataFrame) -> np.ndarray:
        """P(win) for each row, averaged over the ensemble."""
        return ensemble_score(self.family, self.members, rows, self.features)

    def keep_mask(self, rows: pd.DataFrame) -> np.ndarray:
        """Boolean mask of rows the bundle would keep at its own threshold."""
        return self.score(rows) >= self.threshold


def _load_member(family: str, run_dir: Path) -> dict:
    if family == "nn":
        import tensorflow as tf
        scaler = json.loads((run_dir / "scaler.json").read_text())
        model = tf.keras.models.load_model(run_dir / "model.keras")
        return {"model": model,
                "mean": pd.Series(scaler["mean"]), "std": pd.Series(scaler["std"])}
    if family == "gbt":
        import joblib
        return {"model": joblib.load(run_dir / "model.joblib")}
    raise ValueError(f"unknown model family '{family}'")


def load_final_v4(bundle_dir: Path | None = None) -> V4Bundle:
    """Read ``ensemble_config.json`` and every seed's model into a V4Bundle.

    Raises ``FileNotFoundError`` if the bundle or any member file is absent —
    fail closed rather than score with a partial ensemble.
    """
    bundle_dir = Path(bundle_dir) if bundle_dir is not None else FINAL_DIR
    cfg_path = bundle_dir / "ensemble_config.json"
    if not cfg_path.exists():
        raise FileNotFoundError(
            f"{cfg_path} missing — run nn_meta.v4_finalize to build the bundle.")
    cfg = json.loads(cfg_path.read_text())
    family = cfg["family"]
    members = []
    for run_id in cfg["run_ids"]:
        run_dir = bundle_dir / run_id
        if not run_dir.is_dir():
            raise FileNotFoundError(f"bundle member {run_id} missing at {run_dir}")
        members.append(_load_member(family, run_dir))
    return V4Bundle(
        family=family, mode=cfg["mode"], threshold=float(cfg["threshold"]),
        features=list(cfg["features"]), eligible=bool(cfg.get("eligible", False)),
        members=members, config=cfg)


def verify_bundle(bundle_dir: Path | None = None) -> dict:
    """Recompute the trained-artifact hashes recorded in ``manifest.json`` and
    fail closed on any mismatch — a truncated or swapped model file must not be
    scored silently. Only checks ``output_artifacts`` (the bundle's own files);
    the dataset/baseline hashes reference inputs a deployed host may not carry.

    Returns the manifest on success.
    """
    bundle_dir = Path(bundle_dir) if bundle_dir is not None else FINAL_DIR
    manifest_path = bundle_dir / "manifest.json"
    if not manifest_path.exists():
        raise ArtifactValidationError(f"{manifest_path} missing — cannot verify bundle")
    manifest = json.loads(manifest_path.read_text())
    artifacts = manifest.get("output_artifacts")
    if not artifacts:
        raise ArtifactValidationError(
            "manifest records no output_artifacts — bundle predates hashed persistence")
    for rel, expected in artifacts.items():
        path = bundle_dir / rel
        if not path.is_file():
            raise ArtifactValidationError(f"bundle artifact missing: {rel}")
        if sha256_file(path) != expected:
            raise ArtifactValidationError(f"bundle artifact hash mismatch: {rel}")
    return manifest
