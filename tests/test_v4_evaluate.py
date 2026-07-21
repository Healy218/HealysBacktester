"""Pure-policy tests for the V4 ablation evaluator."""
import numpy as np
import pandas as pd

from nn_meta.build_meta_dataset import META_FEATURES, V4_META_FEATURES
from nn_meta.mark_stream import stable_trade_id
from nn_meta.v4_evaluate import choose_policy, marked_metrics, schema_features


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


def _marked_rows():
    return pd.DataFrame({
        "symbol": ["SPY", "QQQ"], "strategy": ["rsi", "rsi"],
        "trade_idx": [1, 2], "dte": [5, 5],
        "entry_ts": pd.to_datetime(["2025-01-02 14:30", "2025-01-03 14:30"]),
        "fill_entry_ts": pd.to_datetime(["2025-01-02 14:45", "2025-01-03 14:45"]),
        "exit_ts": pd.to_datetime(["2025-01-03 14:30", "2025-01-04 14:30"]),
        "fill_exit_ts": pd.to_datetime(["2025-01-03 14:30", "2025-01-04 14:30"]),
        "executed": [True, True], "net_return": [0.18, -0.12],
        "gross_return": [0.20, -0.10], "n_fills": [2, 2],
    })


def _marked_stream(rows):
    tid = stable_trade_id(rows).tolist()
    return pd.DataFrame({
        "trade_id": [tid[0], tid[0], tid[0], tid[1], tid[1]],
        "mark_ts": pd.to_datetime(["2025-01-02 14:45", "2025-01-03 12:00",
                                    "2025-01-03 14:30", "2025-01-03 14:45",
                                    "2025-01-04 14:30"]),
        "gross_return": [0.0, -0.10, 0.20, 0.0, -0.10],
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


def test_marked_metrics_routes_entered_trades_through_the_ledger():
    rows = _marked_rows()
    metrics = marked_metrics(rows, np.array([0.9, 0.9]), "rank", 0.5,
                             _marked_stream(rows))
    # Both distinct-symbol trades enter; the ledger re-derives P&L from marks.
    assert metrics is not None
    assert metrics["n_positions"] == 2
    assert metrics["max_drawdown"] > 0.0


def test_marked_metrics_returns_none_when_nothing_is_entered():
    rows = _marked_rows()
    assert marked_metrics(rows, np.array([0.1, 0.1]), "rank", 0.5,
                          _marked_stream(rows)) is None
