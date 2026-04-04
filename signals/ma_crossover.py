# filename: HealysBacktester/signals/ma_crossover.py

import pandas as pd
import numpy as np
import vectorbt as vbt
import warnings
from utils.logging_utils import setup_logging
from utils.error_handling import handle_errors, BacktesterError # Import the decorator and any custom errors if needed

# Setup logger
logger = setup_logging(log_file="logs/backtester.log")

@handle_errors
def generate_ma_signals(
    close_prices_series: pd.Series,
    windows_range: np.ndarray, # Expect a single 1D numpy array defining the range, e.g., np.arange(2, 101)
    # ma_type: str = 'SMA' # Optional: Add parameter for different MA types if needed
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generates entry and exit signal DataFrames based on MA crossover
    using vectorbt's run_combs for efficiency with large parameter spaces.

    Args:
        close_prices_series: pandas Series of close prices.
        windows_range: 1D numpy array defining the range of window lengths
                       from which fast and slow combinations will be generated.

    Returns:
        A tuple containing two boolean DataFrames:
            - entries: Entry signals (True). Columns are MultiIndex ('fast_window', 'slow_window').
            - exits: Exit signals (True). Columns are MultiIndex ('fast_window', 'slow_window').

    Raises:
        ValueError: If windows_range is empty or too small to form pairs.
        TypeError: If the input series is not a pandas Series.
    """
    if not isinstance(close_prices_series, pd.Series):
        raise TypeError("Input 'close_prices_series' must be a pandas Series.")
    if not isinstance(windows_range, np.ndarray):
        windows_range = np.array(windows_range)
    if windows_range.ndim != 1 or windows_range.size < 2:
        raise ValueError("Input 'windows_range' must be a 1D numpy array with at least 2 elements.")

    logger.info(f"Calculating MA combinations for windows ranging from {windows_range.min()} to {windows_range.max()}...")

    # vbt.MA.run_combs generates all unique pairs (r=2) from windows_range where fast < slow.
    # For windows_range = np.arange(2, 143), this produces C(141, 2) = 9,870 combinations.
    # It returns two aligned indicator objects: fast_ma_obj (smaller window) and slow_ma_obj (larger window).
    # This is far more efficient than looping — vectorbt computes all MAs in one pass.
    try:
        fast_ma_obj, slow_ma_obj = vbt.MA.run_combs(
            close_prices_series,
            window=windows_range,
            r=2,
            short_names=['fast', 'slow']
        )
        # fast_ma_obj and slow_ma_obj are vectorbt indicator objects.

    except Exception as e:
        logger.error(f"Error calculating MA combinations using vectorbt: {e}")
        raise

    # Access the calculated MA DataFrames using the .ma attribute
    fast_ma_values = fast_ma_obj.ma
    slow_ma_values = slow_ma_obj.ma

    # Check if the MA calculation resulted in valid DataFrames
    if not isinstance(fast_ma_values, pd.DataFrame) or not isinstance(slow_ma_values, pd.DataFrame):
        raise TypeError(f"MA calculation did not produce DataFrames (got {type(fast_ma_values)}, {type(slow_ma_values)})")


    # .vbt.crossed_above/below are vectorbt's vectorized crossover detectors.
    # They compare element-wise across all combinations simultaneously — no loops needed.
    # Result shape: (num_bars, num_combinations), dtype=bool.
    # MultiIndex columns: (fast_window, slow_window) for each combination.
    logger.info(f"Generating crossover signals...")
    try:
        entries = fast_ma_values.vbt.crossed_above(slow_ma_values)
        exits = fast_ma_values.vbt.crossed_below(slow_ma_values)
    except Exception as e:
        logger.info(f"Error generating crossover signals: {e}")
        # You might want to inspect fast_ma_values and slow_ma_values here if errors persist
        logger.info("Fast MA Values Head:\n", fast_ma_values.head())
        logger.info("Slow MA Values Head:\n", slow_ma_values.head())
        raise


    # Basic check on the actual signal DataFrame output
    if entries is None or exits is None:
         raise TypeError("Signal generation failed, entries or exits are None.")

    if entries.empty or exits.empty:
        if close_prices_series.empty:
             warnings.warn("Input price series is empty, resulting signal DataFrames are empty.")
        else:
             warnings.warn("Signal generation resulted in empty DataFrames, although price data exists. No crossovers occurred?")
        return entries, exits


    if not isinstance(entries, pd.DataFrame) or not isinstance(exits, pd.DataFrame):
        raise TypeError(f"Signal generation did not produce DataFrames (got {type(entries)}, {type(exits)})")
    if not isinstance(entries.columns, pd.MultiIndex) or not isinstance(exits.columns, pd.MultiIndex):
         warnings.warn("Signal output columns are not MultiIndex as expected.")


    # Print the number of combinations based on the shape of the resulting 'entries' DataFrame
    logger.info(f"MA Crossover signals generated successfully for {entries.shape[1]} combinations.")
    return entries, exits