# indicators/elliott_wave.py
"""
Elliott Wave detection via swing highs/lows and Fibonacci retracement.

Full Elliott Wave analysis is highly subjective. This module implements the
quantifiable core: detecting price swings and identifying Fibonacci retracement
zones where Wave 2/4 corrections tend to end and new impulse moves begin.

The algorithm:
  1. Detect swing highs and swing lows using a rolling window.
  2. Measure the most recent impulse move (swing low → swing high for uptrend,
     swing high → swing low for downtrend).
  3. Compute Fibonacci retracement levels (23.6%, 38.2%, 50%, 61.8%, 78.6%).
  4. Generate entry signals when price retraces to a Fibonacci zone and reverses.

This produces signals analogous to entering at Wave 3 (after Wave 2 retracement)
or Wave 5 (after Wave 4 retracement) — the highest-probability Elliott Wave trades.
"""

import pandas as pd
import numpy as np
from numba import njit
from utils.logging_utils import setup_logging

logger = setup_logging(log_file="logs/backtester.log")

# Standard Fibonacci retracement levels
FIB_LEVELS = np.array([0.236, 0.382, 0.500, 0.618, 0.786])


@njit
def _detect_swings(high: np.ndarray, low: np.ndarray, order: int):
    """
    Detects swing highs and swing lows using a rolling window.

    A swing high at bar i requires high[i] to be the max of
    high[i-order : i+order+1].  Similarly for swing lows.

    Args:
        high: High prices array.
        low: Low prices array.
        order: Number of bars on each side to confirm a swing.

    Returns:
        swing_high: Array of NaN except at confirmation bars (value = pivot high price).
        swing_low:  Array of NaN except at confirmation bars (value = pivot low price).
    """
    n = len(high)
    swing_high = np.full(n, np.nan)
    swing_low = np.full(n, np.nan)

    # A centered pivot becomes observable only after its right-hand window closes.
    for i in range(order, n - order):
        # Check if high[i] is the max in the window
        is_swing_high = True
        for j in range(i - order, i + order + 1):
            if j != i and high[j] >= high[i]:
                is_swing_high = False
                break
        if is_swing_high:
            swing_high[i + order] = high[i]

        # Check if low[i] is the min in the window
        is_swing_low = True
        for j in range(i - order, i + order + 1):
            if j != i and low[j] <= low[i]:
                is_swing_low = False
                break
        if is_swing_low:
            swing_low[i + order] = low[i]

    return swing_high, swing_low


@njit
def _compute_fib_signals(
    close: np.ndarray,
    swing_high: np.ndarray,
    swing_low: np.ndarray,
    fib_level: float,
    fib_tolerance: float,
):
    """
    Generates entry/exit signals based on Fibonacci retracement zones.

    Long entry: After an upswing (swing_low → swing_high), price retraces down
    to the fib_level zone and then moves back up (close crosses above the zone).

    Short entry: After a downswing (swing_high → swing_low), price retraces up
    to the fib_level zone and then moves back down.

    Args:
        close: Close prices.
        swing_high: Swing high values (NaN where no swing).
        swing_low: Swing low values (NaN where no swing).
        fib_level: Fibonacci retracement level (e.g. 0.382).
        fib_tolerance: Width of the Fibonacci zone as fraction (e.g. 0.02 = ±2%).

    Returns:
        long_entries, long_exits, short_entries, short_exits — boolean arrays.
    """
    n = len(close)
    long_entries = np.zeros(n, dtype=np.bool_)
    long_exits = np.zeros(n, dtype=np.bool_)
    short_entries = np.zeros(n, dtype=np.bool_)
    short_exits = np.zeros(n, dtype=np.bool_)

    # Track the most recent swing points
    last_sh = np.nan  # last swing high price
    last_sl = np.nan  # last swing low price
    last_sh_newer = False  # True if swing high is more recent than swing low

    in_long = False
    in_short = False

    for i in range(n):
        # Update swing tracking
        if not np.isnan(swing_high[i]):
            last_sh = swing_high[i]
            last_sh_newer = True
        if not np.isnan(swing_low[i]):
            last_sl = swing_low[i]
            last_sh_newer = False

        if np.isnan(last_sh) or np.isnan(last_sl):
            continue

        move = abs(last_sh - last_sl)
        if move < 1e-10:
            continue

        # Uptrend: swing low happened first, then swing high
        # Retracement level = swing_high - fib_level * move
        if last_sh_newer:
            fib_price = last_sh - fib_level * move
            zone_upper = fib_price * (1 + fib_tolerance)
            zone_lower = fib_price * (1 - fib_tolerance)

            if not in_long and zone_lower <= close[i] <= zone_upper:
                # Price is in the Fib zone — check for bounce (close > prev close)
                if i > 0 and close[i] > close[i - 1]:
                    long_entries[i] = True
                    in_long = True

            # Exit long when price makes a new swing high or drops below the swing low
            if in_long:
                if close[i] >= last_sh or close[i] <= last_sl:
                    long_exits[i] = True
                    in_long = False

        # Downtrend: swing high happened first, then swing low
        # Retracement level = swing_low + fib_level * move
        if not last_sh_newer:
            fib_price = last_sl + fib_level * move
            zone_upper = fib_price * (1 + fib_tolerance)
            zone_lower = fib_price * (1 - fib_tolerance)

            if not in_short and zone_lower <= close[i] <= zone_upper:
                if i > 0 and close[i] < close[i - 1]:
                    short_entries[i] = True
                    in_short = True

            if in_short:
                if close[i] <= last_sl or close[i] >= last_sh:
                    short_exits[i] = True
                    in_short = False

    return long_entries, long_exits, short_entries, short_exits


