# signals/rsi_threshold.py
import pandas as pd
import numpy as np
import traceback
import vectorbt as vbt
from indicators import rsi # Assuming this correctly calculates RSI
from itertools import product # For generating combinations
from typing import Optional, Union # Add Optional here (and Union if used elsewhere)


def generate_rsi_signals(
    close_prices_series: pd.Series,
    window: np.ndarray,                 # Expect numpy array of long windows
    entry_threshold: np.ndarray,        # Expect numpy array of long entry thresholds
    exit_threshold: np.ndarray,         # Expect numpy array of long exit thresholds
    enable_shorting: bool = False,      # Flag to enable shorting
    short_entry_threshold: Optional[np.ndarray] = None, # Optional short entry thresholds
    short_exit_threshold: Optional[np.ndarray] = None   # Optional short exit thresholds
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]: # Return 4 DataFrames
    """
    Generates long and optionally short signals based on RSI crossing thresholds
    for MULTIPLE parameter combinations.

    Args:
        close_prices_series: pandas Series of close prices.
        window: 1D numpy array of RSI window periods.
        entry_threshold: 1D numpy array of RSI levels to trigger a LONG entry upon crossing above.
        exit_threshold: 1D numpy array of RSI levels to trigger a LONG exit upon crossing below.
        enable_shorting: If True, generate short entry/exit signals.
        short_entry_threshold: 1D numpy array of RSI levels to trigger a SHORT entry upon crossing below.
                               Defaults to exit_threshold if None and enable_shorting is True.
        short_exit_threshold: 1D numpy array of RSI levels to trigger a SHORT exit upon crossing above.
                              Defaults to entry_threshold if None and enable_shorting is True.

    Returns:
        A tuple containing four DataFrames:
            - long_entries_df: Columns are MultiIndex named ('window', 'entry_thresh', 'exit_thresh').
            - long_exits_df: Columns are MultiIndex named ('window', 'entry_thresh', 'exit_thresh').
            - short_entries_df: Columns are MultiIndex named ('window', 'entry_thresh', 'exit_thresh'). (All False if shorting disabled)
            - short_exits_df: Columns are MultiIndex named ('window', 'entry_thresh', 'exit_thresh'). (All False if shorting disabled)
    """
    # Ensure inputs are numpy arrays
    if not isinstance(window, np.ndarray): window = np.array(window)
    if not isinstance(entry_threshold, np.ndarray): entry_threshold = np.array(entry_threshold)
    if not isinstance(exit_threshold, np.ndarray): exit_threshold = np.array(exit_threshold)

    # Default short thresholds if enabling shorting and they aren't provided
    if enable_shorting:
        if short_entry_threshold is None:
            print("Warning: short_entry_threshold not provided for shorting, using exit_threshold.")
            short_entry_threshold = exit_threshold
        if short_exit_threshold is None:
            print("Warning: short_exit_threshold not provided for shorting, using entry_threshold.")
            short_exit_threshold = entry_threshold
        # Ensure short thresholds are numpy arrays
        if not isinstance(short_entry_threshold, np.ndarray): short_entry_threshold = np.array(short_entry_threshold)
        if not isinstance(short_exit_threshold, np.ndarray): short_exit_threshold = np.array(short_exit_threshold)
        # Basic validation
        if len(short_entry_threshold) != len(entry_threshold) or len(short_exit_threshold) != len(entry_threshold):
             print("Warning: Short threshold array lengths don't match long entry threshold array length. Broadcasting might be unpredictable.")


    # 1. Calculate RSI for all windows first
    print("Calculating RSI for all windows...")
    try:
        rsi_df = rsi.calculate_rsi(close_prices_series, window=window)
        if not isinstance(rsi_df, pd.DataFrame) or list(rsi_df.columns) != list(window):
             print("Warning: indicators.rsi.calculate_rsi did not return DataFrame with expected window columns.")
             if len(rsi_df.columns) == len(window):
                 rsi_df.columns = window
             else:
                 raise ValueError("Mismatch between number of windows and columns in RSI DataFrame.")
        print(f"RSI calculated. Shape: {rsi_df.shape}")
    except Exception as e:
        print(f"Error calculating RSI: {e}")
        raise

    long_entries_dict = {}
    long_exits_dict = {}
    short_entries_dict = {}
    short_exits_dict = {}

    # 2. Iterate through parameter combinations
    print("Generating signals for parameter combinations...")
    # Use product to create all combinations, including short thresholds if enabled
    if enable_shorting:
         param_combinations = list(product(window, entry_threshold, exit_threshold, short_entry_threshold, short_exit_threshold))
         print(f"Generating long & short signals for {len(param_combinations)} combinations.")
    else:
         # Only generate long combinations if shorting is disabled
         param_combinations = list(product(window, entry_threshold, exit_threshold))
         print(f"Generating long-only signals for {len(param_combinations)} combinations.")


    for i, params in enumerate(param_combinations):
        # Unpack parameters based on whether shorting is enabled
        if enable_shorting:
            w, long_entry_thresh, long_exit_thresh, short_entry_thresh, short_exit_thresh = params
        else:
            w, long_entry_thresh, long_exit_thresh = params
            # Define dummy short thresholds if needed later, though they won't be used
            short_entry_thresh, short_exit_thresh = np.nan, np.nan

        # Use a consistent key tuple based on long parameters for structure
        combo_key = (w, long_entry_thresh, long_exit_thresh)

        # Optional: print progress
        # if (i + 1) % 10 == 0: print(f"  Processed combo {i+1}/{len(param_combinations)}")

        try:
             if w not in rsi_df.columns:
                 print(f"Error: Window {w} not found in pre-calculated RSI columns. Skipping combo {combo_key}")
                 continue
             current_rsi_series = rsi_df[w]

             # --- Generate Long Signals ---
             long_entries_col = current_rsi_series.vbt.crossed_above(long_entry_thresh)
             long_exits_col = current_rsi_series.vbt.crossed_below(long_exit_thresh)

             # Store long results
             long_entries_dict[combo_key] = long_entries_col
             long_exits_dict[combo_key] = long_exits_col

             # --- Generate Short Signals (if enabled) ---
             if enable_shorting:
                 short_entries_col = current_rsi_series.vbt.crossed_below(short_entry_thresh) # Below upper threshold
                 short_exits_col = current_rsi_series.vbt.crossed_above(short_exit_thresh)   # Above lower threshold
                 short_entries_dict[combo_key] = short_entries_col
                 short_exits_dict[combo_key] = short_exits_col
             else:
                 # Store dummy False signals if shorting disabled, to maintain structure
                 short_entries_dict[combo_key] = pd.Series(False, index=current_rsi_series.index)
                 short_exits_dict[combo_key] = pd.Series(False, index=current_rsi_series.index)

        except Exception as e:
            print(f"Error processing combination {combo_key}: {e}")
            # Handle errors, e.g., by adding placeholder columns
            placeholder = pd.Series(False, index=close_prices_series.index)
            long_entries_dict[combo_key] = placeholder
            long_exits_dict[combo_key] = placeholder
            short_entries_dict[combo_key] = placeholder
            short_exits_dict[combo_key] = placeholder


    # 3. Combine results into DataFrames
    print("Combining signal results...")
    if not long_entries_dict: # Check if any combos were processed
         print("Error: No signal combinations were successfully processed.")
         empty_df = pd.DataFrame(index=close_prices_series.index)
         # Return None for all short signals if long signals failed
         return empty_df, empty_df, None, None

    try:
        # Always combine long signals
        long_entries_df = pd.concat(long_entries_dict, axis=1)
        long_exits_df = pd.concat(long_exits_dict, axis=1)
        index_names = ['window', 'entry_thresh', 'exit_thresh']
        long_entries_df.columns.names = index_names
        long_exits_df.columns.names = index_names

        # Initialize short signals to None
        short_entries_df = None
        short_exits_df = None

        # Only combine short signals if shorting was enabled AND signals were generated
        if enable_shorting and short_entries_dict: # Check short_entries_dict specifically
            try:
                short_entries_df = pd.concat(short_entries_dict, axis=1)
                short_exits_df = pd.concat(short_exits_dict, axis=1)
                short_entries_df.columns.names = index_names
                short_exits_df.columns.names = index_names
            except Exception as concat_err:
                print(f"Warning: Error concatenating short signals, setting to None: {concat_err}")
                short_entries_df = None
                short_exits_df = None
        # --- Add Signal Cleaning Logic ---
        # Apply cleaning only if signals exist (especially short ones)
        print("Cleaning signals to prevent conflicts...")
        if short_entries_df is not None:
             short_entries_df = short_entries_df & ~long_entries_df
        if short_exits_df is not None:
             short_exits_df = short_exits_df & ~long_exits_df
        # Clean long signals relative to each other
        long_exits_df = long_exits_df & ~long_entries_df
        # Clean short signals relative to each other (only if they exist)
        if short_entries_df is not None and short_exits_df is not None:
             short_exits_df = short_exits_df & ~short_entries_df
        print("Signal cleaning complete.")

        print("Signal combination complete.")
        # Return long signals, and short signals (which will be None if shorting disabled)
        return long_entries_df, long_exits_df, short_entries_df, short_exits_df

    except Exception as e:
         print(f"Error combining or cleaning signal results: {e}")
         traceback.print_exc() # Print full traceback
         empty_df = pd.DataFrame(index=close_prices_series.index)
         # Return None for shorts on error
         return empty_df, empty_df, None, None