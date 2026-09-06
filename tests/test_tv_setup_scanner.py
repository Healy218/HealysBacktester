"""Known source state/priority cases; external Pine fixtures remain required."""
import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from signals.tv_setup_scanner_signals import generate_setup_scanner_signals
from v3.tv_setup_scanner import SETUPS, SetupTradeBook, setup_scanner


def signals(*ids):
    return np.array([i in ids for i in range(6)])


def step(book, i, high=101, low=99, close=100, longs=(), shorts=(), **kwargs):
    return book.step(i, high, low, close, 1., signals(*longs), signals(*shorts), **kwargs)


def test_fixed_priority_counts_accepted_entries_and_does_not_resolve_entry_bar():
    book = SetupTradeBook()
    entries, exits, outcomes = step(book, 0, high=110, low=90, longs=(0, 5))
    assert entries[:, 0].tolist() == [True, False, False, False, False, False]
    assert not exits.any() and not outcomes
    assert book.counters[:, 0].tolist() == [1, 0, 0, 0, 0, 0]
    assert len(book.trades) == 1 and not book.trades[0].done


def test_same_bar_stop_wins_and_zero_cooldown_can_reenter_after_resolution():
    book = SetupTradeBook()
    step(book, 0, longs=(0,))
    entries, exits, outcomes = step(book, 1, high=110, low=90, longs=(5,))
    assert exits[0, 0] and entries[5, 0]
    assert outcomes == ((0, 1, "stop", 0, True),)
    assert book.counters[0].tolist() == [1, 0, 0, 0, 1, 0]
    assert book.last_close_bar == 1
    blocked = SetupTradeBook()
    step(blocked, 0, longs=(0,))
    assert not step(blocked, 1, high=110, low=90, longs=(5,), reentry=1)[0].any()


def test_targets_update_on_observation_and_later_stop_is_not_stop_before_tp1():
    book = SetupTradeBook()
    step(book, 0, longs=(2,))
    step(book, 1, high=101.3, low=99.5)
    assert book.trades[0].stage == 1
    assert book.counters[2].tolist() == [1, 1, 0, 0, 0, 0]
    _, exits, outcomes = step(book, 2, high=101, low=98)
    assert exits[2, 0] and outcomes[0][2] == "stop"
    assert book.counters[2, 4] == 0


def test_expiry_is_inclusive_and_target_three_has_priority_over_expiry():
    book = SetupTradeBook()
    step(book, 0, longs=(3,))
    assert not step(book, 4, high=100.5, low=99.5, max_bars=5)[1].any()
    assert step(book, 5, high=100.5, low=99.5, max_bars=5)[2][0][2] == "expired"
    assert book.counters[3, 5] == 1
    other = SetupTradeBook()
    step(other, 0, longs=(1,))
    assert step(other, 5, high=104, low=99.5, max_bars=5)[2][0][2] == "TP3"
    assert other.counters[1].tolist() == [1, 1, 1, 1, 0, 0]


def test_one_way_uses_source_pre_loop_direction_snapshot():
    book = SetupTradeBook()
    entries, _, _ = step(book, 0, longs=(0,), shorts=(1,), max_open=2, one_way=True)
    assert entries[0, 0] and entries[1, 1]  # od remains0 through source loop.
    book = SetupTradeBook()
    step(book, 0, shorts=(0,))
    entries, _, _ = step(book, 1, high=100.5, low=99.5, longs=(1,), shorts=(1,), max_open=2, one_way=True)
    assert entries[1, 0]  # S permits dirOk, then source's L branch has priority.


def bars():
    idx = pd.date_range("2026-03-02 07:00", periods=40, freq="15min", tz="America/New_York")
    result = pd.DataFrame({"Open": 100., "High": 101., "Low": 99., "Close": 100., "Volume": 100.}, index=idx)
    return result


def test_orb_waits_for_range_completion_and_consumes_raw_signal_once():
    frame = bars()
    # 09:30 is index10; ATR length2 is ready by the opening window.
    frame.iloc[11, :4] = [100, 103, 100, 102]
    result = setup_scanner(frame, enabled=("ORB",), atr_length=2)
    assert not result.ORB_raw_long.iloc[:11].any()
    assert result.or_high.iloc[11] == 101  # Breakout bar excluded from opening range.
    assert result.ORB_raw_long.iloc[11] and result.ORB_long_entry.iloc[11]
    assert result.or_fired.iloc[11:].all()
    assert result.ORB_raw_long.sum() == 1


def test_vwap_reclaim_uses_prior_run_and_requires_causal_exchange_inputs():
    frame = bars().iloc[:8].copy()
    frame.iloc[:6, :4] = [99, 100, 98, 99]
    frame.iloc[6, :4] = [99, 102, 99, 101]
    obs = pd.DataFrame({"vwap": 100., "available_at": frame.index + pd.Timedelta(minutes=15)}, index=frame.index)
    result = setup_scanner(frame, enabled=("VWAP",), vwap_observations=obs, atr_length=2, vwap_away=6)
    assert result.VWAP_raw_long.iloc[6]
    with pytest.raises(ValueError, match="requires exact"):
        setup_scanner(frame, enabled=("VWAP",))
    obs.iloc[6, 1] += pd.Timedelta(minutes=15)
    with pytest.raises(ValueError, match="unavailable"):
        setup_scanner(frame, enabled=("VWAP",), vwap_observations=obs)


