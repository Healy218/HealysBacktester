# Corrected signals/volume_breakout.py to handle Series output from vbt.MA.run

import pandas as pd
import numpy as np
import vectorbt as vbt
import traceback
from itertools import product as iter_product

def generate_volume_signals(
    ohlcv_df: pd.DataFrame,      # Needs 'Open', 'High', 'Low', 'Close', 'Volume'
    window: np.ndarray,          # Rolling window for average volume
    multiplier: np.ndarray,      # Factor to multiply average volume by for breakout threshold
    exit_ma_window: np.ndarray,  # Exit MA window parameter
    confirm_price_increase: bool = True, # Require price increase on breakout day?
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame | None, pd.DataFrame | None]:
    """
    Generates entry signals based on Volume Breakouts and exit signals based
    on price crossing below a Moving Average. Uses vectorized operations.
    Handles cases where only one exit_ma_window is provided.

    Args:
        ohlcv_df: DataFrame with OHLCV data.
        window: 1D numpy array of rolling window periods for volume averaging.
        multiplier: 1D numpy array of multipliers for the breakout threshold.
        exit_ma_window: 1D numpy array of MA windows for exit signal.
        confirm_price_increase: If True, requires Close > previous Close for entry signal.

    Returns:
        A tuple containing: entries_df, exits_df, None, None.
        Columns are MultiIndex named ('volume_window', 'volume_multiplier', 'exit_ma_window').
    """
    # --- Input Validation ---
    if not isinstance(window, np.ndarray): window = np.array(window)
    if not isinstance(multiplier, np.ndarray): multiplier = np.array(multiplier)
    if not isinstance(exit_ma_window, np.ndarray): exit_ma_window = np.array(exit_ma_window)

    if window.size == 0 or multiplier.size == 0 or exit_ma_window.size == 0:
        raise ValueError("Input window, multiplier, and exit_ma_window arrays cannot be empty.")
    required_cols = ['Close', 'Volume']
    if not all(col in ohlcv_df.columns for col in required_cols):
         raise ValueError(f"OHLCV DataFrame must contain {required_cols} columns.")

    # --- Prepare Parameter Combinations and Final Index ---
    unique_vol_windows = np.unique(window)
    unique_multipliers = np.unique(multiplier)
    unique_exit_windows = np.unique(exit_ma_window)

    param_product = list(iter_product(window, multiplier, exit_ma_window))
    column_index = pd.MultiIndex.from_tuples(
        param_product,
        names=['volume_window', 'volume_multiplier', 'exit_ma_window']
    )
    n_combinations = len(param_product)
    n_rows = len(ohlcv_df) # Get number of rows for reshaping later

    print(f"Calculating Volume/MA signals for {n_combinations} combinations (vectorized)...")

    # --- Vectorized Calculation ---
    try:
        volume_series = ohlcv_df['Volume']
        close_series = ohlcv_df['Close']

        # 1. Calculate Rolling Average Volume
        avg_volume_df = vbt.MA.run(volume_series, window=unique_vol_windows, short_name='vol_ma').ma
        avg_volume_df.columns = unique_vol_windows

        # 2. Calculate Exit Moving Average
        exit_ma_output = vbt.MA.run(close_series, window=unique_exit_windows, short_name='exit_ma').ma
        # exit_ma_output could be Series or DataFrame

        # 3. Prepare arrays for broadcasting ENTRY signals
        volume_np = volume_series.values[:, np.newaxis]

        window_map = {w: i for i, w in enumerate(unique_vol_windows)}
        col_indices_vol = [window_map[w] for w, m, e in param_product]
        avg_volume_np = avg_volume_df.values[:, col_indices_vol] # Shape (n_rows, n_combinations)

        multipliers_ordered = np.array([m for w, m, e in param_product])
        multiplier_aligned_np = multipliers_ordered[np.newaxis, :] # Shape (1, n_combinations)

        volume_breakout_np = volume_np > (multiplier_aligned_np * avg_volume_np)

        if confirm_price_increase:
            price_increase_np = (close_series > close_series.shift(1)).values[:, np.newaxis]
            entries_np = volume_breakout_np & price_increase_np
        else:
            entries_np = volume_breakout_np

        # 4. Prepare arrays for broadcasting EXIT signals <<-- MODIFIED SECTION
        close_np = close_series.values[:, np.newaxis] # Shape (n_rows, 1)

        if isinstance(exit_ma_output, pd.Series):
             # Only one exit window was calculated, result is Series
             exit_ma_1d_np = exit_ma_output.values # Shape (n_rows,)
             # Tile this 1D array to match the number of combinations
             exit_ma_np = np.tile(exit_ma_1d_np[:, np.newaxis], (1, n_combinations)) # Shape (n_rows, n_combinations)
        elif isinstance(exit_ma_output, pd.DataFrame):
             # Multiple exit windows calculated, result is DataFrame
             exit_ma_df = exit_ma_output # Rename for clarity
             exit_ma_df.columns = unique_exit_windows # Ensure columns are named correctly

             # Create exit_ma_np aligned with the final column_index order
             exit_window_map = {e: i for i, e in enumerate(unique_exit_windows)}
             col_indices_exit = [exit_window_map[e] for w, m, e in param_product]
             exit_ma_np = exit_ma_df.values[:, col_indices_exit] # Shape (n_rows, n_combinations)
        else:
             raise TypeError(f"Unexpected output type from exit MA calculation: {type(exit_ma_output)}")

        # Calculate Exit condition: Close < Exit MA
        exits_np = close_np < exit_ma_np # Broadcasting (n_rows, 1) < (n_rows, n_combinations)

        # 5. Create Final DataFrames
        entries_df = pd.DataFrame(entries_np, index=ohlcv_df.index, columns=column_index)
        entries_df = entries_df.fillna(False)

        exits_df = pd.DataFrame(exits_np, index=ohlcv_df.index, columns=column_index)
        exits_df = exits_df.fillna(False)

    except Exception as e:
        print(f"Error during vectorized signal calculation: {e}")
        traceback.print_exc()
        raise

    # Optional: Clean signals...

    print(f"Volume Breakout/MA Exit signals generated. Shape: {entries_df.shape}")
    return entries_df, exits_df, None, None # No short signals