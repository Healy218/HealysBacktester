import pandas as pd
import pytest

from nn_meta.v4_accounting import (AccountingDataError, CostScenario,
                                   mark_to_market_portfolio)


def _trades():
    return pd.DataFrame({
        "trade_id": ["a", "b"], "symbol": ["SPY", "QQQ"],
        "signal_ts": pd.to_datetime(["2025-01-02 14:30", "2025-01-03 14:30"]),
        "fill_entry_ts": pd.to_datetime(["2025-01-02 14:45", "2025-01-03 14:45"]),
        "fill_exit_ts": pd.to_datetime(["2025-01-03 14:30", "2025-01-04 14:30"]),
        "gross_return": [0.20, -0.10],
    })


def _marks():
    return pd.DataFrame({
        "trade_id": ["a", "a", "a", "b", "b"],
        "mark_ts": pd.to_datetime(["2025-01-02 14:45", "2025-01-03 12:00",
                                    "2025-01-03 14:30", "2025-01-03 14:45",
                                    "2025-01-04 14:30"]),
        "gross_return": [0.0, -0.10, 0.20, 0.0, -0.10],
    })


def test_mtm_marks_drawdown_before_exit_and_applies_costs():
    metrics, curve = mark_to_market_portfolio(
        _trades(), _marks(), max_concurrent=2, position_fraction=0.5,
        costs=CostScenario(name="zero", fee=0, slippage=0),
    )
    # SPY is marked down before its eventual gain: that drawdown is retained.
    assert metrics["max_drawdown"] > 0.04
    assert metrics["total_return"] == pytest.approx(0.045)
    assert curve["open_positions"].max() == 1
    assert metrics["turnover"] > 1.0


def test_cost_scenario_reduces_return():
    zero, _ = mark_to_market_portfolio(
        _trades(), _marks(), max_concurrent=2, position_fraction=0.5,
        costs=CostScenario(fee=0, slippage=0),
    )
    costly, _ = mark_to_market_portfolio(
        _trades(), _marks(), max_concurrent=2, position_fraction=0.5,
        costs=CostScenario(fee=0.01, slippage=0),
    )
    assert costly["total_return"] < zero["total_return"]


def test_missing_exit_mark_fails_closed():
    with pytest.raises(AccountingDataError, match="lacks an entry or exit mark"):
        mark_to_market_portfolio(
            _trades(), _marks().query("trade_id != 'b' or mark_ts < '2025-01-04'"),
            max_concurrent=2, position_fraction=0.5,
        )


def test_same_symbol_overlap_is_rejected():
    trades = _trades()
    trades.loc[1, "symbol"] = "SPY"
    trades.loc[1, "signal_ts"] = pd.Timestamp("2025-01-03 11:45")
    trades.loc[1, "fill_entry_ts"] = pd.Timestamp("2025-01-03 12:00")
    marks = _marks()
    marks.loc[(marks["trade_id"] == "b") &
              (marks["mark_ts"] == pd.Timestamp("2025-01-03 14:45")), "mark_ts"] = \
        pd.Timestamp("2025-01-03 12:00")
    with pytest.raises(AccountingDataError, match="overlapping SPY"):
        mark_to_market_portfolio(trades, marks, max_concurrent=2,
                                 position_fraction=0.5)
