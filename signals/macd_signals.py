# signals/macd_signals.py

import gc
import pandas as pd
import numpy as np
import vectorbt as vbt
import warnings
from itertools import product as iter_product
from utils.logging_utils import setup_logging
from utils.error_handling import handle_errors, BacktesterError

# Setup logger
logger = setup_logging(log_file="logs/backtester.log")

# Memory budget for float64 arrays from vbt.MACD.run()
# MACD produces macd, signal, histogram + internal EMAs (~8 float64 arrays)
_SIGNAL_MEM_BUDGET = 2 * 1024**3
_MACD_FLOAT_ARRAYS = 8


def _max_macd_combos(n_rows: int) -> int:
    """Max parameter combos per vbt.MACD.run() call to stay within memory budget."""
    cols = _SIGNAL_MEM_BUDGET // (_MACD_FLOAT_ARRAYS * max(n_rows, 1) * 8)
    return max(500, min(50_000, int(cols)))


@handle_errors
def generate_macd_signals(
    close_prices_series: pd.Series,
    fast_window: np.ndarray,     # Expect numpy array (range)
    slow_window: np.ndarray,     # Expect numpy array (range)
    signal_window: np.ndarray,   # Expect numpy array (range)
    macd_col_name: str = 'macd', # Default name from vbt.MACD
    signal_col_name: str = 'signal',# Default name from vbt.MACD
    short_entries: bool = False, # Optionally generate short signals
    short_exits: bool = False    # Optionally generate short signals
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame | None, pd.DataFrame | None]:
    """
    Generates entry and exit signal DataFrames based on MACD crossovers
    for MULTIPLE parameter combinations using vectorbt.

    Manually generates the cross-product of input parameter ranges and filters
    for valid combinations (fast < slow) before calling vbt.MACD.run
    with aligned 1D arrays. For large parameter spaces, internally chunks
    the computation to stay within a ~2 GB memory budget per chunk.

    Args:
        close_prices_series: pandas Series of close prices.
        fast_window: 1D numpy array of MACD fast EMA window periods.
        slow_window: 1D numpy array of MACD slow EMA window periods.
        signal_window: 1D numpy array of MACD signal line EMA window periods.
        macd_col_name, signal_col_name: Names of columns expected in vbt.MACD output.
        short_entries, short_exits: Flags to enable short signals.

    Returns:
        A tuple containing four items: entries_df, exits_df, short_entries_df, short_exits_df.
        Columns will have a MultiIndex named ('fast_window', 'slow_window', 'signal_window').

    Raises:
        ValueError: If input series is empty, input arrays are empty, no valid combinations found,
                    or indicator calculation fails.
        TypeError: If indicator calculation does not return expected DataFrames.
    """
    if not isinstance(close_prices_series, pd.Series) or close_prices_series.empty:
        raise ValueError("Input 'close_prices_series' must be a non-empty pandas Series.")
    if not isinstance(fast_window, np.ndarray) or not isinstance(slow_window, np.ndarray) or not isinstance(signal_window, np.ndarray):
         warnings.warn("Inputs fast_window, slow_window, or signal_window are not numpy arrays. Attempting conversion.")
         fast_window = np.asarray(fast_window)
         slow_window = np.asarray(slow_window)
         signal_window = np.asarray(signal_window)

    if fast_window.size == 0 or slow_window.size == 0 or signal_window.size == 0:
        raise ValueError("Input window range arrays cannot be empty.")

    # --- Manually Create and Filter Parameter Combinations ---
    logger.info("Generating parameter combinations...")
    param_product = list(iter_product(fast_window, slow_window, signal_window))
    logger.info(f"  Total combinations generated: {len(param_product)}")

    # Filter for valid combinations where fast < slow
    valid_params = [(int(f), int(s), int(g)) for f, s, g in param_product if int(f) < int(s)]
    logger.info(f"  Valid combinations (fast < slow): {len(valid_params)}")

    if not valid_params:
        raise ValueError("No valid parameter combinations found where fast_window < slow_window.")

    # Create aligned 1D numpy arrays for the *valid* combinations
    valid_fast_windows = np.array([p[0] for p in valid_params], dtype=int)
    valid_slow_windows = np.array([p[1] for p in valid_params], dtype=int)
    valid_signal_windows = np.array([p[2] for p in valid_params], dtype=int)

    n_valid = len(valid_params)
    n_rows = len(close_prices_series)
    max_per_chunk = _max_macd_combos(n_rows)

    # Single-pass: fits in memory
    if n_valid <= max_per_chunk:
        logger.info(f"Calculating MACD using vectorbt for {n_valid} valid combinations...")
        entries_df, exits_df, se_df, sx_df = _macd_single_pass(
            close_prices_series, valid_fast_windows, valid_slow_windows,
            valid_signal_windows, short_entries, short_exits,
        )
        logger.info(f"MACD signals generated. Entries shape: {entries_df.shape}")
        return entries_df, exits_df, se_df, sx_df

    # Chunked signal generation
    n_chunks = (n_valid + max_per_chunk - 1) // max_per_chunk
    logger.info(
        f"[MACD] Signal generation chunked: {n_valid:,} combos → "
        f"{n_chunks} chunks of ≤{max_per_chunk:,} (n_rows={n_rows:,})"
    )

    all_entries = []
    all_exits = []
    all_se = []
    all_sx = []

    for chunk_idx, start in enumerate(range(0, n_valid, max_per_chunk)):
        end = min(start + max_per_chunk, n_valid)
        logger.info(f"[MACD]   Signal chunk {chunk_idx + 1}/{n_chunks}: combos {start:,}–{end:,}")

        chunk_e, chunk_x, chunk_se, chunk_sx = _macd_single_pass(
            close_prices_series,
            valid_fast_windows[start:end],
            valid_slow_windows[start:end],
            valid_signal_windows[start:end],
            short_entries, short_exits,
        )

        all_entries.append(chunk_e)
        all_exits.append(chunk_x)
        if chunk_se is not None:
            all_se.append(chunk_se)
        if chunk_sx is not None:
            all_sx.append(chunk_sx)

        gc.collect()

    entries_df = pd.concat(all_entries, axis=1)
    exits_df = pd.concat(all_exits, axis=1)
    short_entries_df = pd.concat(all_se, axis=1) if all_se else None
    short_exits_df = pd.concat(all_sx, axis=1) if all_sx else None

    logger.info(f"MACD signals generated. Entries shape: {entries_df.shape}")
    return entries_df, exits_df, short_entries_df, short_exits_df


