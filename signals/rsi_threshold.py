# signals/rsi_threshold.py
import pandas as pd
import numpy as np
import traceback
import vectorbt as vbt
from typing import Optional, Union, Tuple, List, Dict
from utils.logging_utils import setup_logging
from utils.error_handling import handle_errors, BacktesterError

# Setup logger
logger = setup_logging(log_file="logs/backtester.log")

@handle_errors
def generate_rsi_signals(
    close_prices_series: pd.Series,
    window: np.ndarray,                 # Expect numpy array of RSI window periods
    entry_threshold: np.ndarray,        # Expect numpy array of LONG entry thresholds
    exit_threshold: np.ndarray,         # Expect numpy array of LONG exit thresholds
    enable_shorting: bool = False,      # Flag to enable shorting
    short_entry_threshold: Optional[np.ndarray] = None, # Unused — see note below
    short_exit_threshold: Optional[np.ndarray] = None   # Unused — see note below
    ) -> Tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    """
    Generates long and optionally short signals based on RSI crossing thresholds.

    Produces a TRUE cross-product of (window × entry_threshold × exit_threshold)
    combinations so that every entry/exit threshold pair is tested for every window.
    Column structure of all returned DataFrames:
        MultiIndex: (entry_threshold, exit_threshold, rsi_window)
    This ensures entries and exits share identical columns, which vectorbt requires
    for the parameter sweep to broadcast correctly.

    NOTE: short_entry_threshold / short_exit_threshold are accepted for API
    compatibility but are intentionally unused.  Short signals are derived from
    the same threshold arrays as longs (symmetric structure) so that all four
    DataFrames share identical column shapes:
        short_entries: RSI crosses BELOW exit_threshold  (overbought → open short)
        short_exits:   RSI crosses ABOVE entry_threshold (oversold  → cover short)
    The trend filter in the simulator provides genuine long/short diversity by
    gating long entries to bullish bars and short entries to bearish bars.

    Args:
        close_prices_series: pandas Series of close prices.
        window: 1D numpy array of RSI window periods.
        entry_threshold: 1D numpy array of RSI levels to trigger a LONG entry.
        exit_threshold: 1D numpy array of RSI levels to trigger a LONG exit.
        enable_shorting: If True, generate short entry/exit signals.
        short_entry_threshold: Ignored (kept for API compatibility).
        short_exit_threshold: Ignored (kept for API compatibility).

    Returns:
        Tuple of (entries_df, exits_df, short_entries_df, short_exits_df).
        All DataFrames have MultiIndex columns: (entry_threshold, exit_threshold, rsi_window).
        short_entries_df and short_exits_df are None when enable_shorting=False.
    """
    if not isinstance(close_prices_series, pd.Series):
        raise TypeError("Input 'close_prices_series' must be a pandas Series.")
    if close_prices_series.empty:
        logger.debug("Warning: Input 'close_prices_series' is empty.")
        empty_df = pd.DataFrame()
        return empty_df, empty_df, None, None

    window = np.asarray(window)
    entry_threshold = np.asarray(entry_threshold)
    exit_threshold = np.asarray(exit_threshold)

    logger.info("Calculating RSI using vectorbt...")
    try:
        rsi = vbt.RSI.run(close_prices_series, window=window, short_name='rsi')
        rsi_values = rsi.rsi  # DataFrame: rows=time, cols=window values
        logger.info(f"RSI calculated. Shape: {rsi_values.shape}")
    except Exception as e:
        logger.error(f"Error calculating RSI with vectorbt: {e}")
        traceback.print_exc()
        raise

    # --- Pre-compute per-threshold signals (vectorized over all windows at once) ---
    # For each entry threshold, crossed_above returns a bool DataFrame with one column
    # per window — computed in one vectorbt call rather than looping over windows.
    logger.info(
        f"Pre-computing signals: {len(entry_threshold)} entry × "
        f"{len(exit_threshold)} exit × {len(window)} windows = "
        f"{len(entry_threshold) * len(exit_threshold) * len(window):,} combinations"
    )

    entry_signals: Dict[float, pd.DataFrame] = {}
    exit_signals:  Dict[float, pd.DataFrame] = {}

    for et in entry_threshold:
        entry_signals[float(et)] = rsi_values.vbt.crossed_above(et)

    for xt in exit_threshold:
        exit_signals[float(xt)] = rsi_values.vbt.crossed_below(xt)

    # --- Build cross-product: every (entry_threshold, exit_threshold) pair ---
    # For each pair, the inner columns are the RSI windows, so after concat the
    # MultiIndex is (entry_threshold, exit_threshold, rsi_window).
    # Both entries_df and exits_df use the same outer key structure → identical columns.
    logger.info("Building cross-product signal DataFrames...")
    try:
        entries_pieces: List[pd.DataFrame] = []
        exits_pieces:   List[pd.DataFrame] = []
        keys: List[Tuple[float, float]] = []

        for et in entry_threshold:
            for xt in exit_threshold:
                entries_pieces.append(entry_signals[float(et)])
                exits_pieces.append(exit_signals[float(xt)])
                keys.append((float(et), float(xt)))

        mi = pd.MultiIndex.from_tuples(keys, names=['entry_threshold', 'exit_threshold'])

        entries_df = pd.concat(entries_pieces, axis=1, keys=mi)
        exits_df   = pd.concat(exits_pieces,   axis=1, keys=mi)

        # Ensure level names are correct after concat
        entries_df.columns.names = ['entry_threshold', 'exit_threshold', 'rsi_window']
        exits_df.columns.names   = ['entry_threshold', 'exit_threshold', 'rsi_window']

        logger.info(f"Combined signals. Entries shape: {entries_df.shape}, Exits shape: {exits_df.shape}")

        # --- Short signals (symmetric structure, same column MultiIndex) ---
        short_entries_df = None
        short_exits_df   = None

        if enable_shorting:
            short_entries_pieces: List[pd.DataFrame] = []
            short_exits_pieces:   List[pd.DataFrame] = []

            for et in entry_threshold:
                for xt in exit_threshold:
                    # short entry: RSI crosses BELOW exit_threshold (overbought)
                    short_entries_pieces.append(exit_signals[float(xt)])
                    # short exit:  RSI crosses ABOVE entry_threshold (oversold)
                    short_exits_pieces.append(entry_signals[float(et)])

            short_entries_df = pd.concat(short_entries_pieces, axis=1, keys=mi)
            short_exits_df   = pd.concat(short_exits_pieces,   axis=1, keys=mi)
            short_entries_df.columns.names = ['entry_threshold', 'exit_threshold', 'rsi_window']
            short_exits_df.columns.names   = ['entry_threshold', 'exit_threshold', 'rsi_window']
            logger.info(f"Short signals. Shape: {short_entries_df.shape}")

    except Exception as e:
        logger.error(f"Error building cross-product signal DataFrames: {e}")
        traceback.print_exc()
        empty_df = pd.DataFrame(index=close_prices_series.index)
        return empty_df, empty_df, None, None

    logger.info("RSI signal generation complete.")
    return entries_df, exits_df, short_entries_df, short_exits_df
