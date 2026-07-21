import pandas as pd
import pytest

from nn_meta.v4_accounting import (AccountingDataError, CostScenario,
                                   DEFAULT_FILL_POLICY, FillFailure, FillPolicy,
                                   classify_quote, mark_to_market_portfolio,
                                   resolve_fills)


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


# ── fill-failure taxonomy ────────────────────────────────────────────────────

def test_classify_quote_accepts_a_tight_fresh_quote():
    assert classify_quote(1.00, 1.02) is None


def test_classify_quote_missing_bar_uses_the_supplied_reason():
    assert classify_quote(None, 1.0, missing=FillFailure.NO_ENTRY_BAR) is FillFailure.NO_ENTRY_BAR
    assert classify_quote(1.0, float("nan")) is FillFailure.NO_EXIT_BAR


def test_classify_quote_crossed_before_zero_bid():
    assert classify_quote(1.05, 1.00) is FillFailure.CROSSED_MARKET


def test_classify_quote_zero_bid():
    assert classify_quote(0.0, 1.00) is FillFailure.ZERO_BID


def test_classify_quote_stale():
    assert classify_quote(1.00, 1.02, quote_age=pd.Timedelta("30min")) is FillFailure.STALE_QUOTE
    assert classify_quote(1.00, 1.02, quote_age=pd.Timedelta("5min")) is None


def test_classify_quote_wide_spread():
    # 1.00/2.00 -> half-spread ~3333 bps, beyond the default 500 bps cap.
    assert classify_quote(1.00, 2.00) is FillFailure.WIDE_SPREAD
    loose = FillPolicy(max_half_spread_bps=5000.0)
    assert classify_quote(1.00, 2.00, policy=loose) is None


def _quotes():
    return pd.DataFrame({
        "trade_id": ["ok", "bad_entry", "bad_exit"],
        "entry_bid": [1.00, float("nan"), 1.00],
        "entry_ask": [1.02, 1.02, 1.02],
        "exit_bid": [1.50, 1.50, 0.0],
        "exit_ask": [1.52, 1.52, 1.52],
    })


def test_resolve_fills_rejects_entry_keeps_conservative_exit():
    fills, rejections = resolve_fills(_quotes())
    assert set(fills["trade_id"]) == {"ok", "bad_exit"}   # entry failure dropped
    ok = fills.set_index("trade_id").loc["ok"]
    assert ok["gross_return"] == pytest.approx(1.50 / 1.02 - 1.0)   # buy ask, sell bid
    bad_exit = fills.set_index("trade_id").loc["bad_exit"]
    assert bad_exit["gross_return"] == pytest.approx(-1.0)          # worst-case exit
    entry_rej = rejections.query("trade_id == 'bad_entry'").iloc[0]
    assert entry_rej["reason"] == FillFailure.NO_ENTRY_BAR.value and not entry_rej["conservative"]
    exit_rej = rejections.query("trade_id == 'bad_exit'").iloc[0]
    assert exit_rej["reason"] == FillFailure.ZERO_BID.value and exit_rej["conservative"]


def test_resolve_fills_intrinsic_policy_books_intrinsic_value():
    quotes = _quotes().query("trade_id == 'bad_exit'").assign(intrinsic=0.60)
    fills, _ = resolve_fills(quotes, policy=FillPolicy(missing_exit="intrinsic"))
    assert fills.iloc[0]["gross_return"] == pytest.approx(0.60 / 1.02 - 1.0)


def test_resolve_fills_requires_quote_columns():
    with pytest.raises(AccountingDataError, match="missing columns"):
        resolve_fills(pd.DataFrame({"trade_id": ["x"]}))


def test_fill_policy_rejects_unknown_missing_exit():
    with pytest.raises(ValueError, match="missing_exit"):
        FillPolicy(missing_exit="mid")
