"""Source-backed ICT cases, not exported TradingView parity fixtures."""
import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from v3.tv_ict_killzones import SessionWindow, ict_killzones


def bars(times, prices=None, tz="America/New_York"):
    index = pd.DatetimeIndex(times, tz=tz)
    if prices is None:
        prices = [(10., 11., 9., 10.)] * len(index)
    return pd.DataFrame(prices, columns=["Open", "High", "Low", "Close"], index=index, dtype=float)


def session_bars():
    return bars(["2026-03-02 09:15", "2026-03-02 09:30", "2026-03-02 09:45",
                 "2026-03-02 10:00", "2026-03-02 10:15"],
                [(10, 11, 9, 10), (10, 12, 9, 11), (11, 14, 8, 12),
                 (12, 14, 8, 12), (12, 15, 7, 12)])


def calculate(frame, **kwargs):
    return ict_killzones(frame, sessions={"TEST": "0930-1000"}, opening_times=(), **kwargs)


def test_session_extrema_confirm_on_first_outside_observation_without_backfill():
    frame = session_bars()
    result = calculate(frame, show_midpoints=True)
    assert result.TEST_session_start.tolist() == [False, True, False, False, False]
    assert result.TEST_session_end.tolist() == [False, False, False, True, False]
    assert result.TEST_current_high.iloc[1:4].tolist() == [12, 14, 14]
    assert result.TEST_current_low.iloc[1:4].tolist() == [9, 8, 8]
    assert result.TEST_confirmed_high.iloc[:3].isna().all()
    assert result.TEST_confirmed_high.iloc[3:].tolist() == [14, 14]
    assert result.TEST_confirmed_at.iloc[3] == frame.index[3] + pd.Timedelta(minutes=15)
    assert result.TEST_pivot_high_at.iloc[3] == frame.index[2]
    assert result.TEST_pivot_total.tolist() == [0, 1, 1, 1, 1]
    assert result.TEST_break_high.tolist() == [False, False, False, False, True]
    assert result.TEST_break_low.tolist() == [False, False, False, False, True]
    assert result.TEST_midpoint_touch.tolist() == [False, False, False, True, False]
    assert result.TEST_pivot_high_hit_pct.iloc[-1] == 100


def test_cutoff_counts_crossing_before_invalidating_other_pivot():
    frame = session_bars()
    frame.iloc[3] = [12, 15, 8, 12]
    result = calculate(frame, cutoff="1000-1001")
    assert result.TEST_break_high.iloc[3]
    assert not result.TEST_pivot_low_valid.iloc[3]
    assert not result.TEST_break_low.iloc[4]
    assert result.TEST_pivot_low_hits.iloc[-1] == 0


def test_all_tracking_can_hit_old_pivot_during_new_session_and_prunes():
    frame = pd.concat([session_bars().iloc[:4],
                       bars(["2026-03-03 09:30"], [(10, 15, 9, 10)])])
    recent = calculate(frame)
    all_sessions = calculate(frame, extend_which="All")
    pruned = calculate(frame, extend_which="All", max_days=1)
    assert recent.TEST_high_break_count.iloc[-1] == 0
    assert all_sessions.TEST_high_break_count.iloc[-1] == 1
    assert not all_sessions.TEST_break_high.iloc[-1]  # Source alert only newest pivot.
    assert all_sessions.TEST_pivot_total.iloc[-1] == 2
    assert all_sessions.TEST_pivot_high_hit_pct.iloc[-1] == 50
    assert pruned.TEST_high_break_count.iloc[-1] == 0


def test_range_levels_use_completed_prior_range_and_inclusive_both_side_touches():
    frame = pd.concat([session_bars().iloc[:4],
                       bars(["2026-03-03 09:30", "2026-03-03 10:00"],
                            [(10, 13, 7, 10), (10, 20, 1, 10)])])
    result = calculate(frame, level_multipliers=(.5,))
    assert result.TEST_level_0_total.iloc[:4].eq(0).all()
    assert result.TEST_range_value.iloc[3] == 6
    assert result.TEST_level_0_high.iloc[4] == 13
    assert result.TEST_level_0_low.iloc[4] == 7
    assert result.TEST_level_0_high_hit.iloc[4]
    assert result.TEST_level_0_low_hit.iloc[4]
    assert not result.TEST_level_0_high_hit.iloc[5]
    assert result.TEST_level_0_high_hits.iloc[-1] == 1


