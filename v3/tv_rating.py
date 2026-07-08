# v3/tv_rating.py — TradingView "Technical Ratings" scoring rules.
"""26 components → -1 (sell) / 0 (neutral) / +1 (buy) each, per TV's
documented criteria (support article 43000614331, fetched 2026-07-08):

- 15 "moving averages": SMA & EMA (10/20/30/50/100/200), HMA(9), VWMA(20),
  Ichimoku (bullish/bearish stack).
- 11 oscillators: RSI, Stoch, CCI, ADX, AO, Momentum, MACD, StochRSI, W%R,
  Bull/Bear Power, Ultimate Oscillator.

rating(df) returns per-bar columns: ma_rating, osc_rating, rating (means, in
[-1, 1]) — Strong Sell < -0.5 < Sell < -0.1 < Neutral < 0.1 < Buy < 0.5 <
Strong Buy.

One documented deviation: TV conditions StochRSI and Bull/Bear Power on "the
trend" without publishing its definition; we define trend as Close vs
SMA(50), which matches common practice.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from v3 import indicators as ta

MA_LENGTHS = (10, 20, 30, 50, 100, 200)


def _rising(s: pd.Series) -> pd.Series:
    return s > s.shift(1)


def _score(buy: pd.Series, sell: pd.Series) -> pd.Series:
    return pd.Series(np.where(buy, 1.0, np.where(sell, -1.0, 0.0)),
                     index=buy.index)


def ma_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Price above MA = buy, below = sell (TV's MA criterion)."""
    c = df["Close"]
    out = {}
    for n in MA_LENGTHS:
        out[f"sma{n}"] = _score(c > ta.sma(c, n), c < ta.sma(c, n))
        out[f"ema{n}"] = _score(c > ta.ema(c, n), c < ta.ema(c, n))
    out["hma9"] = _score(c > ta.hma(c, 9), c < ta.hma(c, 9))
    out["vwma20"] = _score(c > ta.vwma(c, df["Volume"], 20),
                           c < ta.vwma(c, df["Volume"], 20))
    ich = ta.ichimoku(df)
    bull = ((ich["span_a"] > ich["span_b"]) & (ich["base"] > ich["span_a"]) &
            (ich["conversion"] > ich["base"]) & (c > ich["conversion"]))
    bear = ((ich["span_a"] < ich["span_b"]) & (ich["base"] < ich["span_a"]) &
            (ich["conversion"] < ich["base"]) & (c < ich["conversion"]))
    out["ichimoku"] = _score(bull, bear)
    return pd.DataFrame(out)


def osc_scores(df: pd.DataFrame) -> pd.DataFrame:
    c = df["Close"]
    trend_up = c > ta.sma(c, 50)          # our documented trend definition
    out = {}

    r = ta.rsi(c, 14)
    out["rsi"] = _score((r < 30) & _rising(r), (r > 70) & ~_rising(r))

    st = ta.stochastic(df)
    out["stoch"] = _score((st["k"] < 20) & (st["d"] < 20) & (st["k"] > st["d"]),
                          (st["k"] > 80) & (st["d"] > 80) & (st["k"] < st["d"]))

    cc = ta.cci(df, 20)
    out["cci"] = _score((cc < -100) & _rising(cc), (cc > 100) & ~_rising(cc))

    ax = ta.adx(df, 14)
    strong = (ax["adx"] > 20) & _rising(ax["adx"])
    out["adx"] = _score(strong & (ax["plus_di"] > ax["minus_di"]),
                        strong & (ax["plus_di"] < ax["minus_di"]))

    ao = ta.awesome_oscillator(df)
    cross_up = (ao > 0) & (ao.shift(1) <= 0)
    saucer_up = (ao > 0) & _rising(ao) & ~_rising(ao).shift(1, fill_value=True)
    cross_dn = (ao < 0) & (ao.shift(1) >= 0)
    saucer_dn = (ao < 0) & ~_rising(ao) & _rising(ao).shift(1, fill_value=False)
    out["ao"] = _score(cross_up | saucer_up, cross_dn | saucer_dn)

    mom = ta.momentum(c, 10)
    out["momentum"] = _score(_rising(mom), ~_rising(mom) & mom.notna())

    mc = ta.macd(c)
    out["macd"] = _score(mc["macd"] > mc["signal"], mc["macd"] < mc["signal"])

    sr = ta.stoch_rsi(c)
    out["stoch_rsi"] = _score(~trend_up & (sr["k"] < 20) & (sr["d"] < 20)
                              & (sr["k"] > sr["d"]),
                              trend_up & (sr["k"] > 80) & (sr["d"] > 80)
                              & (sr["k"] < sr["d"]))

    wr = ta.williams_r(df, 14)
    out["williams_r"] = _score((wr < -80) & _rising(wr),
                               (wr > -20) & ~_rising(wr))

    bb = ta.bull_bear_power(df, 13)
    out["bull_bear"] = _score(trend_up & (bb["bear"] < 0) & _rising(bb["bear"]),
                              ~trend_up & (bb["bull"] > 0) & ~_rising(bb["bull"]))

    uo = ta.ultimate_oscillator(df)
    out["uo"] = _score(uo > 70, uo < 30)
    return pd.DataFrame(out)


def rating(df: pd.DataFrame) -> pd.DataFrame:
    """ma_rating / osc_rating / rating per bar, each in [-1, 1]."""
    ma = ma_scores(df).mean(axis=1)
    osc = osc_scores(df).mean(axis=1)
    return pd.DataFrame({"ma_rating": ma, "osc_rating": osc,
                         "rating": (ma + osc) / 2})


def category(r: float) -> str:
    if r < -0.5:
        return "strong_sell"
    if r < -0.1:
        return "sell"
    if r <= 0.1:
        return "neutral"
    if r <= 0.5:
        return "buy"
    return "strong_buy"
