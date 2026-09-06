"""Hand-computed source behavior; exported TradingView fixtures remain pending."""
from dataclasses import FrozenInstanceError

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from v3.tv_volume_order_blocks import (
    _Machine, _Pending, _pivots, volume_order_blocks, volume_strength,
)


def example(extra=()):
    values = [(100, 101, 99, 100, 100)] * 100
    values += [(100, 101, 90, 100, 200), (100, 104, 95, 103, 100),
               (103, 105, 96, 104, 100)]
    values += list(extra)
    return pd.DataFrame(values, index=pd.date_range("2026-03-02", periods=len(values), freq="15min", tz="UTC"),
                        columns=["Open", "High", "Low", "Close", "Volume"], dtype=float)


def calculate(frame, **kwargs):
    return volume_order_blocks(frame, sw_len=2, include_zone_snapshots=True, **kwargs)


def test_volume_strength_uses_truncation_and_clipping_without_weighting_prices():
    assert volume_strength(0, 100) == 8
    assert volume_strength(100, 100) == 16
    assert volume_strength(200, 105) == 27  # raw alpha73.142... truncates to73.
    assert volume_strength(1000, 100) == 60
    assert volume_strength(0, 0) == 16
    assert volume_strength(100, np.nan) == 16


def test_retroactive_origin_waits_for_confirmation_and_uses_confirmation_atr():
    frame = example()
    result = calculate(frame)
    assert not result.bull_created.iloc[:102].any()
    assert result.bull_created.iloc[102]
    assert result.bull_created_retroactive.iloc[102]
    assert result.pivot_low.iloc[102] == 90
    assert result.atr.iloc[102] == pytest.approx(2.227509)
    assert result.bull_created_trigger.iloc[102] == pytest.approx(90 + 4 * 2.227509)
    assert result.bull_created_high.iloc[102] == 101
    assert result.bull_created_low.iloc[102] == 90
    assert result.bull_created_strength.iloc[102] == 27
    assert result.bull_created_origin_bar.iloc[102] == 100
    assert result.bull_created_confirmed_bar.iloc[102] == 102
    assert result.bull_created_cross_bar.iloc[102] == 101
    assert result.bull_created_available_at.iloc[102] == frame.index[102] + pd.Timedelta(minutes=15)
    assert result.bull_created_origin_at.iloc[102] == frame.index[100]


def test_volume_filter_suppresses_pivot_state_but_preserves_raw_confirmation():
    result = calculate(example(), min_volume_strength=28)
    assert result.pivot_low.iloc[102] == 90
    assert result.pivot_low_strength.iloc[102] == 27
    assert not result.pivot_low_accepted.iloc[102]
    assert not result.bull_pending.any()
    assert result.active_count.eq(0).all()


def test_retroactive_zone_can_emit_retest_on_its_confirmation_bar():
    frame = example()
    frame.iloc[102, :4] = [103, 106, 102, 104]
    result = calculate(frame)
    assert result.bull_created.iloc[102]
    assert result.bull_retest.iloc[102]
    assert result.bull_retest_zone_id.iloc[102] == result.bull_created_id.iloc[102]


def delayed_example():
    return example([(104, 107, 97, 106, 100), (106, 110, 98, 109, 100),
                    (110, 114, 89, 113, 100), (113, 115, 88, 114, 100)])


def test_delayed_breakout_zone_is_created_after_invalidation_pass():
    frame = delayed_example()
    result = calculate(frame, displacement=10)
    assert result.bull_pending.iloc[102:105].all()
    assert result.bull_pending_trigger.iloc[102] == pytest.approx(112.27509)
    assert result.bull_created.iloc[105]
    assert not result.bull_created_retroactive.iloc[105]
    assert result.bull_created_cross_bar.iloc[105] == 105
    assert frame.Low.iloc[105] < result.bull_created_low.iloc[105]
    assert result.bull_active_count.iloc[105] == 1  # Source retains creation-bar breach.
    assert not result.bull_retest.iloc[105]
    assert result.invalidation_count.iloc[106] == 1
    assert result.bull_active_count.iloc[106] == 0


def test_delayed_creation_volume_strength_is_bound_to_pivot_bar_average():
    frame = delayed_example()
    frame.iloc[105, -1] = 10_000_000
    result = calculate(frame, displacement=10)
    assert result.volume_sma.iloc[105] > 100_000
    assert result.bull_created_strength.iloc[105] == 27


def test_bearish_logic_mirrors_bullish_while_preserving_source_order():
    frame = delayed_example()
    mirrored = frame.copy()
    mirrored.Open, mirrored.Close = 200 - frame.Open, 200 - frame.Close
    mirrored.High, mirrored.Low = 200 - frame.Low, 200 - frame.High
    bull, bear = calculate(frame, displacement=10), calculate(mirrored, displacement=10)
    assert bear.bear_created.iloc[105]
    assert bear.bear_created_high.iloc[105] == 110
    assert bear.bear_created_low.iloc[105] == 99
    assert bear.bear_created_trigger.iloc[105] == pytest.approx(200 - bull.bull_created_trigger.iloc[105])
    assert bear.invalidation_count.iloc[106] == 1


