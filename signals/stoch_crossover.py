# signals/stoch_crossover.py
"""
Stochastic Oscillator Crossover signal generator.

Entry (long):  %K crosses above %D while %K is below the oversold threshold (20).
Exit  (long):  %K crosses below %D while %K is above the overbought threshold (80).
Entry (short): %K crosses below %D while %K is above the overbought threshold (80).
Exit  (short): %K crosses above %D while %K is below the oversold threshold (20).

Uses vbt.STOCH.run() with array parameters for vectorized parameter sweep.
"""

import pandas as pd
import numpy as np
import vectorbt as vbt
from itertools import product as iter_product
from utils.logging_utils import setup_logging
from utils.error_handling import handle_errors

logger = setup_logging(log_file="logs/backtester.log")

# Stochastic zones — fixed thresholds (not part of parameter sweep)
_OVERSOLD = 20
_OVERBOUGHT = 80


@handle_errors
def generate_stoch_signals(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    k_window_range: np.ndarray,
    d_window_range: np.ndarray,
    enable_shorting: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame | None, pd.DataFrame | None]:
    """
    Generates entry/exit signals based on Stochastic %K/%D crossovers
    for all combinations of k_window and d_window.

    Args:
        high: High price series.
        low: Low price series.
        close: Close price series.
        k_window_range: 1D array of %K lookback windows (e.g., np.arange(5, 21)).
        d_window_range: 1D array of %D smoothing windows (e.g., np.arange(3, 10)).
        enable_shorting: If True, generate short entry/exit signals.

    Returns:
        (entries, exits, short_entries, short_exits) — boolean DataFrames with
        MultiIndex columns (stoch_k_window, stoch_d_window).
    """
    if close.empty:
        raise ValueError("Close price series is empty.")

    k_window_range = np.asarray(k_window_range, dtype=int)
    d_window_range = np.asarray(d_window_range, dtype=int)

    if k_window_range.size == 0 or d_window_range.size == 0:
        raise ValueError("K and D window ranges cannot be empty.")

    # Build cross-product
    combos = list(iter_product(k_window_range, d_window_range))
    n_combos = len(combos)
    logger.info(f"[STOCH] Generating signals for {n_combos} combinations...")

    k_arr = np.array([int(c[0]) for c in combos])
    d_arr = np.array([int(c[1]) for c in combos])

    # Run vectorized Stochastic calculation
    try:
        stoch = vbt.STOCH.run(
            high, low, close,
            k_window=k_arr,
            d_window=d_arr,
        )
    except Exception as e:
        logger.error(f"[STOCH] vbt.STOCH.run() failed: {e}")
        raise

    pct_k = stoch.percent_k
    pct_d = stoch.percent_d

    if not isinstance(pct_k, pd.DataFrame):
        raise TypeError(f"STOCH did not produce DataFrames (got {type(pct_k)}).")

    # Long entry: %K crosses above %D AND %K was below oversold zone
    k_cross_above_d = pct_k.vbt.crossed_above(pct_d)
    k_cross_below_d = pct_k.vbt.crossed_below(pct_d)
    in_oversold = pct_k < _OVERSOLD
    in_overbought = pct_k > _OVERBOUGHT

    entries = k_cross_above_d & in_oversold
    exits = k_cross_below_d & in_overbought

    short_entries = None
    short_exits = None
    if enable_shorting:
        short_entries = k_cross_below_d & in_overbought
        short_exits = k_cross_above_d & in_oversold

    logger.info(f"[STOCH] Signals generated. Shape: {entries.shape}")
    return entries, exits, short_entries, short_exits