def _macd_single_pass(
    close: pd.Series,
    fast_windows: np.ndarray,
    slow_windows: np.ndarray,
    signal_windows: np.ndarray,
    gen_short_entries: bool,
    gen_short_exits: bool,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame | None, pd.DataFrame | None]:
    """Run vbt.MACD for one batch of parameter combos and compute crossover signals."""
    try:
        macd_indicator = vbt.MACD.run(
            close,
            fast_window=fast_windows,
            slow_window=slow_windows,
            signal_window=signal_windows,
            short_name='macd'
        )
        macd_df = macd_indicator.macd
        signal_df = macd_indicator.signal
    except Exception as e:
        logger.error(f"Error calculating MACD using vectorbt: {e}")
        raise

    if macd_df is None or signal_df is None:
        raise ValueError("MACD calculation failed to produce results (MACD or Signal DataFrame is None).")
    if not isinstance(macd_df, pd.DataFrame) or not isinstance(signal_df, pd.DataFrame):
        raise TypeError(f"MACD calculation did not return DataFrames. Got: {type(macd_df)}, {type(signal_df)}")
    if macd_df.empty or signal_df.empty:
        raise ValueError("MACD calculation resulted in empty DataFrames.")

    # Fix column names if needed
    expected_names = ['macd_fast_window', 'macd_slow_window', 'macd_signal_window']
    if list(macd_df.columns.names) != expected_names:
        try:
            if macd_df.columns.nlevels == len(expected_names):
                macd_df.columns = macd_df.columns.set_names(expected_names)
                signal_df.columns = signal_df.columns.set_names(expected_names)
        except Exception:
            pass

    entries_df = macd_df.vbt.crossed_above(signal_df)
    exits_df = macd_df.vbt.crossed_below(signal_df)

    short_entries_df = None
    short_exits_df = None
    if gen_short_entries:
        logger.info("Generating Short Entry signals (MACD crosses below Signal)...")
        short_entries_df = macd_df.vbt.crossed_below(signal_df)
    if gen_short_exits:
        logger.info("Generating Short Exit signals (MACD crosses above Signal)...")
        short_exits_df = macd_df.vbt.crossed_above(signal_df)

    # Free float64 intermediates
    del macd_indicator, macd_df, signal_df

    return entries_df, exits_df, short_entries_df, short_exits_df