@njit
def _compute_fib_signals_batch(
    close: np.ndarray,
    swing_high: np.ndarray,
    swing_low: np.ndarray,
    fib_levels: np.ndarray,
    fib_tolerances: np.ndarray,
):
    """
    Batched version of _compute_fib_signals: processes ALL (fib_level, fib_tolerance)
    combinations in a single pass through the price data.

    This replaces 6,750+ individual Numba calls per swing order with one call,
    eliminating Python→Numba dispatch overhead and improving cache locality.

    Column ordering: fib_level varies slowest, fib_tolerance varies fastest
    (matching the iteration order of the original triple loop).

    Returns:
        4 arrays of shape (n_bars, n_levels * n_tolerances).
    """
    n = len(close)
    n_levels = len(fib_levels)
    n_tols = len(fib_tolerances)
    n_combos = n_levels * n_tols

    long_entries = np.zeros((n, n_combos), dtype=np.bool_)
    long_exits = np.zeros((n, n_combos), dtype=np.bool_)
    short_entries = np.zeros((n, n_combos), dtype=np.bool_)
    short_exits = np.zeros((n, n_combos), dtype=np.bool_)

    in_long = np.zeros(n_combos, dtype=np.bool_)
    in_short = np.zeros(n_combos, dtype=np.bool_)

    last_sh = np.nan
    last_sl = np.nan
    last_sh_newer = False

    for i in range(n):
        # Update swing tracking (once per bar, shared across all combos)
        if not np.isnan(swing_high[i]):
            last_sh = swing_high[i]
            last_sh_newer = True
        if not np.isnan(swing_low[i]):
            last_sl = swing_low[i]
            last_sh_newer = False

        if np.isnan(last_sh) or np.isnan(last_sl):
            continue

        move = abs(last_sh - last_sl)
        if move < 1e-10:
            continue

        close_i = close[i]
        prev_close = close[i - 1] if i > 0 else close_i

        for fl_idx in range(n_levels):
            fib_level = fib_levels[fl_idx]
            base = fl_idx * n_tols

            if last_sh_newer:
                fib_price = last_sh - fib_level * move
            else:
                fib_price = last_sl + fib_level * move

            for ft_idx in range(n_tols):
                c = base + ft_idx
                fib_tol = fib_tolerances[ft_idx]
                zone_upper = fib_price * (1.0 + fib_tol)
                zone_lower = fib_price * (1.0 - fib_tol)

                if last_sh_newer:
                    if not in_long[c] and zone_lower <= close_i <= zone_upper:
                        if close_i > prev_close:
                            long_entries[i, c] = True
                            in_long[c] = True
                    if in_long[c]:
                        if close_i >= last_sh or close_i <= last_sl:
                            long_exits[i, c] = True
                            in_long[c] = False
                else:
                    if not in_short[c] and zone_lower <= close_i <= zone_upper:
                        if close_i < prev_close:
                            short_entries[i, c] = True
                            in_short[c] = True
                    if in_short[c]:
                        if close_i <= last_sl or close_i >= last_sh:
                            short_exits[i, c] = True
                            in_short[c] = False

    return long_entries, long_exits, short_entries, short_exits


def detect_swings(
    high: pd.Series,
    low: pd.Series,
    order: int = 5,
) -> tuple[pd.Series, pd.Series]:
    """
    Detects swing highs and swing lows.

    Args:
        high: High price series.
        low: Low price series.
        order: Number of bars on each side to confirm a swing point.

    Returns:
        (swing_highs, swing_lows) — Series with NaN except at swing points.
    """
    sh, sl = _detect_swings(high.values, low.values, order)
    return pd.Series(sh, index=high.index), pd.Series(sl, index=low.index)


def compute_fib_retracement_levels(
    swing_high: float,
    swing_low: float,
    direction: str = "up",
) -> dict[str, float]:
    """
    Computes Fibonacci retracement price levels for a given swing move.

    Args:
        swing_high: The swing high price.
        swing_low: The swing low price.
        direction: "up" = retracing an up-move, "down" = retracing a down-move.

    Returns:
        Dict mapping level names to price values.
    """
    move = swing_high - swing_low
    levels = {}
    for fib in FIB_LEVELS:
        if direction == "up":
            levels[f"{fib:.1%}"] = swing_high - fib * move
        else:
            levels[f"{fib:.1%}"] = swing_low + fib * move
    return levels
