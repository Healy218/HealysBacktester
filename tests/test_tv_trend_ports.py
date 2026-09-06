"""Source-backed trend port checks, not exported TradingView numerical fixtures.

Known constant/step identities pin warmup and state order independently of
random-walk seam tests. Cross-platform fixture validation is still pending.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from signals import tv_trend_signals as signals
from v3 import tv_trend_indicators as ta
from v3._tv_trend_support import cross_over, cross_under


def _bars(close, half_range=1.0):
    close = np.asarray(close, dtype=float)
    return pd.DataFrame({"Open": close, "High": close + half_range,
                         "Low": close - half_range, "Close": close,
                         "Volume": np.full(len(close), 1000.0)},
                        index=pd.date_range("2025-01-02 15:00", periods=len(close), freq="15min", tz="UTC"))


@pytest.fixture
def varied():
    rng = np.random.default_rng(854)
    return _bars(100 + np.cumsum(rng.normal(0, 1.5, 420)))


def test_exact_source_bytes_versions_and_explicit_pending_parity():
    folder = Path(__file__).parents[1] / "indicators" / "tradingview_sources"
    manifest = json.loads((folder / "trend_manifest.json").read_text())
    expected = {"AqRNdhlR": "CC-BY-NC-SA-4.0", "U7CZ8jtj": "MPL-2.0", "f4N0F439": "CC-BY-SA-4.0"}
    assert len(manifest["scripts"]) == 3
    for source in manifest["scripts"]:
        raw = (folder / source["source_file"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == source["sha256"]
        assert source["returned_version"] == "1.0"
        assert source["script_access"] == "open_no_auth"
        assert source["license"] == expected[source["public_id"]]
        assert "pending" in manifest["parity_status"].lower()


def test_pine_comparison_precision_does_not_create_roundoff_crossings():
    values = pd.Series([10.0, 10.0 + 1e-10, 10.0 + 2e-9, 10.0 - 1e-10, 10.0 - 2e-9])
    level = pd.Series(10.0, index=values.index)
    assert cross_over(values, level).tolist() == [False, False, True, False, False]
    assert cross_under(values, level).tolist() == [False, False, False, False, True]


def test_gaussian_hand_computed_one_pole_step_and_direction_memory():
    # Literal alpha = .828500414250207 at length2/poles1. Gap true ranges
    # are2,2,11,2,11; a .1×ATR1 deadband gives the following hand recurrence.
    result = ta.gaussian_filter_trend(_bars([100, 100, 110, 110, 100]), length=2,
                                    poles=1, atr_length=1, fixed_multiplier=0.1,
                                    adaptive_width=False)
    np.testing.assert_allclose(result.filtered_price,
                               [100, 100, 108.28500414250207, 109.7058789208765, 101.66455421426797])
    np.testing.assert_allclose(result.trend_line,
                               [100, 100, 107.18500414250208, 109.5058789208765, 102.76455421426796])
    assert result.direction.tolist() == [0, 0, 1, 1, -1]
    assert result.bull_signal.tolist() == [False, False, True, False, False]
    assert result.bear_signal.tolist() == [False, False, False, False, True]


def test_gaussian_adaptive_warmup_and_preset_overrides(varied):
    flat = ta.gaussian_filter_trend(_bars(np.full(30, 100)))
    assert flat.direction.eq(0).all()
    assert flat.trend_width.iloc[:13].isna().all()
    assert flat.trend_width.iloc[13:].eq(5.0).all()  # ATR2 × chop2.5
    explicit = ta.gaussian_filter_trend(varied, length=8, poles=2, atr_length=10,
                                      fixed_multiplier=1.2, efficiency_length=7,
                                      trend_multiplier=0.6, chop_multiplier=1.8,
                                      efficiency_smooth=3)
    preset = ta.gaussian_filter_trend(varied, preset="Fast Response", length=99, poles=4)
    pd.testing.assert_frame_equal(explicit, preset)


def test_fibonacci_exact_fixed_sma_warmup_and_initialization():
    result = ta.fibonacci_trend_continuation(_bars(np.full(210, 100), half_range=2))
    # RMA7's first value is index6; SMA200 first exists at6+199=205.
    assert result.volatility.iloc[:205].isna().all()
    assert result.volatility.iloc[205:].eq(4).all()
    assert result.direction.iloc[:205].eq(0).all()
    assert result.direction.iloc[205:].eq(1).all()
    assert not result.trend_flip.any()
    assert result.lower_band.iloc[-1] == pytest.approx(88)
    assert result.upper_band.iloc[-1] == pytest.approx(112)
    assert result["bull_0.786"].iloc[-1] == pytest.approx(97.432)
    assert result["bear_0.236"].iloc[-1] == pytest.approx(109.168)
    assert not result.bull_signal.any() and not result.bear_signal.any()


def test_fibonacci_continuation_level_selection_and_true_reversal():
    bars = _bars([100] * 210 + [94, 100, 50], half_range=2)
    result = ta.fibonacci_trend_continuation(bars)
    assert result.direction.iloc[210] == 1  # retracement inside the outer band
    assert result.bull_signal.iloc[211]     # enabled levels crossed on recovery
    assert not result.bull_flip.iloc[211]
    assert result.bear_flip.iloc[212] and result.direction.iloc[212] == -1
    disabled = ta.fibonacci_trend_continuation(bars, enabled_levels=())
    assert not disabled.bull_signal.any() and not disabled.bear_signal.any()
    pd.testing.assert_series_equal(result.direction, disabled.direction)


def test_uptrick_neutral_then_bull_bear_and_counter_reset():
    flat = ta.uptrick_adaptive_trend(_bars(np.full(60, 100)))
    assert flat.direction.eq(0).all()
    assert not flat.bull_signal.any() and not flat.bear_signal.any()
    close = np.r_[np.full(35, 100), np.linspace(100, 150, 60), np.linspace(150, 70, 85)]
    result = ta.uptrick_adaptive_trend(_bars(close))
    assert result.bull_signal.any() and result.bear_signal.any()
    assert result.direction.iloc[-1] == -1
    flips = result.bull_signal | result.bear_signal
    assert result.loc[flips, ["bull_st_bars", "bear_st_bars", "bull_confirm", "bear_confirm"]].eq(0).all().all()
    assert result.loc[result.bull_signal, "bull_votes"].ge(2).all()
    assert result.loc[result.bear_signal, "bear_votes"].ge(2).all()
    assert (result.bull_votes + result.bear_votes).eq(3).all()


def test_uptrick_cooldown_bypass_requires_source_fast_pass(varied):
    result = ta.uptrick_adaptive_trend(varied)
    previous = None
    for i in np.flatnonzero(result.bull_signal | result.bear_signal):
        if previous is not None:
            cooldown = 6 + int(np.floor(result.chop.iloc[i] * 4 + 0.5))
            if i - previous < cooldown:
                fast_pass = result.strong_bull.iloc[i] if result.bull_signal.iloc[i] else result.strong_bear.iloc[i]
                assert fast_pass
        previous = i


@pytest.mark.parametrize("calculator", [ta.gaussian_filter_trend, ta.fibonacci_trend_continuation,
                                       ta.uptrick_adaptive_trend])
def test_no_future_bars_change_available_values(calculator, varied):
    full = calculator(varied)
    for stop in (1, 14, 205, 260, 419):
        pd.testing.assert_frame_equal(calculator(varied.iloc[:stop]), full.iloc[:stop])
    changed = varied.copy()
    changed.iloc[260:, changed.columns.get_indexer(["Open", "High", "Low", "Close"])] *= 1.7
    pd.testing.assert_frame_equal(calculator(changed).iloc[:260], full.iloc[:260])


@pytest.mark.parametrize("name", ["gaussian_filter_trend", "fibonacci_trend_continuation", "uptrick_adaptive_trend"])
def test_chunk_replay_restart_and_rejected_backdated_update(name, varied):
    replay = ta.TrendReplay(name)
    first = replay.append(varied.iloc[:210])
    checkpoint = replay.snapshot()
    resumed = ta.TrendReplay(**checkpoint)
    second = resumed.append(varied.iloc[210:320])
    with pytest.raises(ValueError, match="strictly newer"):
        resumed.append(varied.iloc[319:321])
    final = resumed.append(varied.iloc[320:])
    pd.testing.assert_frame_equal(pd.concat([first, second, final]), getattr(ta, name)(varied))
    # A snapshot remains caller-owned; mutating it must not alter active state.
    checkpoint["history"].iloc[0, checkpoint["history"].columns.get_loc("Close")] = -999
    assert replay.snapshot()["history"].Close.iloc[0] > 0


@pytest.mark.parametrize("generator,grids", [
    (signals.generate_gaussian_filter_signals, ([8, 14], [2, 4])),
    (signals.generate_fibonacci_trend_signals, ([50, 200], [3, 7], [1.5, 3.0])),
    (signals.generate_uptrick_trend_signals, ([21, 34], [0.25, 0.35])),
])
def test_every_sweep_column_equals_all_four_frozen_signal_frames(generator, grids, varied):
    sweep = generator(varied, *grids, enable_shorting=True)
    assert all(frame.dtypes.eq(bool).all() for frame in sweep)
    for column in sweep[0].columns:
        frozen = generator(varied, *([value] for value in column), enable_shorting=True)
        for expected, actual in zip(sweep, frozen):
            pd.testing.assert_series_equal(expected[column], actual[column])
    long_only = generator(varied, *grids, enable_shorting=False)
    pd.testing.assert_frame_equal(long_only[0], sweep[0])
    pd.testing.assert_frame_equal(long_only[1], sweep[1])
    assert long_only[2:] == (None, None)


@pytest.mark.parametrize("calculator", [ta.gaussian_filter_trend, ta.fibonacci_trend_continuation,
                                       ta.uptrick_adaptive_trend])
def test_missing_or_unordered_observations_are_explicit(calculator, varied):
    invalid = varied.copy()
    invalid.iloc[20, invalid.columns.get_loc("Close")] = np.nan
    with pytest.raises(ValueError, match="finite OHLC"):
        calculator(invalid)
    with pytest.raises(ValueError, match="unique and increasing"):
        calculator(varied.iloc[::-1])
    with pytest.raises(ValueError, match="numeric dtypes"):
        calculator(varied.astype({"Close": str}))
    assert calculator(varied.iloc[:0]).empty
