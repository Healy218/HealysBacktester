"""Hand-calculated source profiles and causal observation contracts.

These fixtures establish the local formulas and state order. They are not
exported TradingView observations and do not satisfy the external parity gate.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from v3.tv_liquidity_poc import structural_liquidity_poc
from v3.tv_htf_log_profile import auto_htf_period, htf_log_regression_profile


def bars(close, *, volume=10., half_range=1.):
    close = np.asarray(close, dtype=float)
    return pd.DataFrame({"Open": close, "High": close + half_range,
                         "Low": close - half_range, "Close": close, "Volume": volume},
                        index=pd.date_range("2026-01-05 14:30", periods=len(close), freq="15min", tz="UTC"))


def flags(frame, size=26):
    result = pd.Series(np.arange(len(frame)) % size == 0, index=frame.index)
    result.attrs["htf_period"] = "2D"
    return result


def test_profile_source_identity_and_feature_only_scope():
    folder = Path(__file__).parents[1] / "indicators/tradingview_sources"
    manifest = json.loads((folder / "profile_manifest.json").read_text())
    assert {r["public_id"] for r in manifest["scripts"]} == {"I8HrQVRv", "kwXpL7yZ"}
    for source in manifest["scripts"]:
        assert hashlib.sha256((folder / source["source_file"]).read_bytes()).hexdigest() == source["sha256"]
        assert source["license"] == "CC-BY-NC-SA-4.0"
        assert source["signal_wrapper"] is None
        assert "pending" in source["admission_status"]


def test_liquidity_state_preserves_na_comparison_and_restart_order():
    result = structural_liquidity_poc(bars([10, 11, 12, 12]))
    assert result.top_count.tolist() == [2, 0, 2, 3]
    assert result.top_sweep.tolist() == [False, True, False, False]
    assert result.top_anchor_changed.tolist() == [True, False, True, False]
    np.testing.assert_allclose(result.liquidity_top, [11., np.nan, 13., 13.], equal_nan=True)
    assert result.profile_top.tolist() == [11., 11., 13., 13.]
    assert result.top_anchor_index.tolist() == [0, 0, 2, 2]
    down = structural_liquidity_poc(bars([10, 9, 8, 8]))
    assert down.bottom_count.tolist() == [2, 0, 2, 3]
    assert down.bottom_sweep.tolist() == [False, True, False, False]
    assert down.profile_bottom.tolist() == [9., 9., 7., 7.]


def test_fade_occurs_before_anchor_and_does_not_create_sweep():
    result = structural_liquidity_poc(bars([100] * 5), fade_liquidity=3)
    assert result.top_count.tolist() == [2, 0, 2, 0, 2]
    assert not result.top_sweep.any() and not result.bottom_sweep.any()
    assert result.top_anchor_index.tolist() == [0, 0, 2, 2, 4]
    disabled_anchor = structural_liquidity_poc(bars([100] * 3), fade_liquidity=2)
    assert not disabled_anchor.top_anchor_changed.any()
    assert disabled_anchor.profile_top.eq(0).all()


def test_liquidity_atr_bin_allocation_and_poc_exact_hand_fixture():
    source = bars([100] * 101, half_range=2, volume=10.)
    result = structural_liquidity_poc(source, fade_liquidity=1000, include_bins=True)
    assert not result.profile_ready.iloc[:99].any()
    assert result.bin_step.iloc[99] == pytest.approx(.8)
    assert result.bin_count.iloc[99] == 5
    assert result.volume_bins.iloc[99] == (0., 0., 1000., 0., 0.)
    assert result.poc_bin_index.iloc[99] == 2
    assert result.poc_price.iloc[99] == pytest.approx(100.)
    assert result.allocated_volume.iloc[100] == 1010
    assert result.excluded_volume.iloc[100] == 0
    assert result.profile_start_at.iloc[-1] == source.index[0]


def test_liquidity_upper_bin_edge_is_excluded_not_clamped():
    source = bars([100] * 100, half_range=2)
    source["Close"] = 102.
    result = structural_liquidity_poc(source, fade_liquidity=1000, include_bins=True)
    assert result.volume_bins.iloc[-1] == (0., 0., 0., 0., 0.)
    assert result.allocated_volume.iloc[-1] == 0
    assert result.excluded_volume.iloc[-1] == 1000
    # Source chooses its first maximum even with zero volume, then divides
    # drawing widths by zero. The local output clearly separates these facts.
    assert result.poc_bin_index.iloc[-1] == 0
    assert result.poc_price.iloc[-1] == pytest.approx(98.4)
    assert result.profile_status.iloc[-1] == "zero_allocated_volume"
    assert not result.profile_ready.iloc[-1] and not result.poc_visible.iloc[-1]


def test_liquidity_zero_atr_and_resource_limit_are_explicit():
    zero = structural_liquidity_poc(bars([100] * 101, half_range=0))
    assert zero.profile_status.iloc[99] == "zero_atr"
    assert zero.poc_price.isna().all()
    with pytest.raises(ValueError, match="exceeding max_profile_bins"):
        structural_liquidity_poc(bars([100] * 100, half_range=2), max_profile_bins=4)


@pytest.mark.parametrize("period,expected", [
    ("1", "240"), ("5", "720"), ("15", "2D"), ("59", "2D"),
    ("60", "1W"), ("240", "1M"), ("1440", "12M"), ("1D", "2M"),
    ("D", "D"), ("2D", "3M"), ("1W", "12M"), ("1M", "12M"),
])
def test_literal_auto_htf_mapping(period, expected):
    assert auto_htf_period(period) == expected


def two_bar_session():
    source = bars([2., 4., 4.])
    source["Open"] = [1., 5., 3.]
    source["High"] = [2., 5., 4.]
    source["Low"] = [1., 4., 3.]
    source["Volume"] = [10., 20., 50.]
    return source, pd.Series([True, False, True], index=source.index)


def test_htf_log_regression_preserves_one_step_extrapolation_and_bins():
    source, change = two_bar_session()
    result = htf_log_regression_profile(source, change, channel_width=4., bin_count=5, include_bins=True)
    assert result.regression_end.iloc[:1].isna().all()
    row = result.iloc[1]
    assert row.regression_slope == pytest.approx(-np.log(2))
    assert row.regression_intercept == pytest.approx(np.log(8))
    assert row.regression_start == pytest.approx(2.)
    assert row.regression_end == pytest.approx(8.)  # source uses x0, not current fitted x1
    assert row.deviation == pytest.approx(1.)
    assert row.volume_bins == (20., 10., 0., 0., 0.)
    assert row.buy_volume == 10 and row.sell_volume == 20
    assert row.delta_pct == pytest.approx(-100 / 3)
    assert row.poc_start == pytest.approx(-1.2)
    assert row.poc_end == pytest.approx(4.8)
    assert row.poc_line_start_index == 15  # literal source drawing coordinate
    assert row.poc_line_start_price == pytest.approx(88.8)
    assert row.profile_ready and row.poc_visible


def test_completed_profiles_appear_only_when_next_session_is_observed():
    source, change = two_bar_session()
    result = htf_log_regression_profile(source, change, channel_width=4., bin_count=5, include_bins=True)
    assert result.completed_poc_end.iloc[:2].isna().all()
    assert result.session_completed.tolist() == [False, False, True]
    assert result.completed_poc_end.iloc[2] == pytest.approx(4.8)
    assert result.completed_volume_bins.iloc[2] == result.volume_bins.iloc[1]
    assert result.completed_available_at.iloc[2] == source.index[2] + pd.Timedelta(minutes=15)
    assert result.completed_last_observed_at.iloc[2] == source.index[1] + pd.Timedelta(minutes=15)
    assert result.completed_session_start_at.iloc[2] == source.index[0]
    assert result.htf_length.tolist() == [1, 2, 1]


def test_partial_first_session_stays_undefined_until_observed_reset():
    source = bars([2., 3., 4., 5.])
    change = pd.Series([False, False, True, False], index=source.index)
    result = htf_log_regression_profile(source, change)
    assert result.htf_length.tolist() == [2, 3, 1, 2]
    assert result.partial_initial_session.tolist() == [True, True, False, False]
    assert result.session_start_at.iloc[:2].isna().all()
    assert result.regression_end.iloc[:3].isna().all()
    assert np.isfinite(result.regression_end.iloc[3])
    assert result.completed_partial_initial_session.iloc[2]
    assert result.completed_profile_status.iloc[2] == "partial_initial_session"


def test_htf_constant_price_zero_height_is_not_given_an_invented_bin():
    source = bars([100.] * 5)
    result = htf_log_regression_profile(source, flags(source), include_bins=True)
    assert result.profile_status.iloc[1:].eq("undefined_zero_channel_height").all()
    assert not result.profile_ready.any()
    assert np.isnan(result.volume_bins.iloc[-1]).all()
    assert result.delta_pct.eq(0).all()  # all bars are dojis
    assert result.doji_volume.iloc[-1] == 50


def test_profile_and_poc_visibility_do_not_alter_other_features():
    source, change = two_bar_session()
    shown = htf_log_regression_profile(source, change, channel_width=4., bin_count=5)
    hidden_poc = htf_log_regression_profile(source, change, channel_width=4., bin_count=5, show_poc=False)
    assert not hidden_poc.poc_visible.any()
    pd.testing.assert_series_equal(shown.poc_end, hidden_poc.poc_end)
    disabled = htf_log_regression_profile(source, change, show_profile=False)
    assert disabled.profile_status.iloc[1] == "disabled"
    pd.testing.assert_series_equal(shown.buy_volume, disabled.buy_volume)
    pd.testing.assert_series_equal(shown.regression_end, disabled.regression_end)


@pytest.mark.parametrize("function", [structural_liquidity_poc, htf_log_regression_profile])
def test_each_available_profile_is_prefix_invariant(function):
    source = bars(100 + np.random.default_rng(19).normal(0, 1, 155).cumsum(),
                  volume=np.arange(155) + 1)
    def calc(frame):
        kwargs = {"include_bins": True}
        return function(frame, flags(source).loc[frame.index], **kwargs) if function == htf_log_regression_profile else function(frame, **kwargs)
    full = calc(source)
    for end in (0, 1, 2, 26, 99, 130, 154):
        pd.testing.assert_frame_equal(calc(source.iloc[:end]), full.iloc[:end])
    altered = source.copy()
    altered.iloc[120:, :4] *= 1.5
    altered.iloc[120:, altered.columns.get_loc("Volume")] *= 50
    pd.testing.assert_frame_equal(calc(altered).iloc[:120], full.iloc[:120])


@pytest.mark.parametrize("function", [structural_liquidity_poc, htf_log_regression_profile])
def test_profiles_require_real_completed_volume_observations(function):
    source = bars([100, 101, 102])
    def calc(frame, **kwargs):
        return function(frame, flags(frame), **kwargs) if function == htf_log_regression_profile else function(frame, **kwargs)
    with pytest.raises(ValueError, match="forming/future"):
        calc(source, as_of=source.index[-1])
    with pytest.raises(ValueError, match="timezone-aware"):
        calc(source.set_axis(source.index.tz_localize(None)))
    source.loc[source.index[1], "Volume"] = np.nan
    with pytest.raises(ValueError, match="finite and nonnegative"):
        calc(source)


def test_htf_flags_and_positive_log_price_contract():
    source = bars([100, 101, 102])
    change = flags(source)
    change.attrs["htf_period"] = "D"
    with pytest.raises(ValueError, match="flag period"):
        htf_log_regression_profile(source, change)
    with pytest.raises(ValueError, match="aligned nonmissing boolean"):
        htf_log_regression_profile(source, pd.Series([1, 0, 0], index=source.index))
    with pytest.raises(ValueError, match="matching bar_minutes"):
        htf_log_regression_profile(source, flags(source), chart_period="60", bar_minutes=15)
    with pytest.raises(ValueError, match="positive Close"):
        htf_log_regression_profile(bars([0, 1, 2]), flags(source))
