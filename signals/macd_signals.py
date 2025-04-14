# Corrected function for signals/macd_signals.py

import pandas as pd
import numpy as np
import vectorbt as vbt
import warnings
from itertools import product as iter_product # Use alias

def generate_macd_signals(
    close_prices_series: pd.Series,
    fast_window: np.ndarray,     # Expect numpy array
    slow_window: np.ndarray,     # Expect numpy array
    signal_window: np.ndarray,   # Expect numpy array
    macd_col_name: str = 'macd', # Column name for MACD line from vbt output
    signal_col_name: str = 'signal',# Column name for Signal line from vbt output
    short_entries: bool = False, # Optionally generate short signals
    short_exits: bool = False    # Optionally generate short signals
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame | None, pd.DataFrame | None]:
    """
    Generates entry and exit signal DataFrames based on MACD crossovers
    for MULTIPLE parameter combinations using vectorbt. Manually handles
    parameter cross-product generation before calling vbt.MACD.run.

    Args:
        close_prices_series: pandas Series of close prices.
        fast_window: 1D numpy array of MACD fast EMA window periods.
        slow_window: 1D numpy array of MACD slow EMA window periods.
        signal_window: 1D numpy array of MACD signal line EMA window periods.
        macd_col_name, signal_col_name: Names of columns in vbt.MACD output.
        short_entries, short_exits: Flags to enable short signals.

    Returns:
        A tuple containing four items: entries_df, exits_df, short_entries_df, short_exits_df.
        Columns are MultiIndex named ('fast_window', 'slow_window', 'signal_window').

    Raises:
        ValueError: If input arrays are empty or indicator calculation fails.
    """
    # Ensure inputs are numpy arrays
    if not isinstance(fast_window, np.ndarray): fast_window = np.array(fast_window)
    if not isinstance(slow_window, np.ndarray): slow_window = np.array(slow_window)
    if not isinstance(signal_window, np.ndarray): signal_window = np.array(signal_window)

    if fast_window.size == 0 or slow_window.size == 0 or signal_window.size == 0:
        raise ValueError("Input window arrays cannot be empty.")

    # --- Manually Create Parameter Combinations ---
    param_product = list(iter_product(fast_window, slow_window, signal_window))
    # Filter for valid combinations where fast < slow
    valid_params = [(f, s, g) for f, s, g in param_product if f < s]

    if not valid_params:
        raise ValueError("No valid combinations found where fast_window < slow_window.")

    # Create lists of parameters corresponding to the valid combinations
    valid_fast_windows = np.array([p[0] for p in valid_params])
    valid_slow_windows = np.array([p[1] for p in valid_params])
    valid_signal_windows = np.array([p[2] for p in valid_params])

    print(f"Calculating MACD for {len(valid_params)} valid combinations...")

    # 1. Calculate MACD indicator using vectorbt with the aligned parameter lists
    try:
        # ****** REMOVED param_names argument from this call ******
        macd_indicator = vbt.MACD.run(
            close_prices_series,
            fast_window=valid_fast_windows,
            slow_window=valid_slow_windows,
            signal_window=valid_signal_windows,
            short_name='macd'
        )
        # Extract MACD and Signal lines
        macd_df = macd_indicator.macd
        signal_df = macd_indicator.signal

    except Exception as e:
        print(f"Error calculating MACD using vectorbt: {e}")
        raise

    # Check calculation results
    if macd_df is None or signal_df is None:
         raise ValueError("MACD calculation failed to produce results.")
    if not isinstance(macd_df, pd.DataFrame) or not isinstance(signal_df, pd.DataFrame):
         raise TypeError(f"MACD calculation did not return DataFrames. Got: {type(macd_df)}, {type(signal_df)}")

    # --- Check/Set Column Names (Optional but safe) ---
    # vbt should automatically name levels based on kwargs 'fast_window', 'slow_window', 'signal_window'
    expected_names = ['fast_window', 'slow_window', 'signal_window']
    if list(macd_df.columns.names) != expected_names:
        try:
            macd_df.columns = macd_df.columns.set_names(expected_names)
            signal_df.columns = signal_df.columns.set_names(expected_names)
            warnings.warn("Automatically detected column names did not match expected. Renamed levels.")
        except Exception as name_e:
            warnings.warn(f"Could not automatically rename MACD column levels: {name_e}")


    print("Generating MACD crossover signals...")
    # 2. Generate Long Signals based on crossover
    entries_df = macd_df.vbt.crossed_above(signal_df)
    exits_df = macd_df.vbt.crossed_below(signal_df)

    # 3. Generate Short Signals (Optional)
    short_entries_df = None
    short_exits_df = None
    if short_entries:
         print("Generating Short Entry signals (MACD crosses below Signal)...")
         short_entries_df = macd_df.vbt.crossed_below(signal_df)
    if short_exits:
         print("Generating Short Exit signals (MACD crosses above Signal)...")
         short_exits_df = macd_df.vbt.crossed_above(signal_df)

    # Optional Cleaning...

    print(f"MACD signals generated. Shape: {entries_df.shape}")
    return entries_df, exits_df, short_entries_df, short_exits_df