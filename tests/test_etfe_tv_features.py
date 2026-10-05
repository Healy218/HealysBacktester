import numpy as np
import pandas as pd
import pytest

from nn_meta.etfe.causal_inputs import session_bars
from nn_meta.etfe.tv_features import bindings, compute, htf_flags, native_frames, project
from tests.test_etfe_causal import fixture


def test_frozen_projection_census_and_no_legacy_registry():
    b = bindings()
    assert len(b) == 96 and len({x['source'] for x in b}) == 13
    assert all(x['name'].startswith('tv_') for x in b)


@pytest.mark.parametrize('minutes,expected', [(1, 6), (5, 3), (15, 2)])
def test_htf_calendar_anchor_and_prefix(minutes, expected):
    raw, calendar = fixture(); bars = session_bars(raw, calendar, minutes)
    full = htf_flags(bars, minutes)
    assert full.sum() == expected
    pd.testing.assert_series_equal(htf_flags(bars.iloc[:-7], minutes), full.iloc[:-7])
    if minutes == 15:
        assert not full.loc[bars.session_ordinal.eq(1)].any()
        assert full.loc[bars.session_ordinal.eq(2)].iloc[0]


@pytest.mark.parametrize('minutes', [1, 5, 15])
def test_thirteen_sources_prefix_and_extreme_future(minutes):
    raw, calendar = fixture(); bars = session_bars(raw, calendar, minutes)
    cut = len(bars) - 8; observed = bars.index[cut-5:cut]
    full, reasons, frames = compute(bars, raw, minutes, observed)
    prefix, pr, _ = compute(bars.iloc[:cut], raw.loc[raw.index < bars.bar_end.iloc[cut-1]], minutes, observed)
    pd.testing.assert_frame_equal(full, prefix, rtol=1e-12, atol=1e-12)
    pd.testing.assert_frame_equal(reasons, pr)
    changed = bars.copy(); changed.loc[changed.index >= bars.index[cut], ['Open','High','Low','Close']] *= 2
    future, fr, _ = compute(changed, raw, minutes, observed)
    pd.testing.assert_frame_equal(full, future, rtol=1e-12, atol=1e-12)
    pd.testing.assert_frame_equal(reasons, fr)
    assert len(frames) == 13 and full.shape == (5, 96)
    assert not np.isinf(full.to_numpy()).any()
    assert reasons.eq('observed_diagnostic').equals(full.notna())


def test_gap_taints_recurrence_without_filling_or_reset():
    raw, calendar = fixture(1); raw = raw.drop(raw.index[55]); bars = session_bars(raw, calendar, 5)
    result, reasons, _ = compute(bars, raw, 5, bars.index[9:14])
    assert result.iloc[2:].isna().all().all()
    assert reasons.iloc[2:].eq('incomplete_source_prefix').all().all()
    assert result.iloc[:2].notna().any().any()


def test_cold_start_defaults_are_not_observations():
    raw, calendar = fixture(1); bars = session_bars(raw, calendar, 1).iloc[:5]
    result, reasons, _ = compute(bars, raw, 1)
    for field in ['tv_gaussian_direction', 'tv_fibonacci_direction', 'tv_structure_market_direction',
                  'tv_probability_resolved_total', 'tv_order_blocks_bull_active_count', 'tv_amd_phase',
                  'tv_setup_ORB_raw_long', 'tv_liquidity_profile_ready']:
        assert result[field].isna().all(), field
    assert result.tv_setup_or_done.eq(0).all()
    assert result.tv_ict_ASIA_in_session.eq(0).all()
    assert result.tv_ict_ASIA_break_high.isna().all()
    assert result.tv_ict_LNDN_range_value_atr14.isna().all()


def test_zero_atr_no_probability_history_and_delayed_profiles():
    raw, calendar = fixture(1)
    raw[['Open','High','Low','Close']] = 100.
    bars = session_bars(raw, calendar, 5)
    values, _, frames = compute(bars, raw, 5, bars.index[-3:])
    normalized = [b['name'] for b in bindings() if b['transform'] in ('price','range')]
    assert values[normalized].isna().all().all()
    assert values.tv_probability_long_reference_win_pct_fraction.isna().all()
    assert values.tv_htf_completed_profile_ready.isna().all()


def test_projection_predicates_and_formula_units():
    raw, calendar = fixture(); bars = session_bars(raw, calendar, 5)
    observed = bars.index[-2:]; frames = native_frames(bars, raw, 5, observed)
    frames['probability']['total_long_wins'] = 3
    frames['probability']['total_long_losses'] = 1
    frames['probability']['long_resolved'] = 4
    frames['probability']['long_reference_win_pct'] = 75.
    frames['liquidity']['profile_ready'] = False
    frames['liquidity']['poc_price'] = 123.
    values, reasons = project(bars, frames)
    assert values.tv_probability_long_reference_win_pct_fraction.eq(.75).all()
    assert values.tv_liquidity_poc_price_distance_atr14.isna().all()
    assert reasons.tv_liquidity_poc_price_distance_atr14.eq('native_prerequisite_unavailable').all()


def test_reject_unknown_observation_and_accelerator(monkeypatch):
    raw, calendar = fixture(1); bars = session_bars(raw, calendar, 15)
    with pytest.raises(ValueError, match='observation'):
        compute(bars, raw, 15, pd.DatetimeIndex([pd.Timestamp('2023-01-01', tz='UTC')]))
    monkeypatch.setenv('NN_META_V6_ACCELERATE', '1')
    with pytest.raises(ValueError, match='unaccelerated'):
        compute(bars, raw, 15)


def test_delayed_stock_availability_rejected():
    raw, calendar = fixture(1); bars = session_bars(raw, calendar, 15)
    bars.loc[bars.index[0], 'available_at'] += pd.Timedelta(seconds=1)
    with pytest.raises(ValueError, match='publication'):
        compute(bars, raw, 15)


def test_htf_doji_zero_denominator_is_missing():
    raw, calendar = fixture(1); bars = session_bars(raw, calendar, 5)
    bars['Open'] = bars.Close
    values, reasons, _ = compute(bars, raw, 5, bars.index[-2:])
    assert values.tv_htf_delta_pct_fraction.isna().all()
    assert reasons.tv_htf_delta_pct_fraction.eq('native_prerequisite_unavailable').all()
