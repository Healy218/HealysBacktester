"""Hand-computed AMD source transitions, causality and wrapper seam."""
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from signals.tv_amd_po3_signals import generate_amd_po3_signals
from v3._tv_setup_support import percentile_rank_previous
from v3.tv_amd_po3 import AmdConfig, AmdState, amd_po3

AT = pd.Timestamp("2026-03-02", tz="UTC")


def accumulated():
    return AmdState(phase="accum", cycle_id=1, range_high=110., range_low=100., range_mid=105.,
                    range_width=10., range_start=0, expiry_anchor=0, range_age=19, atr_anchor=2.)


def step(state, i, high=109., low=101., close=105., **kwargs):
    return state.step(i, AT + pd.Timedelta(minutes=15 * i), high, low, close, **kwargs)


def test_wick_sweep_opens_distribution_same_bar_with_exact_fib_and_anchored_stop():
    state = accumulated()
    row = step(state, 20, low=98)
    assert row["sweep_low"] and row["long_entry"] and row["alert_distribution"]
    assert row["phase"] == "dist"
    assert row["entry"] == 105
    assert row["target"] == 116
    assert row["stop"] == pytest.approx(97.2)
    assert row["risk"] == pytest.approx(7.8)
    assert row["all_closed"] == 0
    assert not row["long_exit"]


def test_next_bar_target_stop_ambiguity_is_conservative_and_updates_only_now():
    state = accumulated()
    before = step(state, 20, low=98)
    resolved = step(state, 21, high=117, low=96)
    assert resolved["long_exit"] and resolved["ambiguous_outcome"]
    assert resolved["outcome"] == "ambiguous" and resolved["outcome_r"] == -1
    assert resolved["stop_count"] == 1 and resolved["target_count"] == 0
    assert resolved["all_closed"] == 1
    assert before["all_closed"] == 0 and before["sum_r"] == 0


def test_sweep_return_hard_deadline_precedes_inside_close():
    state = accumulated()
    first = step(state, 20, high=113, low=101, close=112)
    assert first["phase"] == "sweepPending"
    late = step(state, 29, high=115, low=102, close=105)
    assert late["breakout"] and late["phase"] == "idle"
    assert not late["short_entry"] and late["sweep_extreme"] == 115
    state = accumulated()
    step(state, 20, high=113, low=101, close=112)
    on_deadline = step(state, 28, high=114, low=102, close=105)
    assert on_deadline["short_entry"] and on_deadline["sweep_extreme"] == 114


def test_htf_rejection_rearms_with_new_expiry_and_blocks_repeat_same_side():
    state = accumulated()
    config = AmdConfig(use_htf_bias=True)
    rejected = step(state, 20, low=98, config=config, htf_close=99, htf_ema=100)
    assert rejected["rearmed"] and rejected["phase"] == "accum"
    assert rejected["expiry_anchor"] == 20 and rejected["first_sweep_side"] == -1
    repeated = step(state, 21, low=97, config=config, htf_close=101, htf_ema=100)
    assert not repeated["sweep_low"] and repeated["phase"] == "accum"
    opposite = step(state, 22, high=113, config=config, htf_close=99, htf_ema=100)
    assert opposite["short_entry"] and opposite["rearm_used"]
    resolved = step(state, 23, high=110, low=90, close=100, config=config)
    assert resolved["outcome"] == "target" and resolved["double_sweep_count"] == 1


def test_second_rejected_manipulation_fails_without_creating_reference_trade():
    state = accumulated()
    config = AmdConfig(use_htf_bias=True)
    step(state, 20, low=98, config=config, htf_close=99, htf_ema=100)
    rejected = step(state, 21, high=113, config=config, htf_close=101, htf_ema=100)
    assert rejected["failed_manipulation"] and rejected["failed_count"] == 1
    assert rejected["phase"] == "idle" and rejected["all_closed"] == 0


def test_filtered_inside_breach_keeps_range_but_outside_breach_resets():
    state = accumulated()
    config = AmdConfig(use_killzones=True)
    inside = step(state, 20, low=98, config=config, in_killzone=False)
    assert inside["phase"] == "accum" and not inside["sweep_low"]
    outside = step(state, 21, low=98, close=99, config=config, in_killzone=False)
    assert outside["filtered_reset"] and outside["phase"] == "idle"


def test_expiry_news_and_immaturity_have_source_priority():
    state = accumulated()
    expired = step(state, 97, high=115, low=95)
    assert expired["range_expired"] and not expired["news_reset"]
    assert step(accumulated(), 20, high=115, low=95)["news_reset"]
    immature = replace(accumulated(), range_start=15, expiry_anchor=15)
    assert step(immature, 20, low=98)["immature_reset"]


