"""Lock the existing v6 strategy choices and their four-frame freeze contract."""
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from nn_meta import config, proposals
from signals.tv_signals import (generate_bbw_squeeze_signals,
                                generate_keltner_signals)


STRATEGIES = ("keltner", "bbw_squeeze")


def _bars(values):
    close = pd.Series(values, dtype=float, index=pd.date_range(
        "2025-01-02 14:30", periods=len(values), freq="15min"))
    return pd.DataFrame({"Open": close, "High": close + 0.4,
                         "Low": close - 0.4, "Close": close, "Volume": 1000.0})


def _two_breakouts():
    # Every configured window/lookback warms up before each direction fires.
    return _bars([100.] * 240 + [130., 100.] + [100.] * 240
                 + [70., 100.] + [100.] * 240)


def _events(frames):
    return [np.flatnonzero(frame.iloc[:, 0]).tolist() for frame in frames]


@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize("shorting", [False, True])
def test_every_grid_column_freezes_all_four_outputs(strategy, shorting, monkeypatch):
    monkeypatch.setattr(config, "ENABLE_SHORTING", shorting)
    bars = _two_breakouts()
    sweep = proposals.sweep_signals(strategy, bars)
    columns = sweep[0].columns
    assert isinstance(columns, pd.MultiIndex)
    assert columns.is_unique and all(columns.names)
    assert len(columns) == (25 if strategy == "keltner" else 9)
    portfolio = SimpleNamespace(wrapper=SimpleNamespace(columns=columns))

    for position, column in enumerate(columns):
        params = proposals.params_from_portfolio(portfolio, position)
        frozen = proposals.single_signals(strategy, bars, params)
        assert len(frozen) == len(sweep) == 4
        for output, (whole, single) in enumerate(zip(sweep, frozen)):
            if output >= 2 and not shorting:
                assert whole is None and single is None
                continue
            assert whole.dtypes.eq(bool).all()
            assert not whole.isna().any().any()
            assert whole[column].any(), "parity must exercise actual events"
            pd.testing.assert_frame_equal(single, whole[[column]])


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_sweep_and_frozen_are_prefix_invariant(strategy, monkeypatch):
    monkeypatch.setattr(config, "ENABLE_SHORTING", True)
    bars = _two_breakouts()
    whole = proposals.sweep_signals(strategy, bars)
    portfolio = SimpleNamespace(wrapper=SimpleNamespace(columns=whole[0].columns))
    params = proposals.params_from_portfolio(portfolio, len(whole[0].columns) - 1)
    frozen = proposals.single_signals(strategy, bars, params)
    # Before full rolling warmup, at a breakout, after its exit, and at reversal.
    for end in (5, 210, 240, 241, 242, 483, 484):
        prefix_sweep = proposals.sweep_signals(strategy, bars.iloc[:end])
        prefix_frozen = proposals.single_signals(strategy, bars.iloc[:end], params)
        for full, partial in zip(whole, prefix_sweep):
            pd.testing.assert_frame_equal(full.iloc[:end], partial)
        for full, partial in zip(frozen, prefix_frozen):
            pd.testing.assert_frame_equal(full.iloc[:end], partial)


def test_keltner_enters_breakouts_and_exits_basis_crosses():
    bars = _bars([100, 100, 110, 112, 90, 88, 105])
    bars["High"], bars["Low"] = bars.Close + 1, bars.Close - 1
    frames = generate_keltner_signals(bars, [3], [.5], enable_shorting=True)
    # At index 2: EMA=105, smoothed TR=5, upper=107.5, close=110.
    # Consecutive closes outside a band do not create repeated entries.
    assert _events(frames) == [[2, 6], [4], [4], [2, 6]]


def test_keltner_basis_touch_waits_for_strict_cross():
    bars = _bars([100, 100, 110, 105, 104])
    frames = generate_keltner_signals(bars, [3], [.5], enable_shorting=True)
    # EMA and close are both 105 at index 3; the long exit occurs at index 4.
    assert _events(frames)[1] == [4]


def test_bbw_flat_tied_minimum_arms_breakout_in_each_direction():
    bars = _bars([100] * 8 + [110, 100] + [100] * 8 + [90, 100])
    frames = generate_bbw_squeeze_signals(bars, [6], [3], enable_shorting=True)
    # The preceding width is zero and tied with earlier minima. Current width
    # expands; prior-bar arming still permits the upward/downward band cross.
    assert _events(frames) == [[8], [9, 18], [18], [8, 19]]


@pytest.mark.parametrize("breakout", [90., 110.])
def test_bbw_requires_complete_width_lookback_before_entry(breakout):
    early = generate_bbw_squeeze_signals(
        _bars([100] * 7 + [breakout]), [6], [3], enable_shorting=True)
    ready = generate_bbw_squeeze_signals(
        _bars([100] * 8 + [breakout]), [6], [3], enable_shorting=True)
    output = 0 if breakout > 100 else 2
    assert not early[output].any().any()
    assert _events(ready)[output] == [8]


def test_bbw_nonminimum_previous_width_does_not_arm_new_band_cross():
    bars = _bars([100] * 8 + [100.1, 100, 110])
    frames = generate_bbw_squeeze_signals(bars, [6], [3], enable_shorting=True)
    # Index 8 is the first small breakout. Index 9 returns inside the bands;
    # its width is positive, above the zero minimum still in the lookback.
    # Index 10 crosses the upper band again but is not armed by index 9.
    assert _events(frames)[0] == [8]
    assert not frames[0].iloc[10, 0]


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_flat_prices_produce_no_entries_or_exits(strategy, monkeypatch):
    monkeypatch.setattr(config, "ENABLE_SHORTING", True)
    assert all(not frame.any().any() for frame in
               proposals.sweep_signals(strategy, _bars([100.] * 400)))
