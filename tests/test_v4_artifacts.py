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
