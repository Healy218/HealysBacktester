# SPDX-License-Identifier: CC-BY-SA-4.0
# Adapted from Uptrick: Adaptive Trend Trail, © Uptrick.
# https://www.tradingview.com/script/f4N0F439-Uptrick-Adaptive-Trend-Trail/
# https://creativecommons.org/licenses/by-sa/4.0/
# Changes: Python closed-bar trend/state port, without the internal trade
# simulation, valuation-table rendering, or chart-object construction.
"""Adaptation of pinned f4N0F439 publication v1; TV fixtures pending."""
from __future__ import annotations

import numpy as np
import pandas as pd
import os

from v3 import pine_compat as pine
from v3._tv_trend_support import comparison_value as cmp
from v3._tv_trend_support import integer, pine_ohlc, positive, validate_bars


def uptrick_adaptive_trend(
    bars: pd.DataFrame, trend_length: int = 34, momentum_length: int = 12,
    sensitivity: float = 0.35, fast_length: int = 9, fast_factor: float = 1.45,
    mid_length: int = 14, mid_factor: float = 1.95,
    slow_length: int = 21, slow_factor: float = 2.55,
    minimum_tick: float = 0.01, trail_size: float = 1.0, smoothness: int = 5,
) -> pd.DataFrame:
    """Compute the nine-field regime, three ST votes, gate and persistent trend.

    ``minimum_tick`` represents Pine's syminfo.mintick and must match the
    instrument for parity. Default 0.01 is an explicit equity configuration.
    Every supplied bar is treated as confirmed. Modelled trading statistics
    are intentionally outside these numerical features and proposal signals.
    """
    validate_bars(bars)
    trend_length = integer("trend_length", trend_length, 10, 200)
    momentum_length = integer("momentum_length", momentum_length, 3, 100)
    sensitivity = positive("sensitivity", sensitivity, 0.10, 1.25)
    fast_length = integer("fast_length", fast_length, 2, 100)
    mid_length = integer("mid_length", mid_length, 2, 150)
    slow_length = integer("slow_length", slow_length, 2, 200)
    fast_factor = positive("fast_factor", fast_factor, 0.25, 10)
    mid_factor = positive("mid_factor", mid_factor, 0.25, 10)
    slow_factor = positive("slow_factor", slow_factor, 0.25, 10)
    minimum_tick = positive("minimum_tick", minimum_tick)
    trail_size = positive("trail_size", trail_size, 0.40, 2.50)
    smoothness = integer("smoothness", smoothness, 1, 20)
    close = bars.Close.astype(float)
    pine_bars = pine_ohlc(bars)
    basis = pine.ema(close, trend_length)
    safe_atr = pine.atr(pine_bars, 14).clip(lower=minimum_tick)
    momentum = pine.ema(close - close.shift(momentum_length), 5) / safe_atr
    distance = (close - basis) / safe_atr
    travel = close.diff().abs().rolling(10).sum()
    efficiency = ((close - close.shift(10)).abs() / travel).clip(0, 1)
    # Pine v6 ternary evaluates its false arm when the comparison contains na.
    efficiency = efficiency.where(cmp(travel) > 0, 0.0)
    chop = 1 - efficiency
    efficiency_direction = np.where(cmp(close) > cmp(close.shift(10)), 1.0,
                                    np.where(cmp(close) < cmp(close.shift(10)), -1.0, 0.0))
    efficiency_field = efficiency * efficiency_direction
    normal_atr = pine.ema(safe_atr, 50)
    vol_ratio = (safe_atr / normal_atr).where(cmp(normal_atr) > 0, 1.0)
    vol_expansion = (vol_ratio - 1).clip(0, 1.25)
    vol_deviation = (vol_ratio - 1).abs().clip(0, 1.5)

    fast_adaptive = fast_factor + chop * 0.25 + vol_expansion * 0.10
    mid_adaptive = mid_factor + chop * 0.35 + vol_expansion * 0.15
    slow_adaptive = slow_factor + chop * 0.45 + vol_expansion * 0.20
    fast = pine.supertrend(pine_bars, fast_adaptive, fast_length)
    medium = pine.supertrend(pine_bars, mid_adaptive, mid_length)
    slow = pine.supertrend(pine_bars, slow_adaptive, slow_length)
    st_directions = pd.concat([fast["direction"], medium["direction"], slow["direction"]], axis=1)
    bull_votes = (st_directions < 0).sum(axis=1)
    bear_votes = (st_directions > 0).sum(axis=1)

    distance_field = (distance / 1.20).clip(-1, 1)
    momentum_field = (momentum / 0.35).clip(-1, 1)
    slope_field = ((basis - basis.shift(3)) / safe_atr / 0.25).clip(-1, 1)
    rsi = pine.rsi(close, 14)
    rsi_field = ((rsi - 50) / 20).clip(-1, 1)
    st_field = (bull_votes - bear_votes) / 3
    slow_center = pine.ema((bars.High + bars.Low) / 2,
                           max(10, int(pine.round_half_up(trend_length * 0.70))))
    slow_slope_field = ((slow_center - slow_center.shift(3)) / safe_atr / 0.25).clip(-1, 1)
    structure_length = max(3, int(pine.round_half_up(trend_length * 0.12)))
    recent_high = bars.High.shift().rolling(structure_length, min_periods=1).max()
    recent_low = bars.Low.shift().rolling(structure_length, min_periods=1).min()
    structure_field = pd.Series(np.where(cmp(close) > cmp(recent_high), 1.0,
                                        np.where(cmp(close) < cmp(recent_low), -1.0, 0.0)), index=bars.index)
    bar_range = (bars.High - bars.Low).clip(lower=minimum_tick)
    body_pressure = (close - bars.Open) / bar_range
    close_location = ((close - bars.Low) / bar_range - 0.5) * 2
    pressure_field = (body_pressure * 0.60 + close_location * 0.40).clip(-1, 1)
    raw_regime = (distance_field * 0.22 + momentum_field * 0.19 + slope_field * 0.14
                  + slow_slope_field * 0.10 + rsi_field * 0.08 + efficiency_field * 0.09
                  + pressure_field * 0.05 + structure_field * 0.05 + st_field * 0.20)
    regime = pine.ema(raw_regime, 3)
    gate = 0.22 + sensitivity * 0.12 + chop * 0.085 + (vol_deviation * 0.04).clip(0, 0.06)
    bull_price_ok = cmp(close) > cmp(basis + safe_atr * sensitivity * 0.30)
    bear_price_ok = cmp(close) < cmp(basis - safe_atr * sensitivity * 0.30)
    # This order matters: update ST counters, update candidate counters, decide
    # the flip, then clear all four counters on that same confirmed bar.
    state = np.zeros(len(bars), dtype=int)
    counters = np.zeros((len(bars), 4), dtype=int)
    ready = np.zeros((len(bars), 2), dtype=bool)
    strong = np.zeros((len(bars), 2), dtype=bool)
    bull_st_bars = bear_st_bars = bull_confirm = bear_confirm = trend = 0
    last_flip = None
    fast_bull = (fast["direction"] < 0).to_numpy()
    fast_bear = (fast["direction"] > 0).to_numpy()
    medium_bull = (medium["direction"] < 0).to_numpy()
    medium_bear = (medium["direction"] > 0).to_numpy()
    slow_bull = (slow["direction"] < 0).to_numpy()
    slow_bear = (slow["direction"] > 0).to_numpy()
    if os.environ.get("NN_META_V6_ACCELERATE") == "1":
        from v3._uptrick_fast import states
        state, counters, ready, strong = states(
            *[v.to_numpy() for v in (chop, bull_votes, bear_votes, regime, gate,
                bull_price_ok, bear_price_ok, momentum, efficiency)],
            fast_bull, fast_bear, medium_bull, medium_bear, slow_bull, slow_bear)
    else:
        for i in range(len(bars)):
            ch, bv, sv = cmp(chop.iloc[i]), bull_votes.iloc[i], bear_votes.iloc[i]
            required_votes = 3 if ch > 0.70 else 2
            bull_st_bars = min(bull_st_bars + 1, 5) if bv >= required_votes else 0
            bear_st_bars = min(bear_st_bars + 1, 5) if sv >= required_votes else 0
            persistence = 2 if ch > 0.72 else 1
            bull_candidate = (cmp(regime.iloc[i]) > cmp(gate.iloc[i]) and bull_price_ok.iloc[i]
                              and cmp(momentum.iloc[i]) > 0.025 and bull_st_bars >= persistence)
            bear_candidate = (cmp(regime.iloc[i]) < cmp(-gate.iloc[i]) and bear_price_ok.iloc[i]
                              and cmp(momentum.iloc[i]) < -0.025 and bear_st_bars >= persistence)
            required_bars = 3 if ch > 0.72 else 2 if ch > 0.40 else 1
            bull_confirm = min(bull_confirm + 1, 4) if bull_candidate else 0
            bear_confirm = min(bear_confirm + 1, 4) if bear_candidate else 0
            strong_bull = (bull_candidate and bv == 3 and cmp(regime.iloc[i]) > cmp(gate.iloc[i] + 0.26)
                           and cmp(momentum.iloc[i]) > 0.16 and cmp(efficiency.iloc[i]) > 0.42)
            strong_bear = (bear_candidate and sv == 3 and cmp(regime.iloc[i]) < cmp(-(gate.iloc[i] + 0.26))
                           and cmp(momentum.iloc[i]) < -0.16 and cmp(efficiency.iloc[i]) > 0.42)
            bull_ready = ((bull_confirm >= required_bars or strong_bull)
                          and fast_bull[i] and (medium_bull[i] or slow_bull[i]))
            bear_ready = ((bear_confirm >= required_bars or strong_bear)
                          and fast_bear[i] and (medium_bear[i] or slow_bear[i]))
            cooldown = 6 + int(pine.round_half_up(chop.iloc[i] * 4.0))
            cooldown_done = (100000 if last_flip is None else i - last_flip) >= cooldown
            changed = False
            if trend != 1 and bull_ready and (cooldown_done or strong_bull):
                trend, changed = 1, True
            elif trend != -1 and bear_ready and (cooldown_done or strong_bear):
                trend, changed = -1, True
            if changed:
                last_flip = i
                bull_confirm = bear_confirm = bull_st_bars = bear_st_bars = 0
            state[i] = trend
            counters[i] = bull_st_bars, bear_st_bars, bull_confirm, bear_confirm
            ready[i], strong[i] = (bull_ready, bear_ready), (strong_bull, strong_bear)
    direction = pd.Series(state, index=bars.index)
    smooth_basis = pine.ema(basis, smoothness) if smoothness > 1 else basis
    smooth_atr = pine.ema(safe_atr, smoothness) if smoothness > 1 else safe_atr
    output = {"basis": basis, "safe_atr": safe_atr, "momentum": momentum,
              "efficiency": efficiency, "chop": chop, "vol_ratio": vol_ratio,
              "raw_regime": raw_regime, "regime": regime, "dynamic_gate": gate,
              "fast_supertrend": fast["supertrend"], "mid_supertrend": medium["supertrend"],
              "slow_supertrend": slow["supertrend"],
              "fast_st_direction": fast["direction"], "mid_st_direction": medium["direction"],
              "slow_st_direction": slow["direction"],
              "bull_votes": bull_votes, "bear_votes": bear_votes,
              "direction": direction, "bull_signal": (direction == 1) & (direction.shift() != 1),
              "bear_signal": (direction == -1) & (direction.shift() != -1),
              "bull_ready": ready[:, 0], "bear_ready": ready[:, 1],
              "strong_bull": strong[:, 0], "strong_bear": strong[:, 1],
              "bull_st_bars": counters[:, 0], "bear_st_bars": counters[:, 1],
              "bull_confirm": counters[:, 2], "bear_confirm": counters[:, 3],
              "valuation": pine.ema(rsi, 3).clip(0, 100)}
    for label, multiplier in (("inner", 0.55), ("outer", 1.15), ("depth", 1.60)):
        offset = smooth_atr * multiplier * trail_size
        output[f"{label}_trail"] = pd.Series(
            np.where(state == 1, smooth_basis - offset,
                     np.where(state == -1, smooth_basis + offset, smooth_basis)), index=bars.index)
    band_basis, band_atr = pine.ema(smooth_basis, smoothness), pine.ema(smooth_atr, smoothness)
    for i, multiplier in enumerate((1.30, 2.00, 2.90), 1):
        output[f"upper_band_{i}"] = band_basis + band_atr * multiplier * trail_size
        output[f"lower_band_{i}"] = band_basis - band_atr * multiplier * trail_size
    return pd.DataFrame(output, index=bars.index)