def test_zone_overlap_is_inclusive_same_side_and_capacity_is_shared_fifo():
    frame = example()
    stamps, available = frame.index, frame.index + pd.Timedelta(minutes=15)
    machine = _Machine()

    def add(high, low, bullish, max_ob=10):
        pending = _Pending(high, low, high + 1, 100, 100, 100, 102, True)
        return machine.add(pending, bullish, 102, 101, stamps, available, max_ob, retroactive=True)

    first, _ = add(101, 90, True)
    second, _ = add(110, 105, False)
    third, removed = add(105, 101, True)
    assert removed == [(first.id, "overlap")]  # Edge101 counts as overlap.
    assert [zone.id for zone in machine.active] == [second.id, third.id]
    fourth, removed = add(125, 120, True, max_ob=2)
    assert removed == [(second.id, "capacity")]
    assert [zone.id for zone in machine.active] == [third.id, fourth.id]


def test_zero_capacity_preserves_creation_event_but_no_active_zone():
    result = calculate(example(), max_ob=0)
    assert result.bull_created.iloc[102]
    assert result.active_count.eq(0).all()
    assert result.capacity_removal_count.iloc[102] == 1


def test_retest_cooldown_is_strictly_more_than_five_bars_and_invalidation_wins():
    frame = example()
    machine = _Machine()
    pending = _Pending(120, 110, 130, 100, 100, 0, 2, True)
    zone, _ = machine.add(pending, True, 2, 1, frame.index, frame.index + pd.Timedelta(minutes=15), 10,
                          retroactive=True)
    high, low, close = np.full(13, 135.), np.full(13, 110.), np.full(13, 115.)
    low[6], close[6] = 125, 130
    assert machine.manage(6, high, low, close)[1] == zone.id
    close[11] = 125  # Cross via close; difference5 is still cooling down.
    assert machine.manage(11, high, low, close)[1] == -1
    low[12], close[12] = 125, 130
    assert machine.manage(12, high, low, close)[1] == zone.id
    machine.last_bull_retest = 0
    low[12] = 109  # Close cross would label, but wick invalidates first.
    close[11] = 115
    removed, bull_event, _ = machine.manage(12, high, low, close)
    assert removed == [(zone.id, "invalidation")]
    assert bull_event == -1


def test_tied_pivot_assumption_confirms_rightmost_plateau_without_backfill():
    high = _pivots(np.array([1., 3., 3., 2.]), 1, high=True)
    low = _pivots(np.array([3., 1., 1., 2.]), 1, high=False)
    assert np.isnan(high[:3]).all() and high[3] == 3
    assert np.isnan(low[:3]).all() and low[3] == 1


def test_prefix_future_perturbation_and_immutable_zone_snapshots():
    frame = delayed_example()
    full = calculate(frame, displacement=10)
    for length in (20, 101, 102, 103, 105, 106):
        assert_frame_equal(calculate(frame.iloc[:length], displacement=10), full.iloc[:length])
    changed = frame.copy()
    changed.iloc[105:, :4] *= 2
    assert_frame_equal(calculate(changed, displacement=10).iloc[:105], full.iloc[:105])
    zone = full.active_zones.iloc[105][0]
    with pytest.raises(FrozenInstanceError):
        zone.high = 999
    assert len(full.active_zones.iloc[105]) == 1
    assert not full.active_zones.iloc[106]


def test_pre_atr_pivot_keeps_nan_trigger_until_replaced():
    frame = example().iloc[:5].copy()
    frame.iloc[2, 2] = 90
    result = calculate(frame)
    assert result.pivot_low_accepted.iloc[4]
    assert result.bull_pending.iloc[4]
    assert np.isnan(result.bull_pending_trigger.iloc[4])
    assert result.active_count.eq(0).all()


def test_input_contract_rejects_missing_bad_volume_forming_bars_and_unsupported_capacity():
    frame = example()
    with pytest.raises(ValueError, match="Volume"):
        calculate(frame.drop(columns="Volume"))
    bad = frame.copy()
    bad.iloc[0, -1] = -1
    with pytest.raises(ValueError, match="Volume"):
        calculate(bad)
    with pytest.raises(ValueError, match="forming/future"):
        calculate(frame, as_of=frame.index[-1])
    with pytest.raises(ValueError, match="max_ob"):
        calculate(frame, max_ob=501)
    with pytest.raises(ValueError, match="sw_len"):
        volume_order_blocks(frame, sw_len=0)
    naive = frame.copy()
    naive.index = naive.index.tz_localize(None)
    with pytest.raises(ValueError, match="timezone-aware"):
        calculate(naive)


def test_empty_history_retains_typed_feature_and_snapshot_schema():
    frame = example()
    assert_frame_equal(calculate(frame.iloc[:0]), calculate(frame).iloc[:0])
