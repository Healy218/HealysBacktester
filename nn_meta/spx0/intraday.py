"""Intraday-native signal generators for the spx0 pool (SPX0_SPEC item 3).

The v31 daily-swing params on 5m bars were a placeholder; these strategies
are built FOR the session clock. Each function returns the builder's 4-tuple
``(entries, exits, short_entries, short_exits)`` of boolean Series on the 5m
bar index, and every value at bar ``t`` uses only bars up to and including
``t`` (the right-labelled 5m bar stamped ``t`` closes at ``t``).

Param sweeps happen IN-FOLD by seating each setting as its own strategy name
(``sc.INTRADAY_STRATEGIES``) — the fold's model and policy selection pick
among seats, exactly how the v31 strategies already compete.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

_FOUR = tuple[pd.Series, pd.Series, pd.Series, pd.Series]


def _sessions(bars: pd.DataFrame):
    return bars.groupby(bars.index.normalize(), group_keys=False)


def _blank(bars: pd.DataFrame) -> pd.Series:
    return pd.Series(False, index=bars.index)


def vwap_reversion(bars: pd.DataFrame, k: float) -> _FOUR:
    """Fade a ``k``-sigma stretch from the session VWAP; exit on the cross
    back through VWAP. VWAP and the dispersion both accumulate within the
    session only (no overnight state)."""
    tp = (bars["High"] + bars["Low"] + bars["Close"]) / 3.0
    pv = (tp * bars["Volume"]).groupby(bars.index.normalize()).cumsum()
    vv = bars["Volume"].groupby(bars.index.normalize()).cumsum()
    vwap = pv / vv.replace(0, np.nan)
    dev = bars["Close"] - vwap
    # Expanding intra-session sigma of the deviation, shifted one bar so the
    # band at t is set before t's close prints against it.
    sig = _sessions(pd.DataFrame({"dev": dev}))["dev"] \
        .apply(lambda s: s.expanding(5).std().shift(1))
    stretched_dn = dev < -k * sig
    stretched_up = dev > k * sig
    entries = stretched_dn.fillna(False)
    short_entries = stretched_up.fillna(False)
    crossed_up = (dev >= 0) & (dev.shift(1) < 0)
    crossed_dn = (dev <= 0) & (dev.shift(1) > 0)
    return (entries, crossed_up.fillna(False),
            short_entries, crossed_dn.fillna(False))


def opening_range_breakout(bars: pd.DataFrame, minutes: int) -> _FOUR:
    """Break of the first ``minutes``' high/low, long above / short below,
    evaluated only after the range is complete; exit on the opposite break."""
    n = max(minutes // 5, 1)

    def _one(day: pd.DataFrame) -> pd.DataFrame:
        hi = day["High"].iloc[:n].max()
        lo = day["Low"].iloc[:n].min()
        after = np.arange(len(day)) >= n
        up = (day["Close"] > hi) & after
        dn = (day["Close"] < lo) & after
        first_up = up & ~up.shift(1, fill_value=False)
        first_dn = dn & ~dn.shift(1, fill_value=False)
        return pd.DataFrame({"e": first_up, "x": first_dn,
                             "se": first_dn, "sx": first_up}, index=day.index)

    f = _sessions(bars).apply(_one)
    return f["e"], f["x"], f["se"], f["sx"]


def gap_fill(bars: pd.DataFrame, min_gap_bp: float) -> _FOUR:
    """Fade an opening gap of at least ``min_gap_bp`` basis points against the
    prior session close: gap up → short toward the fill, gap down → long.
    Entry on the first bar of the gapped session; exit when the close crosses
    the prior session's close (the fill)."""
    day = bars.index.normalize()
    last_close = bars["Close"].groupby(day).last()
    prev_close = last_close.shift(1).reindex(day).to_numpy()
    is_first = ~pd.Series(day, index=bars.index).duplicated()
    gap = bars["Open"] / prev_close - 1.0
    big_up = gap * 1e4 >= min_gap_bp
    big_dn = gap * 1e4 <= -min_gap_bp
    entries = (is_first & big_dn).fillna(False)          # fade down-gap: long
    short_entries = (is_first & big_up).fillna(False)    # fade up-gap: short
    filled_up = (bars["Close"] >= prev_close) & big_dn.groupby(day).transform("any")
    filled_dn = (bars["Close"] <= prev_close) & big_up.groupby(day).transform("any")
    return (entries, filled_up.fillna(False),
            short_entries, filled_dn.fillna(False))


def intraday_signals(strategy: str, bars_5m: pd.DataFrame) -> _FOUR:
    """Dispatch one ``sc.INTRADAY_STRATEGIES`` name to its generator."""
    if strategy.startswith("vwap_rev_"):
        return vwap_reversion(bars_5m, k=float(strategy.rsplit("_", 1)[1]) / 10.0)
    if strategy.startswith("orb_"):
        return opening_range_breakout(bars_5m, minutes=int(strategy.rsplit("_", 1)[1]))
    if strategy.startswith("gap_fill_"):
        return gap_fill(bars_5m, min_gap_bp=float(strategy.rsplit("_", 1)[1]))
    raise ValueError(f"unknown intraday strategy: {strategy}")
