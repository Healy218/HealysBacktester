"""Source formula/state and causality checks; external Pine fixtures pending."""
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from v3.tv_volume_footprint import (
    _Component, _band_mass, _density, _gaussian_rows, _imbalances, _metrics,
    _profile_erfc, _table_cdf, volume_footprint,
)


def bars(close=(100.,), high=None, low=None, volume=None):
    close = np.asarray(close, float)
    n = len(close)
    return pd.DataFrame({"Open": close, "High": close + 2 if high is None else high,
                         "Low": close - 2 if low is None else low, "Close": close,
                         "Volume": np.full(n, 100.) if volume is None else volume},
                        index=pd.date_range("2026-09-01", periods=n, freq="15min", tz="UTC"))


def intrabars(frame, up, down):
    observed = pd.Series(frame.index + pd.Timedelta(minutes=15), index=frame.index)
    observed[np.isnan(up)] = pd.NaT
    return pd.DataFrame({"up_volume": up, "down_volume": down, "observed_at": observed}, index=frame.index)


def test_manifest_pins_exact_sources_and_helpers():
    directory = Path(__file__).parents[1] / "indicators/tradingview_sources"
    manifest = json.loads((directory / "footprint_manifest.json").read_text())
    entry = manifest["scripts"][0]
    assert entry["public_id"] == "Tm1cGCPD"
    assert entry["publication_version"] == 4
    assert hashlib.sha256((directory / entry["source_file"]).read_bytes()).hexdigest() == entry["sha256"]
    assert entry["implementation_module"] == "v3/tv_volume_footprint.py"
    assert entry["signal_wrapper"] is None
    assert entry["engines"]["native"]["supported"] is False
    for dependency in entry["library_dependencies"]:
        assert hashlib.sha256((directory / dependency["source_file"]).read_bytes()).hexdigest() == dependency["sha256"]


@pytest.mark.parametrize("x", [-30., -5., -4., -1., -.46875, 0., .2, 1., 4., 5., 26., 30.])
def test_literal_cody_cdf_agrees_with_independent_erfc(x):
    assert _profile_erfc(x) == pytest.approx(math.erfc(x), abs=3e-16)


def test_table_uses_source_approximation_and_profile_keeps_higher_precision():
    z = 1.
    exact = .5 * math.erfc(-z / math.sqrt(2.))
    assert abs(_table_cdf(z) - exact) > 1e-9
    assert abs(.5 * _profile_erfc(-z * .7071067811865476) - exact) < 1e-15


@pytest.mark.parametrize("axis,view", [(100, 1), (99, 5), (90, 1), (110, 1)])
def test_gaussian_rows_and_off_frame_mass_conserve_each_side(axis, view):
    buy, sell, off_b, off_s, _, _ = _gaussian_rows(80., 20., 103., 97., 101., axis, view, 1., 3., 3.)
    assert np.nansum(buy) + off_b == pytest.approx(80., abs=1e-11)
    assert np.nansum(sell) + off_s == pytest.approx(20., abs=1e-11)
    assert (buy[np.isfinite(buy)] >= 0).all()
    assert (sell[np.isfinite(sell)] >= 0).all()


def test_flat_bar_mass_has_one_price_and_does_not_invent_opposing_rows():
    buy, sell, off_b, off_s, bimb, simb = _gaussian_rows(70., 30., 100.5, 100.5, 100.5, 100, 2, 1., 3., 3.)
    assert buy[3] == 70.  # Pine half-up tick anchor
    assert sell[3] == 30.
    assert np.isfinite(buy).sum() == 1
    assert off_b == off_s == 0
    assert not bimb.any() and not simb.any()


def test_missing_opposing_rows_differ_from_real_zero_opposing_volume():
    buy, sell = np.array([np.nan, 10., 0.]), np.array([np.nan, 0., 10.])
    bimb, _ = _imbalances(buy, sell, 3.)
    assert not bimb[1]
    sell[0] = 0.
    assert _imbalances(buy, sell, 3.)[0][1]


def test_poc_ties_choose_lower_price_and_value_area_ties_expand_up():
    prices = np.array([99., 100., 101.])
    result = _metrics(prices, np.array([2., 4., 2.]), np.zeros(3), 75., 3., require_positive=True)
    assert result["poc"] == 100.
    assert result["val"] == 100. and result["vah"] == 101.
    result = _metrics(prices, np.ones(3), np.zeros(3), 70., 3., require_positive=True)
    assert result["poc"] == 99.
    # Source comparison rounds float operands, including almost-equal maxima.
    result = _metrics(prices, np.array([1., 1. + 1e-11, 0.]), np.zeros(3), 70., 3., require_positive=True)
    assert result["poc"] == 99.


