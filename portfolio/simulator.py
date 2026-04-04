# portfolio/simulator.py

import vectorbt as vbt
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, Union, TYPE_CHECKING # Added Union, TYPE_CHECKING
from utils.logging_utils import setup_logging
from utils.error_handling import handle_errors, BacktesterError # Import the decorator and any custom errors if needed

# Setup logger
logger = setup_logging(log_file="logs/backtester.log")

# Type hint for vbt.Portfolio only during type checking to avoid circular imports if needed
if TYPE_CHECKING:
    from vectorbt.portfolio.base import Portfolio as PortfolioBase
else:
    PortfolioBase = vbt.Portfolio # Fallback for runtime


@handle_errors # Apply the decorator
def run_backtest(
    price_df: pd.DataFrame,
    entries_series: Union[pd.Series, pd.DataFrame],          # Can be Series or DataFrame
    exits_series: Union[pd.Series, pd.DataFrame],            # Can be Series or DataFrame
    frequency: str,
    initial_capital: float = 100000.0,
    fees: float = 0.001,
    slippage: float = 0.0005,
    size : Optional[float] = None,
    size_type: str = 'percent',
    sl_stop : Optional[float] = None,
    tp_stop : Optional[float] = None,
    short_entries_series: Optional[Union[pd.Series, pd.DataFrame]] = None, # New optional arg
    short_exits_series: Optional[Union[pd.Series, pd.DataFrame]] = None,   # New optional arg
    signal_kwargs: Optional[Dict[str, Any]] = None,
    portfolio_kwargs: Optional[Dict[str, Any]] = None
    ) -> PortfolioBase: # Use the type alias
    """
    Runs a vectorbt backtest simulation based on entry/exit signals (long and optionally short).
    Handles index normalization and uses reindex for robust signal alignment.

    Args:
        price_df: DataFrame with OHLCV data. Must include 'Close'.
        entries_series: Series/DataFrame of long entry signals.
        exits_series: Series/DataFrame of long exit signals.
        frequency: Frequency string for simulation (e.g., 'D', 'H').
        initial_capital: Starting cash.
        fees: Fee percentage per trade.
        slippage: Slippage percentage per trade.
        size: Position size. Interpretation depends on size_type. Can be None.
        size_type: How 'size' is interpreted ('percent', 'amount', 'value').
        sl_stop: Stop loss percentage (e.g., 0.05 for 5%). Applied to long and short.
        tp_stop: Take profit percentage (e.g., 0.10 for 10%). Applied to long and short.
        short_entries_series: Optional Series/DataFrame of short entry signals.
        short_exits_series: Optional Series/DataFrame of short exit signals.
        signal_kwargs: Additional kwargs passed directly to from_signals (signal part).
        portfolio_kwargs: Additional kwargs passed directly to from_signals (portfolio part).

    Returns:
        A vectorbt Portfolio object.

    Raises:
        ValueError: If price_df is missing 'Close' column.
        BacktesterError: For specific backtesting related issues (if defined and raised).
        Exception: For any other unexpected errors during simulation (logged and re-raised by decorator).
    """
    logger.info("Starting backtest simulation...")
    if 'Close' not in price_df.columns:
        # Raise specific error before decorator catches it
        logger.error("Price DataFrame must contain a 'Close' column.")
        raise ValueError("Price DataFrame must contain a 'Close' column.")

    # --- NORMALIZE INDICES ---
    # vectorbt requires TZ-naive DatetimeIndex on both price data and signals.
    # Yahoo Finance returns tz-aware timestamps (America/New_York for intraday),
    # which causes alignment errors if not stripped. tz_localize(None) removes the
    # timezone without converting the time values.
    try:
        price_df_to_use = price_df.copy()
        if not isinstance(price_df_to_use.index, pd.DatetimeIndex):
             price_df_to_use.index = pd.to_datetime(price_df_to_use.index)
        if price_df_to_use.index.tz is not None:
             logger.debug("Localizing price index to TZ-naive.")
             price_df_to_use.index = price_df_to_use.index.tz_localize(None)
    except Exception as e:
        logger.error(f"Failed to normalize price data index: {e}")
        raise # Re-raise for decorator to catch

    def normalize_and_copy(signal_series, name="signal"):
        if signal_series is None:
            return None
        try:
            series_copy = signal_series.copy()
            if not isinstance(series_copy.index, pd.DatetimeIndex):
                series_copy.index = pd.to_datetime(series_copy.index)
            if series_copy.index.tz is not None:
                logger.debug(f"Localizing {name} index to TZ-naive.")
                series_copy.index = series_copy.index.tz_localize(None)
            return series_copy
        except Exception as e:
            logger.error(f"Failed to normalize {name} index: {e}")
            raise # Re-raise for decorator to catch

    logger.debug("Normalizing signal indices...")
    entries_series_to_use = normalize_and_copy(entries_series, "long entries")
    exits_series_to_use = normalize_and_copy(exits_series, "long exits")
    short_entries_series_to_use = normalize_and_copy(short_entries_series, "short entries")
    short_exits_series_to_use = normalize_and_copy(short_exits_series, "short exits")

    # --- REINDEX SIGNALS to align with price data ---
    # Signal DataFrames are generated from indicator calculations and may have a slightly
    # different index than the price data (e.g., NaN rows dropped by the cleaner, or
    # extra dates added during indicator warmup). reindex() aligns them to the exact
    # price index, filling any gaps with False so no phantom signals are introduced.
    target_index = price_df_to_use.index
    logger.debug("Reindexing signals to price index...")
    try:
        if entries_series_to_use is None:
             logger.error("Long entry signals are None, cannot proceed.")
             raise ValueError("Long entry signals cannot be None.")
        if exits_series_to_use is None:
             logger.error("Long exit signals are None, cannot proceed.")
             raise ValueError("Long exit signals cannot be None.")

        reindexed_entries = entries_series_to_use.reindex(target_index, fill_value=False).astype(bool)
        reindexed_exits = exits_series_to_use.reindex(target_index, fill_value=False).astype(bool)

        # Reindex short signals if they exist
        reindexed_short_entries = None
        if short_entries_series_to_use is not None:
            reindexed_short_entries = short_entries_series_to_use.reindex(target_index, fill_value=False).astype(bool)

        reindexed_short_exits = None
        if short_exits_series_to_use is not None:
            reindexed_short_exits = short_exits_series_to_use.reindex(target_index, fill_value=False).astype(bool)

    except Exception as e:
        logger.error(f"ERROR during signal reindexing: {e}")
        raise # Re-raise for decorator

    # --- Prepare kwargs for vbt.Portfolio.from_signals ---
    logger.debug("Preparing simulation parameters...")
    # Signal-related arguments (stops are applied to both long and short if enabled)
    final_signal_kwargs = {
        'sl_stop': sl_stop,
        'tp_stop': tp_stop,
        # Add other signal-related defaults if necessary
    }
    if signal_kwargs:
        final_signal_kwargs.update(signal_kwargs)
    logger.debug(f"Final signal kwargs: {final_signal_kwargs}")

    # Portfolio-related arguments
    final_portfolio_kwargs = {
        'size': size,
        'size_type': size_type,
        'fees': fees,
        'slippage': slippage,
        'freq': frequency,
        'init_cash': initial_capital,
        # Add other portfolio-related defaults if necessary
    }
    if portfolio_kwargs:
        final_portfolio_kwargs.update(portfolio_kwargs)
    logger.debug(f"Final portfolio kwargs: {final_portfolio_kwargs}")


    logger.info("Running vectorbt Portfolio.from_signals simulation...")
    try:
        # Use the processed price data and reindexed signals
        sim_price_df = price_df_to_use
        # Determine Open, High, Low, handling missing columns gracefully
        sim_open_col = sim_price_df['Open'] if 'Open' in sim_price_df.columns else sim_price_df['Close']
        sim_high_col = sim_price_df['High'] if 'High' in sim_price_df.columns else None
        sim_low_col = sim_price_df['Low'] if 'Low' in sim_price_df.columns else None

        if sim_high_col is None:
             logger.warning("Missing 'High' column, using 'Close' for high.")
             sim_high_col = sim_price_df['Close']
        if sim_low_col is None:
             logger.warning("Missing 'Low' column, using 'Close' for low.")
             sim_low_col = sim_price_df['Close']


        # Call from_signals, passing the short signals if they exist
        portfolio = vbt.Portfolio.from_signals(
            close=sim_price_df['Close'],
            open=sim_open_col,
            high=sim_high_col, # Pass determined high
            low=sim_low_col,   # Pass determined low
            entries=reindexed_entries,
            exits=reindexed_exits,
            short_entries=reindexed_short_entries, # Pass reindexed short entries
            short_exits=reindexed_short_exits,     # Pass reindexed short exits
            **final_signal_kwargs,
            **final_portfolio_kwargs
        )

        logger.info("Simulation complete.")
        return portfolio
    except Exception as e:
        # Specific checks can remain here for detailed logging before re-raising
        if "'shares'" in str(e).lower() and size_type == 'shares':
             logger.info("\n*** NOTE: Encountered potential known issue with size_type='shares'.")
             logger.info("*** Consider using size_type='percent' or 'value', or check vectorbt documentation for compatibility.\n")
        # Log the error here; decorator will log again and re-raise
        logger.error(f"Error during vectorbt simulation execution: {e}")
        # import traceback # Optional: uncomment for detailed traceback here
        # traceback.print_exc()
        raise # Re-raise the exception for the decorator to handle

