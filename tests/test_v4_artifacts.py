import json

import pandas as pd
import pytest

from nn_meta.v4_artifacts import (ArtifactValidationError, create_manifest,
                                  validate_manifest, write_manifest,
                                  write_metadata_bundle)


def test_manifest_hashes_schema_and_metadata_bundle(tmp_path):
    dataset = tmp_path / "meta.parquet"
    pd.DataFrame({"symbol": ["SPY"], "entry_ts": ["2025-01-02"],
                  "exit_ts": ["2025-01-03"], "executed": [True]}).to_parquet(dataset)
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"config_hash": "abc"}))
    data = create_manifest(dataset_path=dataset, baseline_spec_path=spec,
                           feature_names=["rsi14"], provider_metadata={"name": "test"},
                           code_root=tmp_path)
    path = write_manifest(data, tmp_path / "manifest.json")
    assert validate_manifest(path, dataset_path=dataset, baseline_spec_path=spec,
                             feature_names=["rsi14"])["config_hash"] == "abc"
    bundle = write_metadata_bundle(tmp_path / "bundle.zip", manifest_path=path,
                                   baseline_spec_path=spec)
    assert bundle.exists()


def test_manifest_records_output_artifact_hashes(tmp_path):
    dataset = tmp_path / "meta.parquet"
    pd.DataFrame({"symbol": ["SPY"]}).to_parquet(dataset)
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"config_hash": "abc"}))
    bundle = tmp_path / "model_final_v4"
    (bundle / "seed0").mkdir(parents=True)
    (bundle / "seed0" / "model.joblib").write_bytes(b"weights")
    (bundle / "ensemble_config.json").write_text('{"mode": "rank"}')
    artifacts = [bundle / "seed0" / "model.joblib", bundle / "ensemble_config.json"]

    data = create_manifest(dataset_path=dataset, baseline_spec_path=spec,
                           feature_names=["rsi14"], provider_metadata={},
                           output_artifacts=artifacts)
    recorded = data["output_artifacts"]
    # keyed by path relative to the shared bundle dir, covering trained model
    # AND the ensemble config — not just the inputs
    assert set(recorded) == {"seed0/model.joblib", "ensemble_config.json"}
    assert all(len(h) == 64 for h in recorded.values())


def test_manifest_output_artifacts_must_exist(tmp_path):
    dataset = tmp_path / "meta.parquet"
    pd.DataFrame({"symbol": ["SPY"]}).to_parquet(dataset)
    spec = tmp_path / "spec.json"
    spec.write_text("{}")
    with pytest.raises(ArtifactValidationError, match="missing artifacts"):
        create_manifest(dataset_path=dataset, baseline_spec_path=spec,
                        feature_names=["rsi14"], provider_metadata={},
                        output_artifacts=[tmp_path / "does_not_exist.keras"])


def test_manifest_fails_when_inputs_change(tmp_path):
    dataset = tmp_path / "meta.parquet"
    pd.DataFrame({"symbol": ["SPY"]}).to_parquet(dataset)
    spec = tmp_path / "spec.json"
    spec.write_text("{}")
    path = write_manifest(create_manifest(dataset_path=dataset, baseline_spec_path=spec,
                                          feature_names=["rsi14"], provider_metadata={}),
                          tmp_path / "manifest.json")
    spec.write_text('{"changed": true}')
    with pytest.raises(ArtifactValidationError, match="hash"):
        validate_manifest(path, dataset_path=dataset, baseline_spec_path=spec,
                          feature_names=["rsi14"])
