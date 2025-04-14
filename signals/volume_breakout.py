# filename: HealysBacktester/signals/volume_breakout.py

import pandas as pd
import numpy as np
import vectorbt as vbt
import traceback
from itertools import product as iter_product
from utils.logging_utils import setup_logging
from utils.error_handling import handle_errors, BacktesterError # Import the decorator and any custom errors if needed

# Setup logger
logger = setup_logging(log_file="logs/backtester.log")

@handle_errors
def generate_volume_signals(
    ohlcv_df: pd.DataFrame,            # Needs 'Open', 'High', 'Low', 'Close', 'Volume'
    volume_window_range: np.ndarray,   # Rolling window range for average volume
    volume_multiplier_range: np.ndarray,# Range of factors to multiply average volume by
    exit_ma_window_range: np.ndarray,  # Range of exit MA window parameters
    confirm_price_increase: bool = True, # Require price increase on breakout day?
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame | None, pd.DataFrame | None]:
    """
    Generates entry signals based on Volume Breakouts and exit signals based
    on price crossing below a Moving Average. Uses vectorized operations and handles
    combinations of volume_window_range, volume_multiplier_range, and exit_ma_window_range.

    Args:
        ohlcv_df: DataFrame with OHLCV data.
        volume_window_range: 1D numpy array defining the range for volume averaging windows.
        volume_multiplier_range: 1D numpy array defining the range for multipliers.
        exit_ma_window_range: 1D numpy array defining the range for exit MA windows.
        confirm_price_increase: If True, requires Close > previous Close for entry signal.

    Returns:
        A tuple containing: entries_df, exits_df, None, None.
        Columns are MultiIndex named ('volume_window', 'volume_multiplier', 'exit_ma_window').
    """
    # --- Input Validation ---
    # Ensure inputs are numpy arrays
    if not isinstance(volume_window_range, np.ndarray): volume_window_range = np.array(volume_window_range)
    if not isinstance(volume_multiplier_range, np.ndarray): volume_multiplier_range = np.array(volume_multiplier_range)
    if not isinstance(exit_ma_window_range, np.ndarray): exit_ma_window_range = np.array(exit_ma_window_range)

    if volume_window_range.size == 0 or volume_multiplier_range.size == 0 or exit_ma_window_range.size == 0:
        raise ValueError("Input range arrays cannot be empty.")
    required_cols = ['Close', 'Volume']
    if not all(col in ohlcv_df.columns for col in required_cols):
         raise ValueError(f"OHLCV DataFrame must contain {required_cols} columns.")

    # --- Prepare Parameter Combinations and Final Index ---
    # Use the actual input range arrays for the product
    param_product = list(iter_product(volume_window_range, volume_multiplier_range, exit_ma_window_range))
    column_index = pd.MultiIndex.from_tuples(
        param_product,
        names=['volume_window', 'volume_multiplier', 'exit_ma_window']
    )
    n_combinations = len(param_product)
    n_rows = len(ohlcv_df)

    logger.info(f"Calculating Volume/MA signals for {n_combinations} combinations (vectorized)...")

    # --- Vectorized Calculation ---
    try:
        volume_series = ohlcv_df['Volume']
        close_series = ohlcv_df['Close']

        # 1. Calculate Rolling Average Volume for ALL windows in the range
        avg_volume_df = vbt.MA.run(volume_series, window=volume_window_range, short_name='vol_ma').ma

        # 2. Calculate Exit Moving Average for ALL specified exit windows
        exit_ma_df = vbt.MA.run(close_series, window=exit_ma_window_range, short_name='exit_ma').ma

        # 3. Prepare arrays for broadcasting ENTRY signals
        volume_np = volume_series.values[:, np.newaxis]

        # Create index maps for efficient lookup
        window_map = {w: i for i, w in enumerate(volume_window_range)}
        # Get the column indices corresponding to the volume_window in each combination
        col_indices_vol = [window_map[w] for w, m, e in param_product]
        # Select and order the avg_volume columns according to the final combination order
        avg_volume_aligned_np = avg_volume_df.values[:, col_indices_vol]

        # Get the multipliers aligned with the final combination order
        # Map multipliers if needed (though direct array creation is fine here)
        multipliers_ordered = np.array([m for w, m, e in param_product])
        multiplier_aligned_np = multipliers_ordered[np.newaxis, :]

        # Calculate Volume Breakout condition using broadcasting
        volume_breakout_np = volume_np > (multiplier_aligned_np * avg_volume_aligned_np)

        if confirm_price_increase:
            price_increase_np = (close_series > close_series.shift(1)).values[:, np.newaxis]
            entries_np = volume_breakout_np & price_increase_np
        else:
            entries_np = volume_breakout_np

        # 4. Prepare arrays for broadcasting EXIT signals
        close_np = close_series.values[:, np.newaxis]

        # Create index map for exit MA windows
        exit_window_map = {e: i for i, e in enumerate(exit_ma_window_range)}
        # Get column indices corresponding to the exit_ma_window in each combination
        col_indices_exit = [exit_window_map[e] for w, m, e in param_product]
         # Select and order the exit_ma columns according to the final combination order
        exit_ma_aligned_np = exit_ma_df.values[:, col_indices_exit]

        # Calculate Exit condition: Close < Exit MA using broadcasting
        exits_np = close_np < exit_ma_aligned_np

        # 5. Create Final DataFrames
        entries_df = pd.DataFrame(entries_np, index=ohlcv_df.index, columns=column_index)
        entries_df = entries_df.fillna(False)

        exits_df = pd.DataFrame(exits_np, index=ohlcv_df.index, columns=column_index)
        exits_df = exits_df.fillna(False)

    except Exception as e:
        logger.error(f"Error during vectorized signal calculation: {e}")
        traceback.print_exc()
        raise

    logger.info(f"Volume Breakout/MA Exit signals generated. Shape: {entries_df.shape}")
    return entries_df, exits_df, None, None # No short signals