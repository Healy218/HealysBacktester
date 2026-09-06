"""Fixed-default proposal/replay contracts; no external-Pine parity claim."""
from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from nn_meta import config, proposals
from nn_meta import tradingview_proposals as tv
from nn_meta.tradingview_features import SOURCE_MAP
from v3.tv_amd_po3 import AmdConfig
from v3.tv_setup_scanner import SETUPS


def data(n=310):
    index = pd.DatetimeIndex([stamp for day in pd.bdate_range("2026-08-03", periods=(n + 25) // 26)
                              for stamp in pd.date_range(str(day.date()) + " 09:30", periods=26,
                                                        freq="15min", tz="America/New_York")])[:n]
    i = np.arange(n)
    close = 100 + np.sin(i / 7) * 4 + np.sin(i / 29)
    bars = pd.DataFrame({"Open": close - np.sin(i / 3) * .3, "High": close + 1,
                         "Low": close - 1, "Close": close, "Volume": 1000. + (i % 17) * 100}, index=index)
    flags = pd.DataFrame({"vwap_reset": i % 26 == 0, "htf_change": i % 52 == 0,
                          "available_at": index}, index=index)
    metadata = {"symbol": "SYNTHETIC", "calendar_id": "synthetic-test-calendar", "htf_period": "2D",
                "vwap_anchor": "synthetic fixture anchor", "timeframe_flag_basis": "synthetic test only",
                "chart_session": "RTH synthetic", "history_origin": index[0].isoformat()}
    context = dict(minimum_tick=.05, timeframe_flags=flags, dependency_metadata=metadata,
                   as_of=index[-1] + pd.Timedelta(minutes=15), session_policy="source_literal")
    return bars, context


@pytest.fixture(scope="module")
def source_outputs():
    bars, context = data()
    result = {}
    calculators = {alias: calc for alias, _, calc in SOURCE_MAP}
    for strategy, info in tv.SOURCE_METADATA.items():
        kwargs = {}
        if strategy == "tv_uptrick": kwargs["minimum_tick"] = .05
        if strategy == "tv_amd": kwargs["config"] = AmdConfig(minimum_tick=.05)
        if strategy == "tv_setup":
            kwargs.update(vwap_reset=context["timeframe_flags"].vwap_reset, strict_session_coverage=False)
        result[strategy] = calculators[info["alias"]](bars, **kwargs)
    return bars, context, result


def assert_frames_equal(left, right):
    for a, b in zip(left, right):
        if a is None or b is None:
            assert a is None and b is None
        else:
            pd.testing.assert_frame_equal(a, b, check_exact=True)


def test_baseline_naive_utc_adapter_preserves_expanded_events():
    bars, context = data()
    bars.index = bars.index.tz_convert("UTC")
    context["timeframe_flags"].index = context["timeframe_flags"].index.tz_convert("UTC")
    bars.attrs[tv.CONTEXT_ATTRIBUTE] = context
    expected = proposals.sweep_signals("tv_gaussian", bars)
    naive = bars.copy()
    naive.index = naive.index.tz_localize(None)
    actual = proposals.sweep_signals("tv_gaussian", naive)
    for left, right in zip(actual, expected):
        if left is not None:
            pd.testing.assert_frame_equal(left, right.tz_localize(None))
    assert naive.index.tz is None
    assert naive.attrs[tv.CONTEXT_ATTRIBUTE]["timeframe_flags"].index.tz is not None


@pytest.mark.parametrize("strategy", tv.STRATEGIES)
def test_fixed_default_events_match_direct_source_outputs(source_outputs, strategy):
    bars, context, raw = source_outputs
    frames = tv.sweep_signals(strategy, bars, context=context, enable_shorting=True)
    output = raw[strategy]
    if strategy == "tv_fibonacci":
        fields = ("bull_signal", "bear_flip", "bear_signal", "bull_flip")
    elif strategy in ("tv_rsi_probability", "tv_amd"):
        fields = ("long_entry", "long_exit", "short_entry", "short_exit")
    else:
        fields = ("bull_signal", "bear_signal", "bear_signal", "bull_signal")
    if strategy == "tv_setup":
        assert list(frames[0].columns.get_level_values("setup_identity")) == list(SETUPS)
        for name in SETUPS:
            for frame, suffix in zip(frames, ("long_entry", "long_exit", "short_entry", "short_exit")):
                np.testing.assert_array_equal(frame[(name, 1.2, 60)], output[f"{name}_{suffix}"])
    else:
        assert frames[0].shape[1] == 1
        for frame, field in zip(frames, fields):
            np.testing.assert_array_equal(frame.iloc[:, 0], output[field])
    assert frames[0].index.equals(bars.index)
    assert frames[0].attrs["tradingview_proposal"]["active_pool_admission"] is False
    assert frames[0].attrs["tradingview_proposal"]["external_parity"] is False


@pytest.mark.parametrize("strategy", tv.STRATEGIES)
def test_router_all_columns_recover_typed_params_and_replay_exactly(source_outputs, strategy, monkeypatch):
    bars, context, _ = source_outputs
    attached = bars.copy()
    attached.attrs[tv.CONTEXT_ATTRIBUTE] = context
    monkeypatch.setattr(config, "ENABLE_SHORTING", True)
    swept = proposals.sweep_signals(strategy, attached)
    portfolio = SimpleNamespace(wrapper=SimpleNamespace(columns=swept[0].columns))
    for i, column in enumerate(swept[0].columns):
        params = proposals.params_from_portfolio(portfolio, i)
        if strategy == "tv_setup":
            assert isinstance(params["setup_identity"], str)
        single = proposals.single_signals(strategy, attached, params)
        selected = proposals._select_col(swept, params)
        assert_frames_equal(single, selected)
        assert_frames_equal(single, tuple(frame[[column]] for frame in swept))


@pytest.mark.parametrize("strategy", tv.STRATEGIES)
def test_full_context_can_be_used_by_training_prefix_without_rebase(source_outputs, strategy):
    bars, context, _ = source_outputs
    full = tv.sweep_signals(strategy, bars, context=context, enable_shorting=True)
    prefix = bars.iloc[:205]
    early = tv.sweep_signals(strategy, prefix, context=context, enable_shorting=True)
    assert_frames_equal(early, tuple(frame.iloc[:205] for frame in full))
    info = early[0].attrs["tradingview_proposal"]
    assert pd.Timestamp(info["as_of"]) == prefix.index[-1] + pd.Timedelta(minutes=15)
    assert info["history_origin"] == context["dependency_metadata"]["history_origin"]
    assert len(context["timeframe_flags"]) == len(bars)
    assert context["as_of"] == bars.index[-1] + pd.Timedelta(minutes=15)


def test_string_selection_is_typed_and_numeric_legacy_recovery_stays_compatible():
    columns = pd.MultiIndex.from_tuples([("VWAP", 1.2, 60), ("EMA", 1.2, 60)],
                                       names=["setup_identity", "setup_stop_atr", "setup_max_bars"])
    frame = pd.DataFrame([[True, False], [False, True]], columns=columns)
    params = proposals.params_from_portfolio(SimpleNamespace(wrapper=SimpleNamespace(columns=columns)), 1)
    assert params == {"setup_identity": "EMA", "setup_stop_atr": 1.2, "setup_max_bars": 60}
    result = proposals._select_col((frame, frame, None, None), params)
    assert result[0].iloc[:, 0].tolist() == [False, True]
    assert result[2:] == (None, None)
    with pytest.raises(KeyError):
        proposals._select_col((frame, frame, None, None), {**params, "setup_identity": "ema"})
    legacy = pd.MultiIndex.from_tuples([("14", "0.5")], names=["window", "mult"])
    assert proposals.params_from_portfolio(SimpleNamespace(wrapper=SimpleNamespace(columns=legacy)), 0) == {"window": 14, "mult": .5}


@pytest.mark.parametrize("bad_params", [
    {"gaussian_length": 15, "gaussian_poles": 4},
    {"gaussian_length": "14", "gaussian_poles": 4},
    {"gaussian_length": True, "gaussian_poles": 4},
    {"gaussian_length": 14},
    {"gaussian_length": 14, "gaussian_poles": 4, "extra": 0},
])
def test_frozen_nondefaults_fail_before_calculation(bad_params, monkeypatch):
    monkeypatch.setattr(tv, "_context_for_prefix", lambda *args: pytest.fail("invalid grid reached calculation"))
    with pytest.raises(ValueError):
        tv.single_signals("tv_gaussian", None, bad_params, context=None)


@pytest.mark.parametrize("problem", ["missing", "unknown_setting", "late_flag", "wrong_origin", "suffix", "reordered", "forming", "unknown_asof"])
def test_context_must_be_explicit_causal_and_same_history(problem):
    bars, context = data(80)
    if problem == "missing": context = None
    elif problem == "unknown_setting": context["invent_native_events"] = True
    elif problem == "late_flag": context["timeframe_flags"].iloc[2, 2] += pd.Timedelta(nanoseconds=1)
    elif problem == "wrong_origin": context["dependency_metadata"]["history_origin"] = bars.index[1].isoformat()
    elif problem == "suffix": bars = bars.iloc[1:]
    elif problem == "reordered": bars = bars.iloc[::-1]
    elif problem == "forming": context["as_of"] -= pd.Timedelta(nanoseconds=1)
    elif problem == "unknown_asof": context["as_of"] = pd.NaT
    with pytest.raises(ValueError): tv.sweep_signals("tv_gaussian", bars, context=context)


def test_observed_vwap_is_sliced_with_prefix_and_future_changes_do_not_leak():
    bars, context = data(100)
    context["timeframe_flags"] = context["timeframe_flags"].drop(columns="vwap_reset")
    context["vwap_observations"] = pd.DataFrame({"vwap": bars.Close + .5,
        "available_at": bars.index + pd.Timedelta(minutes=15)}, index=bars.index)
    prefix = bars.iloc[:60]
    before = tv.sweep_signals("tv_setup", prefix, context=context, enable_shorting=True)
    future = deepcopy(context)
    future["vwap_observations"].iloc[60:, 0] += 50
    future["timeframe_flags"].iloc[60:, 0] = True
    after = tv.sweep_signals("tv_setup", prefix, context=future, enable_shorting=True)
    assert_frames_equal(before, after)
    full = tv.sweep_signals("tv_setup", bars, context=context, enable_shorting=True)
    assert_frames_equal(before, tuple(frame.iloc[:60] for frame in full))


def test_shorting_disabled_and_missing_router_context_fail_explicitly():
    bars, context = data(30)
    frames = tv.sweep_signals("tv_gaussian", bars, context=context)
    assert frames[2:] == (None, None)
    with pytest.raises(ValueError, match="context"):
        proposals.sweep_signals("tv_gaussian", bars)
    for feature_only in ("tv_ict", "tv_order_blocks", "tv_liquidity", "tv_htf", "tv_footprint"):
        with pytest.raises(ValueError, match="not a directional"):
            tv.sweep_signals(feature_only, bars, context=context)


def test_exported_registry_has_only_source_defaults_and_no_admission():
    registry = tv.registry_metadata(minimum_tick=.05, session_policy="source_literal", vwap_mode="observed")
    assert len(registry["strategies"]) == 8
    assert all(len(choices) == 1 for s, grid in registry["grids"].items() for key, choices in grid.items() if key != "setup_identity")
    assert registry["parameters"]["tv_setup"]["enabled"] == list(SETUPS)
    assert registry["parameters"]["tv_setup"]["max_open"] == 1
    assert registry["parameters"]["tv_uptrick"]["minimum_tick"] == .05
    assert registry["parameters"]["tv_amd"]["config"]["minimum_tick"] == .05
    assert set(registry["required_source_event_fields"]) == {r["script_id"] for r in tv.SOURCE_METADATA.values()}
    assert len(registry["required_source_event_fields"]["XWuYNmhD"]) == 24
    assert "long_exit" in registry["required_source_event_fields"]["c25U5rsF"]
    assert "bear_flip" in registry["required_source_event_fields"]["U7CZ8jtj"]
    assert set(registry["wrapper_runtime"]) == set(tv.STRATEGIES)
    assert registry["wrapper_runtime"]["tv_setup"]["module"] == "signals.tv_setup_scanner_signals"
    assert registry["wrapper_runtime"]["tv_gaussian"]["function"] == "generate_gaussian_filter_signals"
    assert all(len(record["sha256"]) == 64 for record in registry["wrapper_runtime"].values())
    assert registry["external_parity"] is False and registry["active_pool_admission"] is False


def test_registry_identity_changes_when_a_called_wrapper_module_changes(tmp_path, monkeypatch):
    source = tmp_path / "adapter.py"
    source.write_text("first wrapper behavior")
    actual = tv.inspect.getsourcefile
    monkeypatch.setattr(tv.inspect, "getsourcefile", lambda function: str(source)
        if function is tv.tv_setup_scanner_signals.generate_setup_scanner_signals else actual(function))
    before = tv.registry_metadata(minimum_tick=.01, session_policy="source_literal")
    source.write_text("other wrapper behavior")
    after = tv.registry_metadata(minimum_tick=.01, session_policy="source_literal")
    assert before["wrapper_runtime"]["tv_setup"]["sha256"] != after["wrapper_runtime"]["tv_setup"]["sha256"]
    assert before["wrapper_runtime"]["tv_gaussian"] == after["wrapper_runtime"]["tv_gaussian"]


def test_registry_refuses_uninspectable_wrapper(monkeypatch):
    monkeypatch.setattr(tv.inspect, "getsourcefile", lambda function: None)
    with pytest.raises(ValueError, match="inspectable source"):
        tv.registry_metadata(minimum_tick=.01, session_policy="source_literal")


def test_extending_a_grid_cannot_silently_enable_unverified_optimization(monkeypatch):
    bars, context = data(20)
    monkeypatch.setitem(tv.SWEEP_GRIDS["tv_gaussian"], "gaussian_length", (14, 16))
    with pytest.raises(ValueError, match="source defaults"):
        tv.sweep_signals("tv_gaussian", bars, context=context)
    with pytest.raises(ValueError, match="source defaults"):
        tv.registry_metadata(minimum_tick=.05, session_policy="source_literal")
