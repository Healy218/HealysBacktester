"""Pinned-source structure tests; external TradingView fixtures remain pending."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from signals.tv_structure_signals import generate_market_structure_signals, generate_sr_channel_signals
from v3.tv_market_structure import market_structure_break
from v3.tv_sr_channels import support_resistance_channels


def bars(close, half_range=0.5):
    close = np.asarray(close, dtype=float)
    return pd.DataFrame({"Open": close, "High": close + half_range, "Low": close - half_range,
                         "Close": close, "Volume": 1000.},
                        index=pd.date_range("2025-01-02", periods=len(close), freq="15min", tz="UTC"))


def test_source_versions_hashes_and_partial_scope_remain_explicit():
    root = Path(__file__).parents[1] / "indicators/tradingview_sources"
    manifest = json.loads((root / "structure_manifest.json").read_text())
    assert {s["public_id"] for s in manifest["scripts"]} == {"DkE7UniD", "Ej53t8Wv"}
    for entry in manifest["scripts"]:
        assert hashlib.sha256((root / entry["source_file"]).read_bytes()).hexdigest() == entry["sha256"]
        assert entry["license"] == "MPL-2.0"
        assert "pending" in entry["admission_status"]
    assert "box" in manifest["scripts"][0]["excluded_scope"]


def test_msb_shifted_barssince_and_initial_change_are_not_backdated():
    source = bars([10, 12, 9, 11, 8, 10, 7, 15, 10, 16, 9, 17])
    result = market_structure_break(source, zigzag_length=2, fib_factor=0)
    # Initial trend flips to down, but ta.change has no preceding observation.
    assert result.zigzag_direction.iloc[0] == -1
    assert not result.high_confirmed.iloc[0]
    assert result.high_0.iloc[:2].isna().all()
    # The source's shifted barssince uses length1 here, so its first confirmed
    # high is current9.5, not the visually more intuitive preceding12.5.
    assert result.high_0.iloc[2] == 9.5
    assert result.high_0_index.iloc[2] == 2
    assert np.flatnonzero(result.bear_signal).tolist() == [3]
    assert np.flatnonzero(result.bull_signal).tolist() == [8]
    assert result.market_direction.tolist() == [1, 1, 1, -1, -1, -1, -1, -1, 1, 1, 1, 1]


def test_sr_pivot_availability_strength_and_break_alert():
    source = bars([1, 2, 3, 4, 5, 4, 3, 2, 1, 2, 3, 4, 5, 4, 3, 2, 1, 7], .1)
    result = support_resistance_channels(source, pivot_period=4, channel_width_pct=1, lookback=100)
    assert result.pivot_high.iloc[:8].isna().all()
    assert result.pivot_high.iloc[8] == 5.1
    assert result.pivot_index.iloc[8] == 4
    assert result.channel_1_top.iloc[:8].isna().all()
    assert result.channel_1_top.iloc[8] == 5.1
    assert result.channel_1_strength.iloc[8] == 21  # pivot20 + one high touch
    assert result.channel_1_strength.iloc[16] == 42  # two pivots + two touches
    assert result.bull_signal.iloc[17]
    assert not result.bull_signal.iloc[:17].any()
    assert not result.bear_signal.any()


def test_sr_channels_are_historical_snapshots_not_final_extended_boxes():
    source = bars([1, 2, 3, 4, 5, 4, 3, 2, 1, 2, 3, 4, 5, 4, 3, 2, 1], .1)
    result = support_resistance_channels(source, pivot_period=4, channel_width_pct=1, lookback=100)
    assert result.channel_1_top.iloc[8:12].eq(5.1).all()
    assert result.channel_1_top.iloc[12:16].eq(.9).all()
    assert result.channel_1_top.iloc[16] == 5.1


def test_sr_strength_threshold_can_suppress_all_channels_and_events():
    source = bars([1, 2, 3, 4, 5, 4, 3, 2, 1, 2, 3, 4, 5, 4, 3, 2, 1, 7], .1)
    result = support_resistance_channels(source, pivot_period=4, minimum_strength=100)
    assert result.channel_1_top.isna().all()
    assert not result.bull_signal.any() and not result.bear_signal.any()


@pytest.mark.parametrize("calculator", [market_structure_break, support_resistance_channels])
def test_structure_prefix_and_future_perturbation_invariance(calculator):
    source = bars(100 + np.random.default_rng(854).normal(0, 2, 330).cumsum())
    full = calculator(source)
    for end in (1, 20, 70, 201, 320):
        pd.testing.assert_frame_equal(calculator(source.iloc[:end]), full.iloc[:end])
    changed = source.copy()
    changed.iloc[210:, :4] *= 3
    pd.testing.assert_frame_equal(calculator(changed).iloc[:210], full.iloc[:210])


@pytest.mark.parametrize("generator,grids", [
    (generate_market_structure_signals, ([5, 9], [0, .33])),
    (generate_sr_channel_signals, ([4, 10], [1, 5])),
])
def test_structure_sweep_matches_all_four_frozen_frames(generator, grids):
    source = bars(100 + np.random.default_rng(1).normal(0, 2, 120).cumsum())
    sweep = generator(source, *grids, enable_shorting=True)
    for column in sweep[0].columns:
        frozen = generator(source, *([v] for v in column), enable_shorting=True)
        for expected, actual in zip(sweep, frozen):
            pd.testing.assert_series_equal(expected[column], actual[column])
    long_only = generator(source, *grids)
    assert long_only[2:] == (None, None)


@pytest.mark.parametrize("calculator", [market_structure_break, support_resistance_channels])
def test_structure_rejects_invalid_observations_and_handles_empty(calculator):
    source = bars([1, 2, 3])
    assert calculator(source.iloc[:0]).empty
    with pytest.raises(ValueError, match="unique and increasing"):
        calculator(source.iloc[::-1])
    source.iloc[1, source.columns.get_loc("Close")] = np.nan
    with pytest.raises(ValueError, match="finite OHLC"):
        calculator(source)
