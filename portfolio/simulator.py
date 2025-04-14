# portfolio/simulator.py

import vectorbt as vbt
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, Union # Added Union

def run_backtest(
    price_df: pd.DataFrame,
    entries_series: Union[pd.Series, pd.DataFrame],           # Can be Series or DataFrame
    exits_series: Union[pd.Series, pd.DataFrame],             # Can be Series or DataFrame
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
    ) -> vbt.Portfolio:
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
    """
    if 'Close' not in price_df.columns:
        raise ValueError("Price DataFrame must contain a 'Close' column.")

    # --- NORMALIZE INDICES ---
    # Make sure index is DatetimeIndex and TZ-naive
    price_df_to_use = price_df.copy()
    price_df_to_use.index = pd.to_datetime(price_df_to_use.index)
    if price_df_to_use.index.tz is not None:
        price_df_to_use.index = price_df_to_use.index.tz_localize(None)

    def normalize_and_copy(signal_series):
        if signal_series is None:
            return None
        series_copy = signal_series.copy()
        series_copy.index = pd.to_datetime(series_copy.index)
        if series_copy.index.tz is not None:
            series_copy.index = series_copy.index.tz_localize(None)
        return series_copy

    entries_series_to_use = normalize_and_copy(entries_series)
    exits_series_to_use = normalize_and_copy(exits_series)
    short_entries_series_to_use = normalize_and_copy(short_entries_series) # Normalize short signals too
    short_exits_series_to_use = normalize_and_copy(short_exits_series)     # Normalize short signals too

    # --- REINDEX SIGNALS to align with price data ---
    target_index = price_df_to_use.index
    try:
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
        print(f"ERROR during signal reindexing: {e}")
        raise

    # --- Prepare kwargs for vbt.Portfolio.from_signals ---
    # Signal-related arguments (stops are applied to both long and short if enabled)
    final_signal_kwargs = {
        'sl_stop': sl_stop,
        'tp_stop': tp_stop,
    }
    if signal_kwargs:
        final_signal_kwargs.update(signal_kwargs)

    # Portfolio-related arguments
    final_portfolio_kwargs = {
        'size': size,
        'size_type': size_type,
        'fees': fees,
        'slippage': slippage,
        'freq': frequency,
        'init_cash': initial_capital,
    }
    if portfolio_kwargs:
        final_portfolio_kwargs.update(portfolio_kwargs)

    # print("Running vectorbt Portfolio.from_signals simulation...")
    try:
        # Use the processed price data and reindexed signals
        sim_price_df = price_df_to_use
        sim_open_col = sim_price_df['Open'] if 'Open' in sim_price_df.columns else sim_price_df['Close']
        sim_high_col = sim_price_df['High'] if 'High' in sim_price_df.columns else None
        sim_low_col = sim_price_df['Low'] if 'Low' in sim_price_df.columns else None

        # Call from_signals, passing the short signals if they exist
        portfolio = vbt.Portfolio.from_signals(
            close=sim_price_df['Close'],
            open=sim_open_col,
            high=sim_high_col,
            low=sim_low_col,
            entries=reindexed_entries,
            exits=reindexed_exits,
            short_entries=reindexed_short_entries, # Pass reindexed short entries
            short_exits=reindexed_short_exits,     # Pass reindexed short exits
            **final_signal_kwargs,
            **final_portfolio_kwargs
        )

        # print("Simulation complete.")
        return portfolio
    except Exception as e:
        if "'shares'" in str(e) and size_type == 'shares': # Example specific error check
             print("\n*** NOTE: Encountered known issue with size_type='shares'.")
             print("*** Consider using size_type='percent' or 'value', or investigate compatibility.\n")
        print(f"Error during vectorbt simulation: {e}")
        # Consider logging the traceback here for debugging
        # import traceback
        # traceback.print_exc()
        raise # Re-raise the exception after logging/printing