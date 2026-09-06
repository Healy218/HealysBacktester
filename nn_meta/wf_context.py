"""Lightweight, shared provenance for prewarm and walk-forward checkpoints."""
import hashlib
import json

import pandas as pd

from nn_meta import config
from nn_meta.feature_contract import CONTRACT_VERSION
from nn_meta.v4_artifacts import sha256_file


def experiment_key(winning: dict, folds: int, membership: bool) -> str:
    """Content-address resume files; old fold-number-only artifacts are ignored."""
    inputs = [config.UNDERLYING_15M_PARQUET, config.SURFACE_DATASET_PARQUET,
              config.BASELINE_SPEC_JSON]
    # Provider labels depend on option quotes/prints as well as underlying
    # bars. Hash immutable raw cache contents, not filesystem mtimes.
    inputs += sorted(config.DATA_CACHE.rglob("*.parquet"))
    inputs += sorted(config.DATA_CACHE.rglob("*.json"))
    inputs = list(dict.fromkeys(inputs))
    if membership:
        from nn_meta.universe_pit import ARTIFACT_DIR
        inputs += sorted(ARTIFACT_DIR.glob("*.json"))
    payload = {"contract": CONTRACT_VERSION, "winning": winning, "folds": folds,
               "membership": membership,
               "config": {k: repr(v) for k, v in vars(config).items() if k.isupper()},
               "inputs": {str(p): sha256_file(p) if p.is_file() else None for p in inputs}}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:24]


def frame_digest(rows: pd.DataFrame) -> str:
    return hashlib.sha256(pd.util.hash_pandas_object(rows, index=True).to_numpy().tobytes()).hexdigest()
