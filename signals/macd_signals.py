# signals/macd_signals.py

import pandas as pd
import numpy as np
import vectorbt as vbt
import warnings
from itertools import product as iter_product
from utils.logging_utils import setup_logging
from utils.error_handling import handle_errors, BacktesterError # Import the decorator and any custom errors if needed

# Setup logger
logger = setup_logging(log_file="logs/backtester.log")

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
    with aligned 1D arrays. Vectorbt infers parameter names from keywords.

    Args:
        close_prices_series: pandas Series of close prices.
        fast_window: 1D numpy array of MACD fast EMA window periods (e.g., np.arange(5, 21)).
        slow_window: 1D numpy array of MACD slow EMA window periods (e.g., np.arange(15, 51)).
        signal_window: 1D numpy array of MACD signal line EMA window periods (e.g., np.arange(5, 21)).
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

    logger.info(f"Calculating MACD using vectorbt for {len(valid_params)} valid combinations...")

    # 1. Calculate MACD indicator using vectorbt with the ALIGNED parameter lists
    try:
        # Pass the aligned 1D arrays of valid parameters.
        # Vectorbt infers parameter names from the keywords fast_window, slow_window, signal_window.
        # REMOVED param_names argument from this call
        macd_indicator = vbt.MACD.run(
            close_prices_series,
            fast_window=valid_fast_windows,   # Pass the filtered 1D array
            slow_window=valid_slow_windows,   # Pass the filtered 1D array
            signal_window=valid_signal_windows, # Pass the filtered 1D array
            # param_names=['fast_window', 'slow_window', 'signal_window'], # Removed this line
            short_name='macd'
        )
        # Extract MACD and Signal lines
        macd_df = macd_indicator.macd
        signal_df = macd_indicator.signal

    except Exception as e:
        logger.error(f"Error calculating MACD using vectorbt: {e}")
        import traceback
        traceback.print_exc()
        raise

    # Check calculation results
    if macd_df is None or signal_df is None:
         raise ValueError("MACD calculation failed to produce results (MACD or Signal DataFrame is None).")
    if not isinstance(macd_df, pd.DataFrame) or not isinstance(signal_df, pd.DataFrame):
         raise TypeError(f"MACD calculation did not return DataFrames. Got: {type(macd_df)}, {type(signal_df)}")
    if macd_df.empty or signal_df.empty:
         raise ValueError("MACD calculation resulted in empty DataFrames.")

    # Check column names (should be inferred correctly from keywords)
    expected_names = ['macd_fast_window', 'macd_slow_window', 'macd_signal_window']
    if list(macd_df.columns.names) != expected_names:
        warnings.warn(f"MACD output columns have unexpected names: {macd_df.columns.names}. Expected: {expected_names}. Attempting to rename.")
        # Attempt to rename if necessary
        try:
             # Make sure the number of levels matches before renaming
             if macd_df.columns.nlevels == len(expected_names):
                 macd_df.columns = macd_df.columns.set_names(expected_names)
                 signal_df.columns = signal_df.columns.set_names(expected_names)
             else:
                 warnings.warn(f"Cannot rename levels automatically. Level count mismatch ({macd_df.columns.nlevels} vs {len(expected_names)}).")
        except Exception as name_e:
             warnings.warn(f"Could not rename MACD column levels: {name_e}")

    logger.info(f"MACD indicator calculated. Shape: {macd_df.shape}")
    logger.info("Generating MACD crossover signals...")

    # 2. Generate Long Signals based on crossover
    entries_df = macd_df.vbt.crossed_above(signal_df)
    exits_df = macd_df.vbt.crossed_below(signal_df)

    # 3. Generate Short Signals (Optional)
    short_entries_df = None
    short_exits_df = None
    if short_entries:
         logger.info("Generating Short Entry signals (MACD crosses below Signal)...")
         short_entries_df = macd_df.vbt.crossed_below(signal_df)
    if short_exits:
         logger.info("Generating Short Exit signals (MACD crosses above Signal)...")
         short_exits_df = macd_df.vbt.crossed_above(signal_df)

    logger.info(f"MACD signals generated. Entries shape: {entries_df.shape}")
    return entries_df, exits_df, short_entries_df, short_exits_df