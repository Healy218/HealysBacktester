"""Pure-policy tests for the V4 ablation evaluator."""
import numpy as np
import pandas as pd

from nn_meta.build_meta_dataset import META_FEATURES, V4_META_FEATURES
from nn_meta.mark_stream import stable_trade_id
from nn_meta.v4_evaluate import (choose_policy, marked_metrics, schema_features,
                                 _policy_rank, _select_winner)


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


def test_choose_policy_flags_gate_failures_as_ineligible():
    # Only 3 rows -> n_kept < MIN_KEPT_TRADES, so no candidate can clear the
    # gate. choose_policy must still return a winner (callers need something to
    # report), but it has to be marked ineligible, not silently promoted.
    rows = _rows()
    policy = choose_policy(rows, np.array([0.8, 0.9, 0.1]), _spec(), thresholds=[0.5])
    assert policy["eligible"] is False


def _policy(family, total_return, eligible):
    return {"family": family, "metrics": {"total_return": total_return},
            "eligible": eligible}


def test_select_winner_prefers_eligible_over_higher_return():
    # An ineligible family with a much higher raw return must NOT beat an
    # eligible one — this is the fold-selection half of the -26.3% "winner" bug.
    eligible = _policy("gbt", 0.30, True)
    flashy_but_failing = _policy("nn", 0.90, False)
    assert _select_winner([flashy_but_failing, eligible]) is eligible


def test_select_winner_falls_back_to_best_return_when_all_ineligible():
    a = _policy("gbt", -0.26, False)
    b = _policy("nn", -0.40, False)
    winner = _select_winner([a, b])
    assert winner is a and winner["eligible"] is False


def test_policy_rank_orders_eligible_first_then_by_return():
    assert _policy_rank(_policy("x", 0.1, True)) > _policy_rank(_policy("x", 9.9, False))
    assert _policy_rank(_policy("x", 0.5, True)) > _policy_rank(_policy("x", 0.2, True))
    # None return sorts to the very bottom, not crashes.
    assert _policy_rank(_policy("x", None, False))[1] == float("-inf")
