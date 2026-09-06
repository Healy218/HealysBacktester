"""Local assumptions are reproducible context, never TradingView evidence."""
import pandas as pd
import pytest

from scripts.prepare_v6_local_context import local_context


def calendar():
    return {"timezone": "America/New_York", "sessions": [
        {"date": day, "open": "09:30", "close": close} for day, close in
        [("2025-07-01", "16:00"), ("2025-07-02", "16:00"),
         ("2025-07-03", "13:00"), ("2025-07-07", "16:00")]]}


def bars(dates):
    index = pd.DatetimeIndex([f"{day}T13:30:00Z" for day in dates])
    return pd.DataFrame({"Open": 100., "High": 101., "Low": 99., "Close": 100., "Volume": 100.}, index=index)


def test_calendar_pairs_do_not_shift_for_missing_sessions_or_holidays():
    days = ["2025-07-01", "2025-07-03", "2025-07-07"]
    data = bars([day for day in days for _ in range(2)])
    data.index = pd.DatetimeIndex([f"{day}T{time}Z" for day in days for time in ("13:30", "16:45")])
    flags, context = local_context(data, calendar(), symbol="SPY", minimum_tick=.01)
    assert flags.htf_change.tolist() == [True, False, True, False, False, False]
    assert flags.vwap_reset.tolist() == [True, False, True, False, True, False]
    assert flags.index.equals(data.index)
    assert flags.available_at.tolist() == data.index.tolist()
    assert context["dependency_metadata"]["external_context"] == "unverified-local-assumptions"
    prefix, _ = local_context(data.iloc[:4], calendar(), symbol="SPY", minimum_tick=.01)
    pd.testing.assert_frame_equal(prefix, flags.iloc[:4])


def test_daily_vwap_reset_and_early_close_are_explicit():
    data = bars(["2025-07-03", "2025-07-03"])
    data.index = pd.DatetimeIndex(["2025-07-03T13:30Z", "2025-07-03T16:45Z"])
    flags, _ = local_context(data, calendar(), symbol="SPY", minimum_tick=.01)
    assert flags.vwap_reset.tolist() == [True, False]
    data.index = pd.DatetimeIndex(["2025-07-03T13:30Z", "2025-07-03T17:00Z"])
    with pytest.raises(ValueError, match="outside calendar RTH"):
        local_context(data, calendar(), symbol="SPY", minimum_tick=.01)


def test_unknown_session_and_bad_calendar_are_rejected():
    with pytest.raises(ValueError, match="declared calendar session"):
        local_context(bars(["2025-07-04"]), calendar(), symbol="SPY", minimum_tick=.01)
    cal = calendar()
    cal["sessions"].reverse()
    with pytest.raises(ValueError, match="unique ordered"):
        local_context(bars(["2025-07-01"]), cal, symbol="SPY", minimum_tick=.01)


def test_sparse_ict_session_retains_literal_state_only_when_explicit():
    from v3.tv_ict_killzones import ict_killzones
    data = bars(["2025-07-01", "2025-07-02"])
    with pytest.raises(ValueError, match="missing outside-session"):
        ict_killzones(data)
    result = ict_killzones(data, strict_session_coverage=False)
    assert result.NYAM_session_gap.tolist() == [False, True]
    assert result.NYAM_session_start.tolist() == [True, False]
    flags, context = local_context(data, calendar(), symbol="SPY", minimum_tick=.01)
    assert '"NYAM": 1' in context["dependency_metadata"]["ict_session_gaps"]


def test_legacy_squeeze_is_identical_with_rich_context_attached():
    from nn_meta import proposals
    index = pd.date_range("2025-07-01", periods=100, freq="15min")
    data = pd.DataFrame({"Open": 100., "High": 101., "Low": 99., "Close": 100., "Volume": 100.}, index=index)
    expected = proposals.sweep_signals("squeeze", data)
    data.attrs["v6_tradingview_context"] = {"flags": pd.DataFrame({"flag": True}, index=index)}
    actual = proposals.sweep_signals("squeeze", data)
    for left, right in zip(actual, expected):
        if left is not None:
            pd.testing.assert_frame_equal(left, right)
    assert "v6_tradingview_context" in data.attrs


def test_symbol_without_train_history_is_ineligible_not_a_future_data_error():
    from nn_meta import baseline
    data = bars(["2026-07-01"])
    data.index = data.index.tz_localize(None)
    assert baseline.sweep_train_params("NEW", data, "ma", "2024-08-26", "2025-12-19") is None
