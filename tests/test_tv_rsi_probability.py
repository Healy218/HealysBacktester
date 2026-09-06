"""Causal source-reference tests; these are not TradingView-exported fixtures."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from signals.tv_rsi_probability_signals import generate_rsi_probability_signals
from v3.tv_rsi_probability import RsiProbabilityState, rsi_probability_matrix


def bars(close):
    close = np.asarray(close, dtype=float)
    return pd.DataFrame({"Open": close, "High": close + 1, "Low": close - 1,
                         "Close": close, "Volume": 1000.0},
                        index=pd.date_range("2025-01-02 15:00", periods=len(close), freq="15min", tz="UTC"))


def observe(state, **updates):
    values = {"high": 101, "low": 99, "close": 100, "rsi": 35.5, "atr": 2,
              "raw_long": False, "raw_short": False, "atr_multiplier": 3}
    values.update(updates)
    return state.step(**values)


def test_reference_source_license_and_hash_are_pinned():
    folder = Path(__file__).parents[1] / "indicators" / "tradingview_sources"
    manifest = json.loads((folder / "probability_manifest.json").read_text())
    source = manifest["scripts"][0]
    assert source["public_id"] == "c25U5rsF" and source["publication_version"] == 1
    assert source["license"] == "CC-BY-NC-SA-4.0"
    assert hashlib.sha256((folder / source["source_file"]).read_bytes()).hexdigest() == source["sha256"]
    assert "pending" in manifest["parity_status"].lower()


def test_hand_computed_rsi_crossover_stop_then_opposite_entry():
    result = rsi_probability_matrix(bars([10, 9, 8, 9, 8, 9]), rsi_period=2,
                                    signal_period=2, atr_period=2, atr_multiplier=1,
                                    oversold=80, overbought=20, include_matrix=True)
    np.testing.assert_allclose(result.rsi, [np.nan, np.nan, 0, 50, 25, 62.5], equal_nan=True)
    np.testing.assert_allclose(result.signal, [np.nan, np.nan, np.nan, 25, 37.5, 43.75], equal_nan=True)
    assert result.short_entry.tolist() == [False, False, False, False, True, False]
    assert result.long_entry.tolist() == [False, False, False, False, False, True]
    assert result.short_exit.tolist() == [False, False, False, False, False, True]
    assert result.entry_rsi_bucket.iloc[-1] == 63  # math.round(62.5), not banker's rounding
    assert result.resolution_rsi_bucket.iloc[-1] == 25
    assert result.resolution_outcome.iloc[-1] == -1
    assert result.short_losses_rsi_025.tolist() == [0, 0, 0, 0, 0, 1]
    assert result.total_short_losses.iloc[-1] == 1


@pytest.mark.parametrize("side,bucket", [(1, 36), (-1, 76)])
def test_entry_bar_extremes_ignored_then_target_wins_ambiguous_later_bar(side, bucket):
    state = RsiProbabilityState()
    entry = observe(state, high=200, low=0, rsi=bucket - 0.5,
                    raw_long=side == 1, raw_short=side == -1)
    assert entry["active_side"] == side and entry["resolved_total"] == 0
    assert not entry["ambiguous_resolution"]
    assert entry["entry_rsi_bucket"] == bucket
    resolved = observe(state, high=110, low=90)
    assert resolved["resolution_outcome"] == 1
    assert resolved["resolution_side"] == side and resolved["ambiguous_resolution"]
    assert resolved["resolved_total"] == 1 and resolved["active_side"] == 0
    expected_row = 0 if side == 1 else 2
    assert state.counts[expected_row, bucket] == 1
    assert state.counts.sum() == 1


def test_resolution_updates_statistics_before_same_bar_reentry_only_once():
    state = RsiProbabilityState()
    first = observe(state, raw_long=True)
    assert first["entry_prior_wins"] == 0 and first["entry_prior_win_pct"] == 0
    next_entry = observe(state, high=200, low=0, raw_long=True)
    assert next_entry["long_exit"] and next_entry["long_entry"]
    assert next_entry["entry_prior_wins"] == 1 and next_entry["entry_prior_win_pct"] == 100
    assert next_entry["active_side"] == 1 and next_entry["resolved_total"] == 1
    unchanged = observe(state)
    assert unchanged["active_side"] == 1 and unchanged["resolved_total"] == 1


def test_opposite_raw_signal_is_observable_but_suppressed_while_active():
    state = RsiProbabilityState()
    observe(state, raw_long=True)
    blocked = observe(state, rsi=75, raw_short=True)
    assert blocked["raw_short_signal"] and not blocked["short_entry_signal"]
    assert not blocked["short_entry"] and blocked["active_side"] == 1
    assert blocked["resolved_total"] == 0


def test_atr_unavailable_retains_source_condition_without_opening_trade():
    result = observe(RsiProbabilityState(), raw_long=True, atr=np.nan)
    assert result["long_entry_signal"] and not result["long_entry"]
    assert result["active_side"] == 0


def test_only_resolved_outcomes_count_and_snapshot_restart_is_detached():
    original = RsiProbabilityState()
    observe(original, raw_long=True)
    snapshot = json.loads(json.dumps(original.snapshot()))
    resumed = RsiProbabilityState.from_snapshot(snapshot)
    snapshot["counts"][0][36] = 999  # a caller mutation must not alter restored state
    stopped = observe(resumed, high=102, low=92)
    uninterrupted = observe(original, high=102, low=92)
    assert stopped == uninterrupted
    assert stopped["resolution_outcome"] == -1
    assert resumed.counts[1, 36] == 1 and resumed.counts[0, 36] == 0
    broken = resumed.snapshot()
    broken["counts"][0][0] = -1
    with pytest.raises(ValueError, match="invalid probability count"):
        RsiProbabilityState.from_snapshot(broken)


def test_matrix_snapshots_prefixes_and_future_perturbations_are_causal():
    rng = np.random.default_rng(719)
    data = bars(100 + np.cumsum(rng.normal(size=300)))
    params = dict(rsi_period=5, signal_period=5, atr_period=5, atr_multiplier=0.5,
                  oversold=100, overbought=0, include_matrix=True)
    full = rsi_probability_matrix(data, **params)
    assert full.resolved_total.iloc[-1] > 5
    for stop in (1, 8, 80, 190, 299):
        pd.testing.assert_frame_equal(rsi_probability_matrix(data.iloc[:stop], **params), full.iloc[:stop])
    altered = data.copy()
    altered.loc[altered.index[190:], ["Open", "High", "Low", "Close"]] *= 2
    pd.testing.assert_frame_equal(rsi_probability_matrix(altered, **params).iloc[:190], full.iloc[:190])
    # Each final-chart bucket is represented by its own time series; no row
    # can acquire a later resolution before that resolution actually occurs.
    matrix = full.filter(regex=r"^(long|short)_(wins|losses)_rsi_")
    assert matrix.shape[1] == 404
    np.testing.assert_array_equal(matrix.sum(axis=1), full.resolved_total)
    assert (matrix.diff().fillna(0) >= 0).all().all()


def test_sweep_and_frozen_paths_match_all_four_signal_frames():
    rng = np.random.default_rng(539)
    data = bars(100 + np.cumsum(rng.normal(size=160)))
    fixed = dict(oversold=100, overbought=0, atr_period=5)
    sweep = generate_rsi_probability_signals(data, [3, 5], [3, 5], [0.5, 1.0],
                                             enable_shorting=True, **fixed)
    for column in sweep[0].columns:
        frozen = generate_rsi_probability_signals(data, *([x] for x in column),
                                                  enable_shorting=True, **fixed)
        for expected, actual in zip(sweep, frozen):
            pd.testing.assert_series_equal(expected[column], actual[column])
    assert all(frame.dtypes.eq(bool).all() for frame in sweep)
    long_only = generate_rsi_probability_signals(data, [3, 5], [3, 5], [0.5, 1.0], **fixed)
    pd.testing.assert_frame_equal(long_only[0], sweep[0])
    pd.testing.assert_frame_equal(long_only[1], sweep[1])
    assert long_only[2:] == (None, None)


def test_empty_frame_schema_and_invalid_market_inputs():
    empty = rsi_probability_matrix(bars([]), include_matrix=True)
    assert empty.empty and "short_losses_rsi_100" in empty
    invalid = bars([100, 101])
    invalid.loc[invalid.index[1], "Close"] = np.nan
    with pytest.raises(ValueError, match="finite OHLC"):
        rsi_probability_matrix(invalid)
    with pytest.raises(ValueError, match="atr_multiplier must be finite"):
        rsi_probability_matrix(bars([100]), atr_multiplier=np.inf)