def test_range_level_half_tick_ties_round_up_and_outside_touch_does_not_count():
    frame = bars(["2026-03-02 09:30", "2026-03-02 09:45", "2026-03-02 10:00",
                  "2026-03-03 09:30", "2026-03-03 10:00"],
                 [(10, 11, 10, 10), (10, 11, 10, 10), (10, 11, 10, 10),
                  (10, 10, 10, 10), (10, 12, 9, 10)])
    result = calculate(frame, level_multipliers=(.5,), minimum_tick=1)
    assert result.TEST_level_0_high.iloc[3] == 11
    assert result.TEST_level_0_low.iloc[3] == 10  # 9.5 rounds to 10.
    assert result.TEST_level_0_low_hit.iloc[3]
    assert not result.TEST_level_0_high_hit.iloc[4]
    assert result.TEST_level_0_high_hits.iloc[-1] == 0


def test_standard_deviation_refreshes_at_next_start_and_weights_bars():
    frame = pd.concat([session_bars().iloc[:4],
                       bars(["2026-03-03 09:30", "2026-03-03 10:00",
                             "2026-03-04 09:30"],
                            [(10, 15, 9, 14), (10, 15, 9, 10), (10, 11, 9, 10)])])
    result = calculate(frame, range_measure="Standard Deviation")
    assert result.TEST_sd_value.iloc[:4].isna().all()
    assert result.TEST_sd_value.iloc[4:6].tolist() == [.5, .5]  # Previous displacements 1,2.
    assert result.TEST_sd_value.iloc[6] == pytest.approx(np.std([1, 2, 4], ddof=0))
    trimmed = calculate(frame, range_measure="Standard Deviation", data_lookback=1)
    assert np.isnan(trimmed.TEST_sd_value.iloc[6])  # One sample in the retained session.


def test_overnight_day_mask_uses_end_day_and_does_not_reset_at_midnight():
    frame = bars(["2026-03-01 19:45", "2026-03-01 20:00", "2026-03-01 23:45",
                  "2026-03-02 00:00", "2026-03-02 00:15", "2026-03-02 01:00",
                  "2026-03-02 20:00"])
    result = ict_killzones(frame, sessions={"NIGHT": "2000-0100:2"}, opening_times=())
    assert result.NIGHT_in_session.tolist() == [False, True, True, True, True, False, False]
    assert result.NIGHT_session_start.sum() == 1
    assert result.NIGHT_session_end.sum() == 1
    assert result.NIGHT_pivot_total.iloc[-1] == 1


def test_iana_dst_changes_utc_session_time_but_fixed_gmt_does_not():
    frame = bars(["2026-03-06 14:15", "2026-03-06 14:30", "2026-03-06 15:00",
                  "2026-03-09 13:15", "2026-03-09 13:30", "2026-03-09 14:00",
                  "2026-03-09 14:30"], tz="UTC")
    ny = calculate(frame)
    fixed = calculate(frame, timezone="GMT-5")
    assert ny.TEST_session_start.tolist() == [False, True, False, False, True, False, False]
    assert fixed.TEST_session_start.tolist() == [False, True, False, False, False, False, True]
    assert ny.available_at.iloc[4] == pd.Timestamp("2026-03-09 13:45", tz="UTC")


def test_exchange_period_flags_are_explicit_and_boundary_bar_can_break_prior_period():
    frame = session_bars()
    flags = pd.DataFrame({"D": [True, False, True, False, False]}, index=frame.index)
    result = calculate(frame, period_changes=flags)
    assert np.isnan(result.D_previous_high.iloc[1])
    assert result.D_previous_high.iloc[2] == 12
    assert result.D_previous_low.iloc[2] == 9
    assert result.D_break_high.iloc[2] and result.D_break_low.iloc[2]
    assert result.D_total.iloc[-1] == 1
    assert result.D_high_hits.iloc[-1] == 1
    assert not any(column.startswith("D_") for column in calculate(frame))
    flags.iloc[0] = False
    unknown_initial_period = calculate(frame, period_changes=flags)
    assert unknown_initial_period.D_current_high.iloc[:2].isna().all()
    assert unknown_initial_period.D_previous_high.isna().all()