def test_vwap_reset_accumulates_hlc3_volume_and_does_not_infer_calendar():
    frame = bars().iloc[:3].copy()
    frame.iloc[1, :4] = [100, 104, 100, 102]
    frame.Volume = [1., 3., 1.]
    flags = pd.Series([True, False, True], index=frame.index)
    result = setup_scanner(frame, enabled=("VWAP",), vwap_reset=flags, atr_length=2)
    assert result.vwap.tolist() == [100., 101.5, 100.]


def test_sweep_filter_accepts_missing_volume_but_applies_low_participation():
    frame = bars()
    frame.iloc[25, :4] = [100, 101, 97, 100.5]
    frame.loc[frame.index[25], "Volume"] = 1
    result = setup_scanner(frame, enabled=("SWEEP",), atr_length=2)
    assert not result.SWEEP_raw_long.iloc[25]
    frame.loc[frame.index[25], "Volume"] = np.nan
    result = setup_scanner(frame, enabled=("SWEEP",), atr_length=2)
    assert result.SWEEP_raw_long.iloc[25]


def test_prefix_future_perturbation_and_four_frame_setup_identity():
    frame = bars()
    frame.iloc[11, :4] = [100, 103, 100, 102]
    kwargs = dict(enabled=("EMA", "SWEEP", "ORB"), atr_length=2)
    result = setup_scanner(frame, **kwargs)
    for length in (5, 10, 12, 20):
        assert_frame_equal(setup_scanner(frame.iloc[:length], **kwargs), result.iloc[:length])
    changed = frame.copy()
    changed.iloc[20:, :4] *= 2
    assert_frame_equal(setup_scanner(changed, **kwargs).iloc[:20], result.iloc[:20])
    outputs = generate_setup_scanner_signals(frame, [1.2], [60], enable_shorting=True, **kwargs)
    assert len(outputs) == 4
    assert outputs[0].columns.names == ["setup_identity", "setup_stop_atr", "setup_max_bars"]
    assert outputs[0][("ORB", 1.2, 60)].equals(result.ORB_long_entry)
    with pytest.raises(ValueError, match="single-position"):
        generate_setup_scanner_signals(frame, [1.2], [60], max_open=2, **kwargs)


def test_missing_session_boundary_is_explicit_and_literal_mode_does_not_invent_reset():
    frame = bars().loc["2026-03-02 09:30":"2026-03-02 15:45"]
    tomorrow = frame.iloc[:1].copy()
    tomorrow.index += pd.Timedelta(days=1)
    frame = pd.concat([frame, tomorrow])
    with pytest.raises(ValueError, match="conceal"):
        setup_scanner(frame, enabled=("ORB",))
    result = setup_scanner(frame, enabled=("ORB",), strict_session_coverage=False)
    assert result.session_gap.iloc[-1]
    assert result.or_done.iloc[-1]


def test_ema_pullback_uses_recent_touch_then_price_confirmation():
    frame = bars()
    price = 100 + np.arange(len(frame)) * .5
    frame.Open, frame.Close, frame.High, frame.Low = price - .2, price, price + 1, price - 1
    frame.iloc[25, 2] = 100
    frame.iloc[26, :4] = [113, 116, 112.5, 115]
    result = setup_scanner(frame, enabled=("EMA",), atr_length=2)
    assert result.EMA_raw_long.iloc[26]
    untouched = frame.copy()
    untouched.iloc[25, 2] = 111.5
    untouched.iloc[26, 2] = 113
    assert not setup_scanner(untouched, enabled=("EMA",), atr_length=2).EMA_raw_long.iloc[26]


def test_break_retest_keeps_busy_level_and_promotes_queued_pivot_after_fire():
    frame = bars()
    frame.iloc[20, 1] = 105
    frame.iloc[23, :4] = [100, 107, 100, 106]
    frame.iloc[24, :4] = [106, 107, 104.9, 106.5]
    frame.iloc[25, :4] = [107, 110, 106, 108]
    frame.iloc[26, :4] = [107, 108, 106, 107]
    frame.iloc[27, :4] = [106, 107, 105.5, 106]
    frame.iloc[28, :4] = [106, 108, 105, 107]
    result = setup_scanner(frame, enabled=("BRT",), atr_length=2, pivot_length=2)
    assert result.BRT_raw_long.iloc[24]
    assert result.brt_high_pending.iloc[27] == 110
    assert result.brt_high.iloc[27] == 105
    assert result.BRT_raw_long.iloc[28]
    assert result.brt_high.iloc[28] == 110
    assert np.isnan(result.brt_high_pending.iloc[28])


def test_divergence_observes_rsi_at_pivot_but_fires_only_at_confirmation(monkeypatch):
    import v3.tv_setup_scanner as module
    frame = bars()
    frame.iloc[20, 2] = 95
    frame.iloc[26, 2] = 94
    values = pd.Series(50., index=frame.index)
    values.iloc[20], values.iloc[26] = 20, 30
    monkeypatch.setattr(module, "rsi", lambda source, length: values)
    result = setup_scanner(frame, enabled=("DIV",), atr_length=2, pivot_length=2)
    assert not result.DIV_raw_long.iloc[:28].any()
    assert result.DIV_raw_long.iloc[28]
