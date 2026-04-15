# signals/bbands_breakout.py
"""
Bollinger Bands Breakout signal generator.

Entry (long):  Close crosses above the upper Bollinger Band.
Exit  (long):  Close crosses below the middle band (MA).
Entry (short): Close crosses below the lower Bollinger Band.
Exit  (short): Close crosses above the middle band (MA).

Uses vbt.BBANDS.run() with array parameters for vectorized parameter sweep.
"""

import pandas as pd
import numpy as np
import vectorbt as vbt
import warnings
from itertools import product as iter_product
from utils.logging_utils import setup_logging
from utils.error_handling import handle_errors

logger = setup_logging(log_file="logs/backtester.log")


@handle_errors
def generate_bbands_signals(
    close_prices_series: pd.Series,
    window_range: np.ndarray,
    std_range: np.ndarray,
    enable_shorting: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame | None, pd.DataFrame | None]:
    """
    Generates entry/exit signals based on Bollinger Band breakouts
    for all combinations of window and std_dev multiplier.

    Args:
        close_prices_series: Close price series.
        window_range: 1D array of lookback window values (e.g., np.arange(10, 51, 2)).
        std_range: 1D array of std dev multiplier values (e.g., np.arange(1.0, 3.25, 0.25)).
        enable_shorting: If True, generate short entry/exit signals.

    Returns:
        (entries, exits, short_entries, short_exits) — boolean DataFrames with
        MultiIndex columns (bbands_window, bbands_alpha).
    """
    if not isinstance(close_prices_series, pd.Series) or close_prices_series.empty:
        raise ValueError("Input must be a non-empty pandas Series.")

    window_range = np.asarray(window_range)
    std_range = np.asarray(std_range)

    if window_range.size == 0 or std_range.size == 0:
        raise ValueError("Window and std ranges cannot be empty.")

    # Build cross-product of parameters
    combos = list(iter_product(window_range, std_range))
    n_combos = len(combos)
    logger.info(f"[BBANDS] Generating signals for {n_combos} combinations...")

    windows_arr = np.array([int(c[0]) for c in combos])
    alpha_arr = np.array([float(c[1]) for c in combos])

    # Run vectorized BBANDS calculation across all parameter combos
    try:
        bb = vbt.BBANDS.run(
            close_prices_series,
            window=windows_arr,
            alpha=alpha_arr,
        )
    except Exception as e:
        logger.error(f"[BBANDS] vbt.BBANDS.run() failed: {e}")
        raise

    upper = bb.upper
    middle = bb.middle
    lower = bb.lower

    if not isinstance(upper, pd.DataFrame):
        raise TypeError(f"BBANDS did not produce DataFrames (got {type(upper)}).")

    # Long signals: enter when close breaks above upper band, exit below middle
    logger.info("[BBANDS] Generating crossover signals...")
    entries = close_prices_series.vbt.crossed_above(upper)
    exits = close_prices_series.vbt.crossed_below(middle)

    # Short signals
    short_entries = None
    short_exits = None
    if enable_shorting:
        short_entries = close_prices_series.vbt.crossed_below(lower)
        short_exits = close_prices_series.vbt.crossed_above(middle)

    logger.info(f"[BBANDS] Signals generated. Shape: {entries.shape}")
    return entries, exits, short_entries, short_exits
