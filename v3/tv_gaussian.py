# SPDX-License-Identifier: CC-BY-NC-SA-4.0
# Adapted from Gaussian Filter Trend [QuantAlgo], © QuantAlgo.
# https://www.tradingview.com/script/AqRNdhlR-Gaussian-Filter-Trend-QuantAlgo/
# https://creativecommons.org/licenses/by-nc-sa/4.0/
# Changes: Python closed-bar numerical/state port; decorative graphics omitted.
"""Adaptation of the pinned AqRNdhlR publication v1; TV fixtures pending."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from v3 import pine_compat as pine
from v3._tv_trend_support import comparison_value as cmp
from v3._tv_trend_support import integer, pine_ohlc, positive, validate_bars


def gaussian_filter_trend(
    bars: pd.DataFrame, length: int = 14, poles: int = 4,
    atr_length: int = 14, fixed_multiplier: float = 1.5,
    adaptive_width: bool = True, efficiency_length: int = 10,
    trend_multiplier: float = 0.8, chop_multiplier: float = 2.5,
    efficiency_smooth: int = 5, source: str = "Close", preset: str = "Default",
) -> pd.DataFrame:
    """Calculate the author's filter, deadband, persistent state and alerts.

    ``Fast Response``/``Smooth Trend`` override numerical inputs exactly as
    upstream; adaptive_width and source remain user inputs. Flat trend-line
    bars retain the last direction. Neutral→direction is an upstream alert.
    """
    validate_bars(bars)
    if preset == "Fast Response":
        length, poles, atr_length, fixed_multiplier = 8, 2, 10, 1.2
        efficiency_length, trend_multiplier, chop_multiplier, efficiency_smooth = 7, 0.6, 1.8, 3
    elif preset == "Smooth Trend":
        length, poles, atr_length, fixed_multiplier = 21, 4, 21, 2.0
        efficiency_length, trend_multiplier, chop_multiplier, efficiency_smooth = 18, 1.0, 3.2, 8
    elif preset != "Default":
        raise ValueError(f"unknown Gaussian preset: {preset}")
    length = integer("length", length, 2)
    poles = integer("poles", poles, 1, 4)
    atr_length = integer("atr_length", atr_length)
    efficiency_length = integer("efficiency_length", efficiency_length, 2)
    efficiency_smooth = integer("efficiency_smooth", efficiency_smooth)
    fixed_multiplier = positive("fixed_multiplier", fixed_multiplier, 0.1)
    trend_multiplier = positive("trend_multiplier", trend_multiplier, 0.1)
    chop_multiplier = positive("chop_multiplier", chop_multiplier, 0.1)
    if source in ("Open", "High", "Low", "Close"):
        src = bars[source].astype(float)
    elif source == "HL2":
        src = (bars.High + bars.Low) / 2
    elif source == "HLC3":
        src = (bars.High + bars.Low + bars.Close) / 3
    elif source == "OHLC4":
        src = bars[["Open", "High", "Low", "Close"]].mean(axis=1)
    else:
        raise ValueError(f"unsupported Pine price source: {source}")
    # 1.414 is deliberately the literal used by the author, not sqrt(2).
    beta = (1 - math.cos(2 * math.pi / length)) / (1.414 ** (2 / poles) - 1)
    alpha = -beta + math.sqrt(beta * beta + 2 * beta)
    filtered = np.empty(len(src))
    stages = np.full(4, np.nan)
    for i, price in enumerate(src):
        current = price
        for stage in range(4):
            previous = price if np.isnan(stages[stage]) else stages[stage]
            stages[stage] = alpha * current + (1 - alpha) * previous
            current = stages[stage]
        filtered[i] = stages[poles - 1]
    filtered = pd.Series(filtered, index=bars.index)
    travel = src.diff().abs().rolling(efficiency_length).sum()
    efficiency = (src - src.shift(efficiency_length)).abs() / travel
    efficiency = efficiency.mask(cmp(travel) == 0, 0.0)
    smoothed_efficiency = pine.ema(efficiency, efficiency_smooth)
    width_multiplier = (chop_multiplier + (trend_multiplier - chop_multiplier)
                        * smoothed_efficiency if adaptive_width else fixed_multiplier)
    width = pine.atr(pine_ohlc(bars), atr_length) * width_multiplier
    upper, lower = filtered + width, filtered - width
    lines, directions = np.empty(len(src)), np.zeros(len(src), dtype=int)
    previous_line, direction = np.nan, 0
    for i in range(len(src)):
        line = filtered.iloc[i] if np.isnan(previous_line) else previous_line
        if cmp(upper.iloc[i]) < cmp(line):
            line = upper.iloc[i]
        if cmp(lower.iloc[i]) > cmp(line):
            line = lower.iloc[i]
        if cmp(line) > cmp(previous_line):
            direction = 1
        elif cmp(line) < cmp(previous_line):
            direction = -1
        lines[i], directions[i], previous_line = line, direction, line
    state = pd.Series(directions, index=bars.index)
    return pd.DataFrame({
        "filtered_price": filtered, "efficiency": efficiency,
        "smoothed_efficiency": smoothed_efficiency, "trend_width": width,
        "upper_band": upper, "lower_band": lower, "trend_line": lines,
        "direction": state, "bull_signal": (state == 1) & (state.shift() != 1),
        "bear_signal": (state == -1) & (state.shift() != -1),
    }, index=bars.index)
