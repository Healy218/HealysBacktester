import json

import pandas as pd

from nn_meta.v4_preflight import check_environment


def test_preflight_reports_missing_and_complete_schema(tmp_path):
    missing = check_environment(tmp_path / "no.parquet", tmp_path / "no.json", require_gbt=False)
    assert not missing["ok"]
    from nn_meta.build_meta_dataset import V4_META_FEATURES
    ds = pd.DataFrame([{**{feature: 0.0 for feature in V4_META_FEATURES},
                        "entry_ts": "2025-01-01", "exit_ts": "2025-01-02",
                        "executed": True, "net_return": 0.1}])
    dataset, spec = tmp_path / "dataset.parquet", tmp_path / "spec.json"
    ds.to_parquet(dataset)
    spec.write_text(json.dumps({"symbols": {}}))
    complete = check_environment(dataset, spec, require_gbt=False)
    assert complete["ok"]