def test_opening_price_requires_matching_bar_open_and_cutoff_stops_extension():
    frame = session_bars()
    result = ict_killzones(frame, sessions={}, opening_times=("0930", "0931"), cutoff="1000-1001")
    assert result.open_0930_event.tolist() == [False, True, False, False, False]
    assert result.open_0930.iloc[1:].eq(10).all()
    assert result.open_0931.isna().all()
    assert result.open_0930_active.tolist() == [False, True, True, False, False]


def test_partial_session_is_exposed_and_missing_day_reset_is_rejected():
    partial = calculate(session_bars().iloc[2:])
    assert partial.TEST_partial_session.all()
    frame = bars(["2026-03-02 09:30", "2026-03-02 09:45", "2026-03-03 09:30"])
    with pytest.raises(ValueError, match="missing outside-session bars"):
        calculate(frame)


def test_all_features_are_prefix_and_future_perturbation_invariant():
    frame = pd.concat([session_bars(), bars(["2026-03-03 09:30", "2026-03-03 09:45",
                                            "2026-03-03 10:00"])])
    kwargs = dict(show_midpoints=True, level_multipliers=(.25, .5), extend_which="All")
    full = calculate(frame, **kwargs)
    for length in (1, 3, 4, 6, 7):
        assert_frame_equal(calculate(frame.iloc[:length], **kwargs), full.iloc[:length])
    changed = frame.copy()
    changed.iloc[5:] *= 20
    assert_frame_equal(calculate(changed, **kwargs).iloc[:5], full.iloc[:5])


def test_pivot_comparison_rounds_operands_without_rounding_stored_extrema():
    frame = session_bars().iloc[:4].copy()
    frame.iloc[3] = [12, 14 + 1e-11, 8 - 1e-11, 12]
    result = calculate(frame)
    assert not result.TEST_break_high.any()
    assert not result.TEST_break_low.any()


def test_disabled_pivots_keep_session_range_without_hit_counters():
    result = calculate(session_bars(), show_pivots=False)
    assert result.TEST_current_range.iloc[-1] == 6
    assert result.TEST_pivot_high.isna().all()
    assert result.TEST_pivot_total.eq(0).all()
    assert not result.TEST_break_high.any()


def test_input_contract_rejects_naive_forming_unaligned_and_bad_period_inputs():
    frame = session_bars()
    naive = frame.copy()
    naive.index = naive.index.tz_localize(None)
    with pytest.raises(ValueError, match="timezone-aware"):
        calculate(naive)
    with pytest.raises(ValueError, match="forming/future"):
        calculate(frame, as_of=frame.index[-1])
    with pytest.raises(ValueError, match="boundaries must align"):
        ict_killzones(frame, sessions={"BAD": "0931-1000"})
    with pytest.raises(ValueError, match="full-day"):
        SessionWindow.parse("0000-0000")
    with pytest.raises(ValueError, match="inclusive display"):
        calculate(frame, bar_minutes=60)
    with pytest.raises(ValueError, match="finite and positive"):
        calculate(frame, level_multipliers=(0,))
    with pytest.raises(ValueError, match="nonmissing boolean"):
        calculate(frame, period_changes=pd.DataFrame({"D": [0] * len(frame)}, index=frame.index))
    with pytest.raises(ValueError, match="align to bars"):
        calculate(frame, period_changes=pd.DataFrame({"D": [True]}))
    half_hour = frame.iloc[[1, 3]]
    ict_killzones(half_hour, sessions={}, opening_times=(), bar_minutes=30, timeframe_limit=30)


def test_empty_input_retains_numeric_feature_schema():
    frame = session_bars()
    flags = pd.DataFrame({"D": [True, False, False, False, False]}, index=frame.index)
    full = calculate(frame, level_multipliers=(.5,), period_changes=flags)
    empty = calculate(frame.iloc[:0], level_multipliers=(.5,), period_changes=flags.iloc[:0])
    assert set(empty) == set(full)
    assert_frame_equal(empty.reindex(columns=full.columns), full.iloc[:0])
