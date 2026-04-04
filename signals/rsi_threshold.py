# signals/rsi_threshold.py
import pandas as pd
import numpy as np
import traceback
import vectorbt as vbt
from typing import Optional, Union, Tuple, List, Dict # Added List, Dict
from utils.logging_utils import setup_logging
from utils.error_handling import handle_errors, BacktesterError # Import the decorator and any custom errors if needed

# Setup logger
logger = setup_logging(log_file="logs/backtester.log")

@handle_errors
def generate_rsi_signals(
    close_prices_series: pd.Series,
    window: np.ndarray,                 # Expect numpy array of RSI window periods
    entry_threshold: np.ndarray,        # Expect numpy array of LONG entry thresholds
    exit_threshold: np.ndarray,         # Expect numpy array of LONG exit thresholds
    enable_shorting: bool = False,      # Flag to enable shorting
    short_entry_threshold: Optional[np.ndarray] = None, # Optional SHORT entry thresholds
    short_exit_threshold: Optional[np.ndarray] = None   # Optional SHORT exit thresholds
    ) -> Tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    """
    Generates long and optionally short signals based on RSI crossing thresholds
    using vectorbt, iterating through thresholds but vectorizing across windows.

    Args:
        close_prices_series: pandas Series of close prices.
        window: 1D numpy array of RSI window periods.
        entry_threshold: 1D numpy array of RSI levels to trigger a LONG entry.
        exit_threshold: 1D numpy array of RSI levels to trigger a LONG exit.
        enable_shorting: If True, generate short entry/exit signals.
        short_entry_threshold: 1D numpy array of RSI levels for SHORT entry.
        short_exit_threshold: 1D numpy array of RSI levels for SHORT exit.

    Returns:
        A tuple containing four DataFrames, potentially with MultiIndex columns
        representing parameter combinations (e.g., ('rsi_window', 'entry_threshold')).
            - entries_df: Long entry signals (True).
            - exits_df: Long exit signals (True).
            - short_entries_df: Short entry signals (True) or None.
            - short_exits_df: Short exit signals (True) or None.
    """
    if not isinstance(close_prices_series, pd.Series):
        raise TypeError("Input 'close_prices_series' must be a pandas Series.")
    if close_prices_series.empty:
        logger.debug("Warning: Input 'close_prices_series' is empty.")
        empty_df = pd.DataFrame()
        return empty_df, empty_df, None, None

    # Ensure inputs are numpy arrays
    window = np.asarray(window)
    entry_threshold = np.asarray(entry_threshold)
    exit_threshold = np.asarray(exit_threshold)

    logger.info("Calculating RSI using vectorbt...")
    try:
        rsi = vbt.RSI.run(close_prices_series, window=window, short_name='rsi')
        rsi_values = rsi.rsi # DataFrame: Index=time, Columns=window values
        logger.info(f"RSI calculated. Shape: {rsi_values.shape}")
    except Exception as e:
        logger.error(f"Error calculating RSI with vectorbt: {e}")
        traceback.print_exc()
        raise

    # Strategy: vectorbt computes RSI for ALL windows at once (rsi_values is a DataFrame
    # with shape (num_bars, num_windows)). We then iterate over each threshold value and
    # use crossed_above/below to get a boolean DataFrame per threshold.
    # Final result is a MultiIndex DataFrame combining both dimensions (window x threshold).
    logger.info("Generating signals by iterating through thresholds...")
    entries_list: List[pd.DataFrame] = []
    exits_list: List[pd.DataFrame] = []
    short_entries_list: List[pd.DataFrame] = []
    short_exits_list: List[pd.DataFrame] = []

    # Store keys for final concatenation — each key corresponds to one threshold value.
    entry_keys: List[Tuple[float]] = []
    exit_keys: List[Tuple[float]] = []
    short_entry_keys: List[Tuple[float]] = []
    short_exit_keys: List[Tuple[float]] = []

    # Generate Long Signals
    logger.info(f" Processing {len(entry_threshold)} long entry thresholds...")
    for et in entry_threshold:
        try:
            # Compare all window columns against the current single entry threshold
            entries_for_thresh = rsi_values.vbt.crossed_above(et)
            entries_list.append(entries_for_thresh)
            entry_keys.append((et,)) # Tuple key for MultiIndex later
        except Exception as e:
            logger.error(f"Error processing entry threshold {et}: {e}")
            # Optional: Append empty DataFrame or handle error differently
            entries_list.append(pd.DataFrame(False, index=rsi_values.index, columns=rsi_values.columns))
            entry_keys.append((et,))

    logger.info(f" Processing {len(exit_threshold)} long exit thresholds...")
    for xt in exit_threshold:
         try:
             exits_for_thresh = rsi_values.vbt.crossed_below(xt)
             exits_list.append(exits_for_thresh)
             exit_keys.append((xt,))
         except Exception as e:
             logger.error(f"Error processing exit threshold {xt}: {e}")
             exits_list.append(pd.DataFrame(False, index=rsi_values.index, columns=rsi_values.columns))
             exit_keys.append((xt,))

    # Generate Short Signals (if enabled)
    if enable_shorting:
        if short_entry_threshold is None or short_exit_threshold is None:
            logger.debug("Warning: Shorting enabled but short entry or exit thresholds are None. Skipping short signals.")
            short_entries_df = None
            short_exits_df = None
        else:
            short_entry_threshold = np.asarray(short_entry_threshold)
            short_exit_threshold = np.asarray(short_exit_threshold)

            logger.info(f" Processing {len(short_entry_threshold)} short entry thresholds...")
            for set_ in short_entry_threshold:
                try:
                    short_entries_for_thresh = rsi_values.vbt.crossed_below(set_)
                    short_entries_list.append(short_entries_for_thresh)
                    short_entry_keys.append((set_,))
                except Exception as e:
                    logger.error(f"Error processing short entry threshold {set_}: {e}")
                    short_entries_list.append(pd.DataFrame(False, index=rsi_values.index, columns=rsi_values.columns))
                    short_entry_keys.append((set_,))

            logger.info(f" Processing {len(short_exit_threshold)} short exit thresholds...")
            for sxt in short_exit_threshold:
                try:
                    short_exits_for_thresh = rsi_values.vbt.crossed_above(sxt)
                    short_exits_list.append(short_exits_for_thresh)
                    short_exit_keys.append((sxt,))
                except Exception as e:
                    logger.error(f"Error processing short exit threshold {sxt}: {e}")
                    short_exits_list.append(pd.DataFrame(False, index=rsi_values.index, columns=rsi_values.columns))
                    short_exit_keys.append((sxt,))
    else:
        short_entries_df = None
        short_exits_df = None

    # --- Combine results into DataFrames with MultiIndex ---
    # After the loop, entries_list contains one DataFrame per threshold value.
    # Each DataFrame has columns = RSI windows. We concat them along axis=1 using
    # threshold values as a new outer key, producing a 2-level MultiIndex:
    #   (entry_threshold, rsi_window)
    # Then reorder_levels flips it to (rsi_window, entry_threshold) so both entries and
    # exits share the same outer level, which is required for vectorbt broadcasting.
    logger.info("Combining signal results...")
    try:
        # Combine Long Signals
        if not entries_list or not exits_list:
             raise ValueError("No valid long entry or exit signals were generated.")

        entries_df = pd.concat(entries_list, axis=1, keys=pd.MultiIndex.from_tuples(entry_keys, names=['entry_threshold']))
        entries_df = entries_df.reorder_levels(['rsi_window', 'entry_threshold'], axis=1)
        entries_df = entries_df.sort_index(axis=1)


        exits_df = pd.concat(exits_list, axis=1, keys=pd.MultiIndex.from_tuples(exit_keys, names=['exit_threshold']))
        exits_df = exits_df.reorder_levels(['rsi_window', 'exit_threshold'], axis=1)
        exits_df = exits_df.sort_index(axis=1)


        # Combine Short Signals (if generated)
        if enable_shorting and short_entries_list and short_exits_list:
            short_entries_df = pd.concat(short_entries_list, axis=1, keys=pd.MultiIndex.from_tuples(short_entry_keys, names=['short_entry_threshold']))
            short_entries_df = short_entries_df.reorder_levels(['rsi_window', 'short_entry_threshold'], axis=1)
            short_entries_df = short_entries_df.sort_index(axis=1)


            short_exits_df = pd.concat(short_exits_list, axis=1, keys=pd.MultiIndex.from_tuples(short_exit_keys, names=['short_exit_threshold']))
            short_exits_df = short_exits_df.reorder_levels(['rsi_window', 'short_exit_threshold'], axis=1)
            short_exits_df = short_exits_df.sort_index(axis=1)


        logger.info(f"Combined signals. Final shapes - Entries: {entries_df.shape}, Exits: {exits_df.shape}")
        if short_entries_df is not None: logger.info(f" Short Entries: {short_entries_df.shape}, Short Exits: {short_exits_df.shape}")

    except Exception as e:
        logger.error(f"Error combining signal DataFrames: {e}")
        traceback.print_exc()
        # Return empty DataFrames on error during combination
        empty_df = pd.DataFrame(index=close_prices_series.index)
        return empty_df, empty_df, None, None


    # Basic cleaning can be skipped or done here, but Portfolio simulation is often better place.
    logger.info("Signal generation complete (combination stage).")
    # The Portfolio simulation should handle aligning these separate signal DataFrames
    # based on the common 'rsi_window' level in their MultiIndex columns.
    return entries_df, exits_df, short_entries_df, short_exits_df