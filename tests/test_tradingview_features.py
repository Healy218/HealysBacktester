"""Local feature projection/causality checks, never exported-Pine parity."""
import numpy as np
import pandas as pd
import pytest

import nn_meta.tradingview_features as tv
from v3.pine_compat import atr
from v3._tv_trend_support import pine_ohlc


def sample(n=310, *, constant=False, rth=False):
    if rth:
        index = pd.DatetimeIndex([stamp for day in pd.bdate_range("2026-08-03", periods=(n + 25) // 26)
                                 for stamp in pd.date_range(str(day.date()) + " 09:30", periods=26, freq="15min", tz="America/New_York")])[:n]
    else:
        index = pd.date_range("2026-08-03", periods=n, freq="15min", tz="America/New_York")
    i = np.arange(n)
    close = np.full(n, 100.) if constant else 100 + np.sin(i / 7) * 3 + np.sin(i / 29)
    opening = close if constant else close - np.sin(i / 3) * .3
    bars = pd.DataFrame({"Open": opening, "High": close + 1, "Low": close - 1,
                         "Close": close, "Volume": 1000. + (i % 17) * 100}, index=index)
    # Synthetic flags are explicitly test data; no exchange grouping inference.
    period = 26 if rth else 96
    flags = pd.DataFrame({"vwap_reset": i % period == 0,
                          "htf_change": i % (2 * period) == 0,
                          "available_at": index}, index=index)
    metadata = {"symbol": "SYNTHETIC", "calendar_id": "synthetic-test-calendar",
                "htf_period": "2D", "vwap_anchor": "synthetic fixture anchor",
                "timeframe_flag_basis": "explicit synthetic test flags; not exchange evidence",
                "chart_session": "RTH synthetic" if rth else "24x7 synthetic",
                "history_origin": index[0].isoformat()}
    return bars, flags, metadata


def calculate(bars, flags, metadata, **kwargs):
    return tv.tradingview_features(bars, minimum_tick=.01, timeframe_flags=flags,
                                  dependency_metadata=metadata,
                                  as_of=bars.index[-1] + pd.Timedelta(minutes=15), **kwargs)


@pytest.fixture(scope="module")
def observation():
    bars, flags, metadata = sample()
    return bars, flags, metadata, calculate(bars, flags, metadata)


def test_fixed_schema_all_thirteen_sources_and_no_admission(observation):
    bars, flags, metadata, result = observation
    assert result.values.shape == (len(bars), 96)
    assert tuple(result.values) == tv.FEATURE_NAMES
    assert len(set(tv.FEATURE_NAMES)) == 96
    assert len({spec.source for spec in tv.FEATURE_SPECS}) == 13
    assert set(result.metadata["source_fixture_identities"]) == {row[1] for row in tv.SOURCE_MAP}
    assert all(pd.api.types.is_float_dtype(result.values[col]) for col in result.values)
    assert not np.isinf(result.values.to_numpy()).any()
    assert result.metadata["external_parity"] is False
    assert result.metadata["model_admission"] is False
    assert result.metadata["external_context_verified"] is False
    assert result.metadata["fixed_parameters"]["footprint"]["include_diagnostics"] is False
    assert result.metadata["fixed_parameters"]["footprint"]["engine"] == "geometric"
    pd.testing.assert_series_equal(result.available_at, pd.Series(bars.index + pd.Timedelta(minutes=15), index=bars.index, name="available_at"))
    # Feature-only publications expose events/levels, never fabricated entry/exit.
    for alias in ("ict", "order_blocks", "liquidity", "htf", "footprint"):
        assert not any("entry" in s.name or "exit" in s.name for s in tv.FEATURE_SPECS if s.source == alias)


@pytest.mark.parametrize("alias,script_id,calculator", tv.SOURCE_MAP, ids=[row[0] for row in tv.SOURCE_MAP])
def test_each_source_projection_preserves_direct_port_observation(observation, alias, script_id, calculator):
    bars, flags, metadata, result = observation
    # Independently invoke each public calculator with its defaults and external
    # dependencies, then check one selected field and its stated normalization.
    kwargs = {}
    if alias == "setup": kwargs["vwap_reset"] = flags.vwap_reset
    if alias == "htf": kwargs["htf_change"] = flags.htf_change
    if alias == "footprint": kwargs.update(tick_size=.01, include_diagnostics=False)
    raw = calculator(bars, **kwargs)
    spec = next(s for s in tv.FEATURE_SPECS if s.source == alias and (
        s.field == "bull_active_count" if alias == "order_blocks" else s.transform in ("price_atr", "range_atr", "percent")))
    expected = raw[spec.field].astype(float)
    if spec.transform == "price_atr": expected = (expected - bars.Close) / atr(pine_ohlc(bars), 14).where(lambda s: s > 0)
    elif spec.transform == "range_atr": expected = expected / atr(pine_ohlc(bars), 14).where(lambda s: s > 0)
    elif spec.transform == "percent": expected = expected / 100
    if spec.valid_when: expected = expected.where(raw[spec.valid_when])
    assert expected.notna().any(), alias
    np.testing.assert_allclose(result.values[spec.name], expected, rtol=0, atol=0, equal_nan=True)
    source_columns = [s.name for s in tv.FEATURE_SPECS if s.source == alias]
    assert result.values[source_columns].notna().any().any()


def test_known_flat_market_and_geometric_allocation_results():
    bars, flags, metadata = sample(210, constant=True)
    result = calculate(bars, flags, metadata).values
    assert (result.tv_gaussian_direction == 0).all()
    assert (result.tv_gaussian_trend_line_distance_atr14.dropna() == 0).all()
    # RMA7 followed by SMA200 becomes available at index205; constant range2 / ATR2 = 1.
    assert result.tv_fibonacci_volatility_atr14.iloc[:205].isna().all()
    assert (result.tv_fibonacci_volatility_atr14.iloc[205:] == 1).all()
    assert (result.tv_structure_market_direction == 1).all()
    assert (result.tv_sr_inside_channel == 0).all()
    assert (result.tv_order_blocks_bull_active_count == 0).all()
    assert (result.tv_amd_all_closed == 0).all()
    assert (result.tv_probability_resolved_total == 0).all()
    assert result.tv_probability_long_reference_win_pct_fraction.isna().all()
    assert (result.tv_setup_vwap_distance_atr14.dropna() == 0).all()
    assert result.tv_ict_NYAM_in_session.sum() == 12  # six 15m bars in each of two completed NYAM windows
    assert (result.tv_ict_NYAM_range_value_atr14.dropna() == 1).all()
    np.testing.assert_allclose(result.tv_liquidity_poc_price_distance_atr14.dropna(), 0, atol=1e-12)
    # Source's accumulated log regression has floating cancellation near zero.
    np.testing.assert_allclose(result.tv_htf_regression_end_distance_atr14.dropna(), 0, atol=4e-12)
    np.testing.assert_allclose(result.tv_footprint_buy_share_pct_fraction, .5, atol=0)
    np.testing.assert_allclose(result.tv_footprint_profile_tilt_pct_fraction, 0, atol=0)
    assert (result.tv_footprint_chart_poc_fresh == 1).all()


def test_default_order_block_confirmed_at_ten_right_bars_without_origin_backfill():
    bars, flags, metadata = sample(111, constant=True)
    bars.iloc[100] = [100, 101, 90, 100, 2000]
    bars.iloc[101] = [100, 104, 95, 103, 1000]
    bars.iloc[102:] = [103, 105, 96, 104, 1000]
    result = calculate(bars, flags, metadata).values
    assert (result.tv_order_blocks_bull_active_count.iloc[:110] == 0).all()
    assert result.tv_order_blocks_bull_active_count.iloc[110] == 1
    source_atr = scale_atr = 2.
    for tr in [11.] + [9.] * 10:
        source_atr = source_atr * .99 + tr * .01
        scale_atr = scale_atr * 13 / 14 + tr / 14
    expected_trigger = 90 + 4 * source_atr
    assert result.tv_order_blocks_bull_latest_trigger_distance_atr14.iloc[110] == pytest.approx((expected_trigger - 104) / scale_atr)
    assert result.tv_order_blocks_bull_latest_trigger_distance_atr14.iloc[:110].isna().all()


@pytest.mark.parametrize("prefix", [99, 205, 257])
def test_all_columns_are_prefix_invariant_at_warmup_and_session_edges(observation, prefix):
    bars, flags, metadata, full = observation
    part = calculate(bars.iloc[:prefix], flags.iloc[:prefix], metadata)
    pd.testing.assert_frame_equal(part.values, full.values.iloc[:prefix], check_exact=True)
    pd.testing.assert_series_equal(part.available_at, full.available_at.iloc[:prefix])
    assert part.metadata["configuration_sha256"] == full.metadata["configuration_sha256"]


def test_future_prices_volume_and_flags_do_not_change_prior_features(observation):
    bars, flags, metadata, full = observation
    altered = bars.copy()
    altered.iloc[210:, :4] += 15
    altered.loc[altered.index[210:], "Volume"] *= 9
    changed_flags = flags.copy()
    changed_flags.loc[changed_flags.index[240], ["vwap_reset", "htf_change"]] = True
    later = calculate(altered, changed_flags, metadata)
    pd.testing.assert_frame_equal(later.values.iloc[:210], full.values.iloc[:210], check_exact=True)
    assert later.metadata["bar_input_sha256"] != full.metadata["bar_input_sha256"]
    assert later.metadata["timeframe_flags_sha256"] != full.metadata["timeframe_flags_sha256"]


def test_rth_requires_explicit_literal_policy_without_invented_orb_reset():
    bars, flags, metadata = sample(52, rth=True)
    with pytest.raises(ValueError, match="outside-session bars"):
        calculate(bars, flags, metadata)
    result = calculate(bars, flags, metadata, session_policy="source_literal")
    assert result.values.tv_setup_session_gap.sum() == 1
    assert result.values.tv_setup_session_gap.iloc[26] == 1
    assert result.values.tv_setup_or_done.iloc[26] == 1  # source literal: no new 09:30 reset
    assert result.metadata["setup_session_gap_count"] == 1
    assert result.metadata["fixed_parameters"]["setup"]["strict_session_coverage"] is False


@pytest.mark.parametrize("problem", ["missing_flags", "nonboolean", "late_flag", "missing_availability", "wrong_period", "naive_bars", "forming_bar", "rebased_origin", "off_grid", "negative_volume", "no_asof"])
def test_required_context_fails_closed_before_any_port(monkeypatch, problem):
    bars, flags, metadata = sample(20)
    kwargs = dict(minimum_tick=.01, timeframe_flags=flags, dependency_metadata=metadata,
                  as_of=bars.index[-1] + pd.Timedelta(minutes=15))
    if problem == "missing_flags": kwargs["timeframe_flags"] = flags.drop(columns="htf_change")
    elif problem == "nonboolean": flags["htf_change"] = flags.htf_change.astype(int)
    elif problem == "late_flag": flags.loc[flags.index[4], "available_at"] += pd.Timedelta(nanoseconds=1)
    elif problem == "missing_availability": flags.loc[flags.index[4], "available_at"] = pd.NaT
    elif problem == "wrong_period": metadata["htf_period"] = "D"
    elif problem == "naive_bars": bars.index = bars.index.tz_localize(None)
    elif problem == "forming_bar": kwargs["as_of"] -= pd.Timedelta(nanoseconds=1)
    elif problem == "rebased_origin": bars = bars.iloc[1:]; kwargs["timeframe_flags"] = flags.iloc[1:]
    elif problem == "off_grid": bars.index += pd.Timedelta(minutes=1); flags.index = bars.index
    elif problem == "negative_volume": bars.iloc[0, bars.columns.get_loc("Volume")] = -1
    elif problem == "no_asof": kwargs["as_of"] = None
    monkeypatch.setattr(tv, "build_catalog", lambda *a: pytest.fail("invalid inputs reached calculators"))
    with pytest.raises(ValueError): tv.tradingview_features(bars, **kwargs)


def test_datetime_units_do_not_change_grid_or_feature_values():
    bars, flags, metadata = sample(20)
    before = calculate(bars, flags, metadata)
    bars.index = bars.index.as_unit("ms")
    flags.index = bars.index
    flags["available_at"] = flags.available_at.astype("datetime64[ms, America/New_York]")
    after = calculate(bars, flags, metadata)
    np.testing.assert_allclose(before.values, after.values, rtol=0, atol=0, equal_nan=True)
    assert before.metadata["bar_input_sha256"] == after.metadata["bar_input_sha256"]


def test_feature_schema_exposes_capture_settings_without_computing_bars():
    schema = tv.feature_schema(minimum_tick=.05, session_policy="source_literal")
    assert len(schema["columns"]) == 96 and len(schema["parameters"]) == 13
    assert schema["parameters"]["uptrick"]["minimum_tick"] == .05
    assert schema["parameters"]["amd"]["config"]["minimum_tick"] == .05
    assert schema["parameters"]["footprint"]["profile_resolution"] == 100
    assert schema["parameters"]["htf"]["auto_htf"] is True
    assert schema["external_parity"] is False and schema["model_admission"] is False


def test_explicit_observed_vwap_needs_no_invented_reset_flags():
    bars, flags, metadata = sample(30)
    # A deliberately different supplied series proves that the bridge consumes
    # the observed source value instead of deriving an implicit daily anchor.
    observed = pd.DataFrame({"vwap": bars.Close + 2,
                             "available_at": bars.index + pd.Timedelta(minutes=15)}, index=bars.index)
    result = calculate(bars, flags.drop(columns="vwap_reset"), metadata, vwap_observations=observed)
    expected = 2 / atr(pine_ohlc(bars), 14).where(lambda s: s > 0)
    np.testing.assert_allclose(result.values.tv_setup_vwap_distance_atr14, expected, equal_nan=True)
    assert result.metadata["vwap_mode"] == "observed"
    assert result.metadata["vwap_observations_sha256"]
    with pytest.raises(ValueError, match="timeframe_flags"):
        calculate(bars, flags, metadata, vwap_observations=observed)
    observed.iloc[-1, observed.columns.get_loc("available_at")] += pd.Timedelta(nanoseconds=1)
    with pytest.raises(ValueError, match="unavailable"):
        calculate(bars, flags.drop(columns="vwap_reset"), metadata, vwap_observations=observed)
