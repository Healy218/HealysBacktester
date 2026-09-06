"""Tests for the v4 deployable-bundle loader."""
import json
from nn_meta.feature_contract import CONTRACT_VERSION

import joblib
import numpy as np
import pandas as pd
import pytest

from nn_meta.v4_artifacts import (ArtifactValidationError, create_manifest,
                                  write_manifest)
from nn_meta.v4_loader import (V4Bundle, ensemble_score, load_final_v4,
                               verify_bundle)


class FakeGBT:
    """Top-level so joblib/pickle can round-trip it through disk."""
    def __init__(self, value):
        self.value = value

    def predict_proba(self, x):
        p = np.full(len(x), self.value)
        return np.column_stack([1 - p, p])


FEATURES = ["rsi14", "macd_hist"]   # real, availability-declared v4 features


def _rows(n=4, features=FEATURES):
    return pd.DataFrame({f: np.arange(n, dtype="float32") for f in features})


def test_ensemble_score_averages_gbt_members():
    out = ensemble_score("gbt", [{"model": FakeGBT(0.2)}, {"model": FakeGBT(0.8)}],
                         _rows(), FEATURES)
    assert np.allclose(out, 0.5)


def test_ensemble_score_rejects_empty_and_unknown_family():
    with pytest.raises(ValueError, match="empty ensemble"):
        ensemble_score("gbt", [], _rows(), FEATURES)
    with pytest.raises(ValueError, match="unknown model family"):
        ensemble_score("svm", [{"model": FakeGBT(0.5)}], _rows(), FEATURES)


def _write_gbt_bundle(bundle_dir, values, features=FEATURES, *, threshold=0.5,
                      eligible=True, with_manifest=True, tmp_path=None):
    bundle_dir.mkdir(parents=True, exist_ok=True)
    run_ids = []
    artifacts = []
    for i, v in enumerate(values):
        run_id = f"v4-gbt-xs-s{i}"
        run_dir = bundle_dir / run_id
        run_dir.mkdir()
        joblib.dump(FakeGBT(v), run_dir / "model.joblib")
        (run_dir / "params.json").write_text("{}")
        run_ids.append(run_id)
        artifacts.append(run_dir / "model.joblib")
    cfg = {"feature_contract_version": CONTRACT_VERSION, "run_ids": run_ids, "family": "gbt", "mode": "rank",
           "threshold": threshold, "features": list(features),
           "eligible": eligible}
    (bundle_dir / "ensemble_config.json").write_text(json.dumps(cfg))
    artifacts.append(bundle_dir / "ensemble_config.json")
    if with_manifest and tmp_path is not None:
        dataset = tmp_path / "meta.parquet"
        pd.DataFrame({"symbol": ["SPY"]}).to_parquet(dataset)
        spec = tmp_path / "spec.json"
        spec.write_text("{}")
        manifest = create_manifest(dataset_path=dataset, baseline_spec_path=spec,
                                   feature_names=list(features), provider_metadata={},
                                   output_artifacts=artifacts)
        write_manifest(manifest, bundle_dir / "manifest.json")
    return bundle_dir


def test_load_and_score_gbt_bundle_roundtrip(tmp_path):
    bundle = _write_gbt_bundle(tmp_path / "model_final_v4", [0.3, 0.9],
                               threshold=0.55, tmp_path=tmp_path)
    loaded = load_final_v4(bundle)
    assert isinstance(loaded, V4Bundle)
    assert loaded.family == "gbt" and loaded.threshold == 0.55 and loaded.eligible
    scores = loaded.score(_rows())
    assert np.allclose(scores, 0.6)                     # mean of 0.3 and 0.9
    assert loaded.keep_mask(_rows()).all()              # 0.6 >= 0.55


def test_load_final_v4_fails_closed_on_missing_member(tmp_path):
    bundle = _write_gbt_bundle(tmp_path / "model_final_v4", [0.5],
                               with_manifest=False)
    import shutil
    shutil.rmtree(bundle / "v4-gbt-xs-s0")
    with pytest.raises(FileNotFoundError, match="member"):
        load_final_v4(bundle)


def test_load_final_v4_fails_when_bundle_absent(tmp_path):
    with pytest.raises(FileNotFoundError, match="ensemble_config"):
        load_final_v4(tmp_path / "nope")


def test_verify_bundle_passes_then_fails_on_tamper(tmp_path):
    bundle = _write_gbt_bundle(tmp_path / "model_final_v4", [0.4, 0.6],
                               tmp_path=tmp_path)
    assert verify_bundle(bundle)["output_artifacts"]         # clean bundle verifies
    (bundle / "ensemble_config.json").write_text('{"tampered": true}')
    with pytest.raises(ArtifactValidationError, match="hash mismatch"):
        verify_bundle(bundle)


def test_verify_bundle_requires_a_manifest(tmp_path):
    bundle = _write_gbt_bundle(tmp_path / "model_final_v4", [0.5],
                               with_manifest=False)
    with pytest.raises(ArtifactValidationError, match="missing"):
        verify_bundle(bundle)


def test_load_and_score_nn_bundle_roundtrip(tmp_path):
    # Exercises the real tf load path in _load_member (model.keras + scaler.json).
    from nn_meta import config
    from nn_meta.model import build_meta_mlp
    bundle = tmp_path / "model_final_v4"
    run_dir = bundle / "v4-nn-xs-s0"
    run_dir.mkdir(parents=True)
    model = build_meta_mlp(len(FEATURES), config.ARCHITECTURES[0], config.LEARNING_RATES[0])
    model.save(run_dir / "model.keras")
    (run_dir / "scaler.json").write_text(json.dumps(
        {"mean": {f: 0.0 for f in FEATURES}, "std": {f: 1.0 for f in FEATURES}}))
    (bundle / "ensemble_config.json").write_text(json.dumps(
        {"feature_contract_version": CONTRACT_VERSION, "run_ids": ["v4-nn-xs-s0"], "family": "nn", "mode": "filter",
         "threshold": 0.5, "features": FEATURES, "eligible": True}))

    loaded = load_final_v4(bundle)
    scores = loaded.score(_rows())
    assert scores.shape == (4,) and np.all((scores >= 0) & (scores <= 1))
