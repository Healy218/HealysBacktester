# SPDX-License-Identifier: MPL-2.0
# Adapted from Fibonacci Trend Continuation Signals [AlgoAlpha], © AlgoAlpha.
# https://www.tradingview.com/script/U7CZ8jtj-Fibonacci-Trend-Continuation-Signals-AlgoAlpha/
# https://mozilla.org/MPL/2.0/
# Changes: Python closed-bar numerical/state port; rendering omitted.
"""Adaptation of the pinned U7CZ8jtj publication v1; TV fixtures pending."""
from __future__ import annotations

import numpy as np
import pandas as pd

from v3 import pine_compat as pine
from v3._tv_trend_support import comparison_value as cmp
from v3._tv_trend_support import cross_over, cross_under, integer, positive, validate_bars

FIB_LEVELS = (0.236, 0.382, 0.500, 0.618, 0.786)


from v3._source_memo import memoized_source


@memoized_source
def fibonacci_trend_continuation(
    bars: pd.DataFrame, midline_length: int = 200, pivot_length: int = 7,
    band_width: float = 3.0, enabled_levels: tuple[float, ...] = FIB_LEVELS,
) -> pd.DataFrame:
    """Return bands, all ten levels, continuation alerts and reversal events.

    ``pivot_length`` names the upstream RMA input; it is not a swing-pivot
    confirmation window. The fixed SMA200 of that RMA is part of the source.
    Initial direction is chosen once bands exist and does not emit a flip.
    """
    validate_bars(bars)
    midline_length = integer("midline_length", midline_length)
    pivot_length = integer("pivot_length", pivot_length)
    band_width = positive("band_width", band_width, 0.1)
    if any(level not in FIB_LEVELS for level in enabled_levels):
        raise ValueError("enabled_levels must select from the five upstream Fibonacci ratios")
    volatility = pine.sma(pine.rma(bars.High - bars.Low, pivot_length), 200)
    midline = pine.ema(bars.Close, midline_length)
    upper, lower = midline + volatility * band_width, midline - volatility * band_width
    directions = np.zeros(len(bars), dtype=int)
    flips = np.zeros(len(bars), dtype=bool)
    direction = 0
    for i, close in enumerate(bars.Close):
        if direction == 0 and not np.isnan(upper.iloc[i]):
            direction = 1 if cmp(close) >= cmp(midline.iloc[i]) else -1
        previous = direction
        if cmp(close) > cmp(upper.iloc[i]):
            direction = 1
        elif cmp(close) < cmp(lower.iloc[i]):
            direction = -1
        directions[i] = direction
        flips[i] = direction != previous and previous != 0
    bullish, bearish = directions == 1, directions == -1
    long_cross = pd.Series(False, index=bars.index)
    short_cross = pd.Series(False, index=bars.index)
    output = {"midline": midline, "volatility": volatility, "upper_band": upper,
              "lower_band": lower, "direction": directions, "trend_flip": flips}
    for level in FIB_LEVELS:
        bull = lower + (midline - lower) * level
        bear = upper + (midline - upper) * level
        output[f"bull_{level:.3f}"] = bull
        output[f"bear_{level:.3f}"] = bear
        if level in enabled_levels:
            long_cross |= cross_over(bars.Close, bull)
            short_cross |= cross_under(bars.Close, bear)
    output.update(bull_signal=bullish & long_cross, bear_signal=bearish & short_cross,
                  bull_flip=flips & bullish, bear_flip=flips & bearish)
    return pd.DataFrame(output, index=bars.index)