def test_geometric_engine_split_and_flat_zero_volume_edges():
    frame = bars([98., 102., 100., 100.], high=[102., 102., 100., 100.],
                 low=[98., 98., 100., 100.], volume=[100., 100., 80., 0.])
    got = volume_footprint(frame, tick_size=1., include_diagnostics=False)
    assert got.buy_volume.tolist() == [0., 100., 40., 0.]
    assert got.sell_volume.tolist() == [100., 0., 40., 0.]
    assert got.delta_volume.tolist() == [-100., 100., 0., 0.]
    assert got.buy_share_pct.iloc[:3].tolist() == [0., 100., 50.]
    assert np.isnan(got.buy_share_pct.iloc[-1])
    assert got.engine_data_available.all()  # real zero data is available
    assert (got.available_at == frame.index + pd.Timedelta(minutes=15)).all()


def test_window_search_skips_nonintersecting_bars_instead_of_rolling_last_n():
    frame = bars([100., 200., 100.], volume=[10., 200., 30.])
    got = volume_footprint(frame, tick_size=1., window=2, view_ticks=1, profile_period=2,
                           include_levels=True, include_diagnostics=False).iloc[-1]
    assert got.window_offsets == (0, 2)
    assert got.window_buy_volume + got.window_sell_volume == 40.
    assert got.profile_buy_volume + got.profile_sell_volume == 230.
    assert got.window_in_frame_buy + got.window_off_frame_buy == pytest.approx(got.window_buy_volume)
    assert got.window_in_frame_sell + got.window_off_frame_sell == pytest.approx(got.window_sell_volume)


def test_profile_density_and_integrated_band_are_distinct_units():
    sigma, mu, low, high, amount = 2., 100., 96., 104., 50.
    mass = .5 * math.erfc(-(high - mu) / sigma / math.sqrt(2.)) - .5 * math.erfc(-(low - mu) / sigma / math.sqrt(2.))
    comp = _Component(mu, sigma, amount / (sigma * mass), low, high)
    assert _band_mass(low, high, [comp]) == pytest.approx(amount, abs=1e-13)
    assert float(_density(mu, [comp])) == pytest.approx(amount / (sigma * mass) / math.sqrt(2 * math.pi))
    assert _band_mass(mu - .5, mu + .5, [comp]) < _density(mu, [comp])
    assert _band_mass(110., 112., [comp]) == 0.


def test_flat_atoms_have_dashboard_poc_and_no_fabricated_density_curve():
    frame = bars([100., 100.], high=[100., 100.], low=[100., 100.])
    got = volume_footprint(frame, tick_size=1., include_levels=True)
    assert got.dashboard_poc.tolist() == [100., 100.]
    assert got.chart_poc.isna().all()
    assert got.profile_status.tolist() == ["flat_atoms_only"] * 2
    assert got.profile_overlap_pct.tolist() == [100., 100.]
    assert got.profile_residual_ppm.tolist() == [0., 0.]
    assert all(value == () for value in got.profile_prices)


def test_chart_poc_preserves_source_stale_value_and_exposes_freshness():
    frame = bars([100., 110., 110.], high=[102., 110., 110.], low=[98., 110., 110.])
    got = volume_footprint(frame, tick_size=1., profile_period=2, include_diagnostics=False)
    assert got.chart_poc_fresh.tolist() == [True, True, False]
    assert got.chart_poc.iloc[2] == got.chart_poc.iloc[1]
    assert np.isnan(got.chart_poc_buy_volume.iloc[2])
    assert got.profile_status.iloc[2] == "flat_atoms_only"
    sparse = volume_footprint(frame, tick_size=1., profile_period=2,
                             include_diagnostics=False, observation_positions=[2])
    pd.testing.assert_frame_equal(sparse, got.iloc[[2]], check_exact=True, check_freq=False)


def test_distinct_flat_prices_do_not_enter_source_density_or_band_mass():
    frame = bars([100., 101.], high=[100., 101.], low=[100., 101.])
    got = volume_footprint(frame, tick_size=1.).iloc[-1]
    assert got.profile_status == "atoms_without_density"
    assert got.chart_poc == 100.  # source best=-1 accepts first zero sample
    assert got.chart_poc_buy_volume == got.chart_poc_sell_volume == 0.
    assert got.profile_overlap_pct == 100.


def test_exact_zero_crossing_quirk_is_preserved_in_source_overlap_diagnostic():
    # Buy/sell bells have different centers; source scanner only tests strict
    # sign changes and misses a zero exactly on its12-point scan grid. Do not
    # silently substitute a mathematically corrected overlap implementation.
    got = volume_footprint(bars(), tick_size=1.).iloc[0]
    assert got.profile_overlap_pct == pytest.approx(100., abs=1e-4)
    assert 0 <= got.profile_residual_ppm < 1.