def test_absolute_expansion_uses_old_tolerance_and_liquidity_needs_two_confirmed_pivots():
    state = accumulated()
    widened = step(state, 20, high=110.5, low=99.5, config=AmdConfig(boundary_mode="absolute"))
    assert widened["range_high"] == 110.5 and widened["range_low"] == 99.5
    state = accumulated()
    config = AmdConfig(require_liquidity=True)
    state.pivots_low.append((10, 100.4))
    assert not step(state, 20, low=98, config=config)["sweep_low"]
    state.pivots_low.append((15, 99.6))
    assert step(state, 21, low=98, config=config)["long_entry"]


def test_impulse_tail_trim_anchors_atr_before_trimmed_window():
    state = AmdState()
    highs, lows, atrs = np.full(102, 110.), np.full(102, 100.), np.arange(102.) + 1
    highs[82] = 200
    row = step(state, 101, config=AmdConfig(stat_window=100, boundary_mode="absolute"),
               highs=highs, lows=lows, atrs=atrs, width_high=200, width_low=100, percent_rank=0)
    assert row["range_created"] and row["range_start_bar"] == 83
    assert row["range_age"] == 18 and row["range_high"] == 110
    assert row["atr_anchor"] == atrs[82]


def test_timeout_is_strictly_after_budget_and_target_has_priority():
    state = accumulated()
    config = AmdConfig(distribution_timeout=24)
    step(state, 20, low=98, config=config)
    assert not step(state, 44, config=config)["long_exit"]
    row = step(state, 45, close=106, config=config)
    assert row["outcome"] == "timeout" and row["outcome_r"] == pytest.approx(1 / 7.8)
    other = accumulated()
    step(other, 20, low=98, config=config)
    assert step(other, 45, high=117, config=config)["outcome"] == "target"


def test_time_window_statistics_and_detached_state_restart():
    state = accumulated()
    step(state, 20, low=98)
    restart = state.snapshot()
    assert step(state, 21, high=117) == step(restart, 21, high=117)
    assert state is not restart and state.cycles is not restart.cycles
    later = state.step(22, AT + pd.Timedelta(days=2), 109., 101., 105.)
    assert later["24h_closed"] == 0 and later["30d_closed"] == 1 and later["all_closed"] == 1
    assert np.isnan(later["all_target_rate"])  # min sample10 is preserved.


def compressed_bars():
    n = 230
    width = np.linspace(10, 1, n)
    frame = pd.DataFrame({"Open": 100., "High": 100 + width / 2,
                          "Low": 100 - width / 2, "Close": 100.},
                         index=pd.date_range(AT, periods=n, freq="15min"))
    frame.iloc[205, :4] = [100, 100.5, 96, 100]
    frame.iloc[206, :4] = [100, 110, 99, 105]
    return frame


def test_full_detector_prefix_future_perturbation_and_four_frame_parity():
    frame = compressed_bars()
    config = AmdConfig(boundary_mode="absolute")
    result = amd_po3(frame, config=config)
    assert result.range_created.iloc[201]
    assert result.long_entry.iloc[205]
    assert result.long_exit.iloc[206]
    for length in (50, 201, 202, 205, 206):
        assert_frame_equal(amd_po3(frame.iloc[:length], config=config), result.iloc[:length])
    changed = frame.copy()
    changed.iloc[207:] *= 2
    assert_frame_equal(amd_po3(changed, config=config).iloc[:207], result.iloc[:207])
    outputs = generate_amd_po3_signals(frame, [25], [1.5], enable_shorting=True, config=config)
    assert len(outputs) == 4
    assert outputs[0][(25, 1.5)].equals(result.long_entry)
    assert outputs[1][(25, 1.5)].equals(result.long_exit)


def test_rank_excludes_current_and_htf_availability_is_checked_at_bar_open():
    ranked = percentile_rank_previous([3., 2., 1., 0., 4.], 3)
    assert ranked[3] == 0 and ranked[4] == 100
    frame = compressed_bars()
    obs = pd.DataFrame({"close": 101., "ema50": 100., "available_at": frame.index}, index=frame.index)
    amd_po3(frame, config=AmdConfig(use_htf_bias=True), htf_observations=obs)
    obs.available_at += pd.Timedelta(minutes=15)
    with pytest.raises(ValueError, match="unavailable"):
        amd_po3(frame, config=AmdConfig(use_htf_bias=True), htf_observations=obs)
    with pytest.raises(ValueError, match="lower timeframe"):
        amd_po3(frame, config=AmdConfig(use_htf_bias=True), htf_observations=obs, htf_minutes=5)
