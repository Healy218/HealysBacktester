# signals/stoch_crossover.py
"""
Stochastic Oscillator Crossover signal generator.

Entry (long):  %K crosses above %D while %K is below the oversold threshold.
Exit  (long):  %K crosses below %D while %K is above the overbought threshold.
Entry (short): %K crosses below %D while %K is above the overbought threshold.
Exit  (short): %K crosses above %D while %K is below the oversold threshold.

Sweeps over k_window × d_window × oversold_threshold × overbought_threshold.
Uses vbt.STOCH.run() for vectorized indicator computation, then builds the
full cross-product of window combos × threshold combos.
"""

import pandas as pd
import numpy as np
import vectorbt as vbt
from itertools import product as iter_product
from utils.logging_utils import setup_logging
from utils.error_handling import handle_errors

logger = setup_logging(log_file="logs/backtester.log")


@handle_errors
def generate_stoch_signals(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    k_window_range: np.ndarray,
    d_window_range: np.ndarray,
    oversold_range: np.ndarray | None = None,
    overbought_range: np.ndarray | None = None,
    enable_shorting: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame | None, pd.DataFrame | None]:
    """
    Generates entry/exit signals based on Stochastic %K/%D crossovers
    for all combinations of k_window, d_window, oversold, and overbought.

    Args:
        high: High price series.
        low: Low price series.
        close: Close price series.
        k_window_range: 1D array of %K lookback windows.
        d_window_range: 1D array of %D smoothing windows.
        oversold_range: 1D array of oversold thresholds (default: [20]).
        overbought_range: 1D array of overbought thresholds (default: [80]).
        enable_shorting: If True, generate short entry/exit signals.

    Returns:
        (entries, exits, short_entries, short_exits) — boolean DataFrames with
        MultiIndex columns.
    """
    if close.empty:
        raise ValueError("Close price series is empty.")

    k_window_range = np.asarray(k_window_range, dtype=int)
    d_window_range = np.asarray(d_window_range, dtype=int)
    if oversold_range is None:
        oversold_range = np.array([20])
    else:
        oversold_range = np.asarray(oversold_range)
    if overbought_range is None:
        overbought_range = np.array([80])
    else:
        overbought_range = np.asarray(overbought_range)

    if k_window_range.size == 0 or d_window_range.size == 0:
        raise ValueError("K and D window ranges cannot be empty.")

    # Step 1: Build window combos and compute STOCH for each unique (k, d) pair
    window_combos = list(iter_product(k_window_range, d_window_range))
    n_windows = len(window_combos)
    k_arr = np.array([c[0] for c in window_combos])
    d_arr = np.array([c[1] for c in window_combos])

    n_thresholds = oversold_range.size * overbought_range.size
    total_combos = n_windows * n_thresholds
    logger.info(
        f"[STOCH] {n_windows} window combos × {n_thresholds} threshold combos "
        f"= {total_combos:,} total combinations"
    )

    try:
        stoch = vbt.STOCH.run(high, low, close, k_window=k_arr, d_window=d_arr)
    except Exception as e:
        logger.error(f"[STOCH] vbt.STOCH.run() failed: {e}")
        raise

    pct_k = stoch.percent_k  # DataFrame: rows=bars, cols=window combos
    pct_d = stoch.percent_d

    if not isinstance(pct_k, pd.DataFrame):
        raise TypeError(f"STOCH did not produce DataFrames (got {type(pct_k)}).")

    # Pre-compute crossovers (one per window combo) — these are reused across thresholds
    k_cross_above_d = pct_k.vbt.crossed_above(pct_d)
    k_cross_below_d = pct_k.vbt.crossed_below(pct_d)

    # Step 2: For each threshold pair, apply the zone filter and tile into the full cross-product
    all_entries = []
    all_exits = []
    all_short_entries = []
    all_short_exits = []
    col_tuples = []

    window_col_names = list(pct_k.columns)  # original window combo column identifiers

    for oversold in oversold_range:
        for overbought in overbought_range:
            in_oversold = pct_k < oversold
            in_overbought = pct_k > overbought

            entries = k_cross_above_d & in_oversold
            exits = k_cross_below_d & in_overbought

            all_entries.append(entries)
            all_exits.append(exits)

            if enable_shorting:
                all_short_entries.append(k_cross_below_d & in_overbought)
                all_short_exits.append(k_cross_above_d & in_oversold)

            # Build MultiIndex column tuples: (k_window, d_window, oversold, overbought)
            for wc in window_col_names:
                if isinstance(wc, tuple):
                    col_tuples.append((*wc, int(oversold), int(overbought)))
                else:
                    col_tuples.append((wc, int(oversold), int(overbought)))

    # Step 3: Concatenate all DataFrames horizontally
    logger.info("[STOCH] Assembling full cross-product signal DataFrames...")
    entries_df = pd.concat(all_entries, axis=1)
    exits_df = pd.concat(all_exits, axis=1)

    # Apply MultiIndex columns
    mi = pd.MultiIndex.from_tuples(
        col_tuples,
        names=["stoch_k_window", "stoch_d_window", "oversold", "overbought"],
    )
    entries_df.columns = mi
    exits_df.columns = mi

    short_entries_df = None
    short_exits_df = None
    if enable_shorting and all_short_entries:
        short_entries_df = pd.concat(all_short_entries, axis=1)
        short_exits_df = pd.concat(all_short_exits, axis=1)
        short_entries_df.columns = mi
        short_exits_df.columns = mi

    logger.info(f"[STOCH] Signals generated. Shape: {entries_df.shape}")
    return entries_df, exits_df, short_entries_df, short_exits_df
