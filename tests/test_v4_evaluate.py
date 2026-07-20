"""Pure-policy tests for the V4 ablation evaluator."""
import numpy as np
import pandas as pd

from nn_meta.build_meta_dataset import META_FEATURES, V4_META_FEATURES
from nn_meta.v4_evaluate import choose_policy, schema_features


def _spec():
    return {"symbols": {"SPY": {"strategies": {"rsi": {"dte": 5}}}}}


def _rows():
    return pd.DataFrame({
        "symbol": ["SPY", "SPY", "SPY"], "strategy": ["rsi"] * 3,
        "trade_idx": [1, 1, 2], "dte": [5, 10, 5],
        "entry_ts": pd.to_datetime(["2025-01-02", "2025-01-02", "2025-01-03"]),
        "exit_ts": pd.to_datetime(["2025-01-02 15:00", "2025-01-02 15:00", "2025-01-03 15:00"]),
        "executed": [True, True, True], "net_return": [0.10, 0.80, -0.10],
        "n_fills": [2, 2, 2],
    })


def test_v4_schema_removes_only_execution_time_premium():
    assert schema_features("legacy") == META_FEATURES
    assert schema_features("v4") == V4_META_FEATURES
    assert "prem_spot" not in schema_features("v4")


def test_policy_selection_uses_the_shared_rank_portfolio():
    rows = _rows()
    policy = choose_policy(rows, np.array([0.8, 0.9, 0.1]), _spec(), thresholds=[0.5])
    assert policy["mode"] == "rank"
    assert policy["metrics"]["n_kept"] == 1
    assert policy["metrics"]["total_return"] > 0
