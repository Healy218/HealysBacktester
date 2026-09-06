# signals/tv_signals.py
"""TradingView-derived proposal strategies (v3): SuperTrend regime flips,
Technical-Rating threshold crossings, Squeeze-Momentum releases.

Same contract as the other signals modules: each generator returns
(entries, exits, short_entries, short_exits) DataFrames whose MultiIndex
columns carry one level per parameter, so nn_meta.proposals can sweep them
and recover winning params from column levels. Indicator math lives in
v3/indicators.py; TV rating rules in v3/tv_rating.py.
"""
from __future__ import annotations

from itertools import product

import numpy as np
import pandas as pd

from v3 import indicators as ta
from v3 import tv_rating


def _assemble(per_combo: dict, names: list[str], enable_shorting: bool):
    cols = pd.MultiIndex.from_tuples(list(per_combo), names=names)
    frames = []
    for i in range(4):
        if i >= 2 and not enable_shorting:
            frames.append(None)
            continue
        df = pd.DataFrame({c: per_combo[c][i] for c in per_combo})
        df.columns = cols
        frames.append(df.fillna(False).astype(bool))
    return tuple(frames)


def _cross_over(s: pd.Series, level: float) -> pd.Series:
    return (s > level) & (s.shift(1) <= level)


def _cross_under(s: pd.Series, level: float) -> pd.Series:
    return (s < level) & (s.shift(1) >= level)


def generate_supertrend_signals(ohlcv: pd.DataFrame, window_range,
                                mult_range, enable_shorting: bool = False):
    """Long on flip to +1 regime, exit on flip to -1 (shorts mirrored)."""
    out = {}
    for n, m in product(window_range, mult_range):
        d = ta.supertrend(ohlcv, int(n), float(m))["direction"]
        flip_up = (d == 1) & (d.shift(1) == -1)
        flip_dn = (d == -1) & (d.shift(1) == 1)
        out[(int(n), float(m))] = (flip_up, flip_dn, flip_dn, flip_up)
    return _assemble(out, ["st_window", "st_mult"], enable_shorting)


def generate_tv_rating_signals(ohlcv: pd.DataFrame, entry_range, exit_range,
                               enable_shorting: bool = False):
    """Composite Technical Rating crossings. entry_rating > 0 arms longs on
    an upward cross; exit_rating < 0 disarms on a downward cross. Shorts
    mirror around zero. The rating is computed once per bars."""
    r = tv_rating.rating(ohlcv)["rating"]
    out = {}
    for eth, xth in product(entry_range, exit_range):
        eth, xth = float(eth), float(xth)
        out[(eth, xth)] = (_cross_over(r, eth), _cross_under(r, xth),
                           _cross_under(r, -eth), _cross_over(r, -xth))
    return _assemble(out, ["entry_rating", "exit_rating"], enable_shorting)


def generate_squeeze_signals(ohlcv: pd.DataFrame, bb_mult_range,
                             kc_mult_range, enable_shorting: bool = False):
    """LazyBear squeeze: enter on release in the momentum's direction, exit
    when momentum crosses back through zero."""
    out = {}
    for bm, km in product(bb_mult_range, kc_mult_range):
        sq = ta.squeeze_momentum(ohlcv, bb_mult=float(bm), kc_mult=float(km))
        released = sq["squeeze_on"].shift(1, fill_value=False) & ~sq["squeeze_on"]
        mom = sq["momentum"]
        out[(float(bm), float(km))] = (released & (mom > 0),
                                       _cross_under(mom, 0.0),
                                       released & (mom < 0),
                                       _cross_over(mom, 0.0))
    return _assemble(out, ["sq_bb_mult", "sq_kc_mult"], enable_shorting)


# ── v6 additions (user notes 2026-09-05) ─────────────────────────────────────

def generate_keltner_signals(ohlcv: pd.DataFrame, window_range, mult_range,
                             enable_shorting: bool = False):
    """Keltner channel breakout: EMA(close, n) ± mult × smoothed true range.
    Both EWM smoothers retain this family's first-observation seed. Long on
    a close crossing above the
    upper band, exit on a close crossing back under the mid line; shorts
    mirrored on the lower band. The Keltner half of the squeeze family, as an
    entry family of its own."""
    out = {}
    tr = ta.true_range(ohlcv)
    close = ohlcv["Close"]
    for n, m in product(window_range, mult_range):
        n, m = int(n), float(m)
        mid = close.ewm(span=n, adjust=False).mean()
        rng = m * ta.rma(tr, n)
        upper, lower = mid + rng, mid - rng
        long_in = (close > upper) & (close.shift(1) <= upper.shift(1))
        long_out = (close < mid) & (close.shift(1) >= mid.shift(1))
        short_in = (close < lower) & (close.shift(1) >= lower.shift(1))
        short_out = (close > mid) & (close.shift(1) <= mid.shift(1))
        out[(n, m)] = (long_in, long_out, short_in, short_out)
    return _assemble(out, ["kc_window", "kc_mult"], enable_shorting)


def generate_bbw_squeeze_signals(ohlcv: pd.DataFrame, window_range,
                                 lookback_range, enable_shorting: bool = False):
    """Bollinger Band Width squeeze: width =
    (upper − lower) / basis with a 2σ band; a squeeze is on while the width
    sits at its lowest over ``lookback`` fully populated widths, ties included.
    Entry = a close crossing outside the band while the squeeze was on the
    bar before; exit = a close crossing back through the basis.
    Distinct from the ``squeeze`` family, which is LazyBear's BB-inside-Keltner
    release with a momentum sign."""
    out = {}
    close = ohlcv["Close"]
    for n, lb in product(window_range, lookback_range):
        n, lb = int(n), int(lb)
        basis = ta.sma(close, n)
        dev = 2.0 * close.rolling(n).std(ddof=0)
        upper, lower = basis + dev, basis - dev
        width = (upper - lower) / basis.replace(0, np.nan)
        squeeze_on = width <= width.rolling(lb).min()
        armed = squeeze_on.shift(1, fill_value=False)
        long_in = armed & (close > upper) & (close.shift(1) <= upper.shift(1))
        long_out = (close < basis) & (close.shift(1) >= basis.shift(1))
        short_in = armed & (close < lower) & (close.shift(1) >= lower.shift(1))
        short_out = (close > basis) & (close.shift(1) <= basis.shift(1))
        out[(n, lb)] = (long_in, long_out, short_in, short_out)
    return _assemble(out, ["bbw_window", "bbw_lookback"], enable_shorting)