def test_intrabar_uses_actual_signed_totals_and_missing_data_stays_missing():
    frame = bars([100., 100., 100., 100.])
    stream = intrabars(frame, [10., np.nan, 30., np.nan], [-5., np.nan, -7., np.nan])
    got = volume_footprint(frame, tick_size=1., engine="intrabar", intrabar_stream=stream,
                           include_diagnostics=False)
    assert got.engine_data_available.tolist() == [True, False, True, False]
    assert got.intrabar_coverage_bars.tolist() == [1, 0, 1, 0]
    assert got.total_volume.iloc[0] == 15.  # chart OHLCV volume100 must not substitute
    assert got.total_volume.iloc[2] == 37.
    assert got.buy_volume.iloc[[1, 3]].isna().all()
    assert got.engine_observed_at.iloc[[1, 3]].isna().all()
    assert got.profile_data_bars.iloc[-1] == 2


@pytest.mark.parametrize("problem", ["future_ns", "before_open", "positive_down", "unpaired_missing", "na_observed", "naive_observed", "index", "missing_column"])
def test_intrabar_invalid_or_future_observations_fail_closed(problem):
    frame = bars([100., 100.])
    stream = intrabars(frame, [10., 20.], [-5., -7.])
    if problem == "future_ns":
        stream.loc[frame.index[0], "observed_at"] += pd.Timedelta(nanoseconds=1)
    elif problem == "before_open":
        stream.loc[frame.index[0], "observed_at"] = frame.index[0] - pd.Timedelta(nanoseconds=1)
    elif problem == "positive_down":
        stream.iloc[0, 1] = 5.
    elif problem == "unpaired_missing":
        stream.iloc[0, 0] = np.nan
    elif problem == "na_observed":
        stream.iloc[0, 2] = pd.NaT
    elif problem == "naive_observed":
        stream["observed_at"] = stream.observed_at.dt.tz_localize(None)
    elif problem == "index":
        stream.index += pd.Timedelta(minutes=1)
    else:
        stream = stream.drop(columns="up_volume")
    with pytest.raises(ValueError):
        volume_footprint(frame, tick_size=1., engine="intrabar", intrabar_stream=stream)


def test_native_requires_exact_provider_objects_and_geometric_rejects_extra_engine_data():
    frame = bars()
    with pytest.raises(NotImplementedError, match="exact provider"):
        volume_footprint(frame, tick_size=1., engine="native")
    with pytest.raises(ValueError, match="only valid"):
        volume_footprint(frame, tick_size=1., intrabar_stream=intrabars(frame, [1.], [-1.]))
    with pytest.raises(ValueError, match="must not exceed"):
        volume_footprint(frame, tick_size=1., engine="intrabar", intrabar_minutes=60,
                         intrabar_stream=intrabars(frame, [1.], [-1.]))


@pytest.mark.parametrize("kwargs", [{"tick_size": 0}, {"tick_size": np.nan}, {"window": 1},
                                    {"view_ticks": 0}, {"bell_div": 11}, {"profile_period": 1},
                                    {"profile_resolution": 10}, {"value_area_pct": 101},
                                    {"imbalance_pct": 0}, {"include_diagnostics": 1}])
def test_source_parameter_bounds_are_enforced(kwargs):
    with pytest.raises(ValueError):
        volume_footprint(bars(), **({"tick_size": 1.} | kwargs))


def test_as_of_cannot_admit_forming_bar():
    frame = bars()
    with pytest.raises(ValueError, match="forming/future"):
        volume_footprint(frame, tick_size=1., as_of=frame.index[0] + pd.Timedelta(minutes=14))


def test_prefix_invariance_including_levels_and_empty_output_schema():
    frame = bars([100., 101., 100., 102., 99.], volume=[100., 0., 30., 400., 60.])
    kwargs = dict(tick_size=.5, include_levels=True, profile_resolution=20, profile_period=3)
    full = volume_footprint(frame, **kwargs)
    for stop in (0, 1, 3, 4):
        prefix = volume_footprint(frame.iloc[:stop], **kwargs)
        pd.testing.assert_frame_equal(prefix, full.iloc[:stop])
    changed = frame.copy()
    changed.iloc[-1, changed.columns.get_loc("Volume")] = 10000.
    pd.testing.assert_frame_equal(volume_footprint(changed, **kwargs).iloc[:-1], full.iloc[:-1])


def test_disabling_diagnostics_changes_only_diagnostic_outputs():
    frame = bars([100., 101.])
    full = volume_footprint(frame, tick_size=1.)
    off = volume_footprint(frame, tick_size=1., include_diagnostics=False)
    columns = ["profile_overlap_pct", "profile_residual_ppm", "diagnostics_computed"]
    pd.testing.assert_frame_equal(full.drop(columns=columns), off.drop(columns=columns))
    assert off.profile_overlap_pct.isna().all() and not off.diagnostics_computed.any()
