# signals/bbands_breakout.py
"""
Bollinger Bands Breakout signal generator.

Entry (long):  Close crosses above the upper Bollinger Band.
Exit  (long):  Close crosses below the middle band (MA).
Entry (short): Close crosses below the lower Bollinger Band.
Exit  (short): Close crosses above the middle band (MA).

Uses vbt.BBANDS.run() with array parameters for vectorized parameter sweep.
For large parameter spaces, internally chunks the computation to stay within
a ~2 GB memory budget per chunk.
"""

import gc
import pandas as pd
import numpy as np
import vectorbt as vbt
import warnings
from itertools import product as iter_product
from utils.logging_utils import setup_logging
from utils.error_handling import handle_errors

logger = setup_logging(log_file="logs/backtester.log")

# Memory budget for float64 arrays from vbt.BBANDS.run().
# Each call produces upper/middle/lower DataFrames plus internal working arrays
# (~6 float64 arrays total).  We cap each chunk at ~2 GB to avoid OOM/swap.
_SIGNAL_MEM_BUDGET = 2 * 1024**3
_BBANDS_FLOAT_ARRAYS = 6


def _max_signal_combos(n_rows: int) -> int:
    """Max parameter combos per vbt.BBANDS.run() call to stay within memory budget."""
    cols = _SIGNAL_MEM_BUDGET // (_BBANDS_FLOAT_ARRAYS * max(n_rows, 1) * 8)
    return max(500, min(50_000, int(cols)))


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

    For large parameter spaces, internally chunks the vbt.BBANDS.run()
    call to avoid exceeding memory limits.

    Args:
        close_prices_series: Close price series.
        window_range: 1D array of lookback window values.
        std_range: 1D array of std dev multiplier values.
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
    logger.info(f"[BBANDS] Generating signals for {n_combos:,} combinations...")

    windows_arr = np.array([int(c[0]) for c in combos])
    alpha_arr = np.array([float(c[1]) for c in combos])

    n_rows = len(close_prices_series)
    max_per_chunk = _max_signal_combos(n_rows)

    # Single-pass: all combos fit within memory budget
    if n_combos <= max_per_chunk:
        entries, exits, se, sx = _bbands_single_pass(
            close_prices_series, windows_arr, alpha_arr, enable_shorting,
        )
        logger.info(f"[BBANDS] Signals generated. Shape: {entries.shape}")
        return entries, exits, se, sx

    # Chunked: process subsets to stay within memory budget
    n_chunks = (n_combos + max_per_chunk - 1) // max_per_chunk
    logger.info(
        f"[BBANDS] Signal generation chunked: {n_combos:,} combos → "
        f"{n_chunks} chunks of ≤{max_per_chunk:,} (n_rows={n_rows:,})"
    )

    all_entries = []
    all_exits = []
    all_short_entries = []
    all_short_exits = []

    for chunk_idx, start in enumerate(range(0, n_combos, max_per_chunk)):
        end = min(start + max_per_chunk, n_combos)
        logger.info(f"[BBANDS]   Signal chunk {chunk_idx + 1}/{n_chunks}: combos {start:,}–{end:,}")

        chunk_entries, chunk_exits, chunk_se, chunk_sx = _bbands_single_pass(
            close_prices_series,
            windows_arr[start:end],
            alpha_arr[start:end],
            enable_shorting,
        )

        all_entries.append(chunk_entries)
        all_exits.append(chunk_exits)
        if enable_shorting and chunk_se is not None:
            all_short_entries.append(chunk_se)
        if enable_shorting and chunk_sx is not None:
            all_short_exits.append(chunk_sx)

        gc.collect()

    entries = pd.concat(all_entries, axis=1)
    exits = pd.concat(all_exits, axis=1)
    short_entries = pd.concat(all_short_entries, axis=1) if all_short_entries else None
    short_exits = pd.concat(all_short_exits, axis=1) if all_short_exits else None

    logger.info(f"[BBANDS] Signals generated. Shape: {entries.shape}")
    return entries, exits, short_entries, short_exits


def _bbands_single_pass(
    close: pd.Series,
    windows_arr: np.ndarray,
    alpha_arr: np.ndarray,
    enable_shorting: bool,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame | None, pd.DataFrame | None]:
    """Run vbt.BBANDS for one batch of parameter combos and compute crossover signals."""
    try:
        bb = vbt.BBANDS.run(close, window=windows_arr, alpha=alpha_arr)
    except Exception as e:
        logger.error(f"[BBANDS] vbt.BBANDS.run() failed: {e}")
        raise

    upper = bb.upper
    middle = bb.middle
    lower = bb.lower

    if not isinstance(upper, pd.DataFrame):
        raise TypeError(f"BBANDS did not produce DataFrames (got {type(upper)}).")

    entries = close.vbt.crossed_above(upper)
    exits = close.vbt.crossed_below(middle)

    short_entries = None
    short_exits = None
    if enable_shorting:
        short_entries = close.vbt.crossed_below(lower)
        short_exits = close.vbt.crossed_above(middle)

    # Free float64 intermediates
    del bb, upper, middle, lower

    return entries, exits, short_entries, short_exits
