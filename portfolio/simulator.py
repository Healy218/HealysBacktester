# portfolio/simulator.py

import vectorbt as vbt
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any

def run_backtest(
    price_df: pd.DataFrame,
    entries_series: pd.Series,
    exits_series: pd.Series,
    frequency: str,
    initial_capital: float = 100000.0,
    fees: float = 0.001,
    slippage: float = 0.0005,
    size: float = 0.99, # Default back to 0.99 or your preferred default
    size_type: str = 'percent',
    sl_stop: Optional[float] = None,
    tp_stop: Optional[float] = None,
    signal_kwargs: Optional[Dict[str, Any]] = None,
    portfolio_kwargs: Optional[Dict[str, Any]] = None
    ) -> vbt.Portfolio:
    """
    Runs a vectorbt backtest simulation based on entry and exit signals.
    Handles index normalization and uses reindex for robust signal alignment.

    (Keep your original detailed Args/Returns/Raises docstring here)
    """
    if 'Close' not in price_df.columns:
        raise ValueError("Price DataFrame must contain a 'Close' column.")

    # --- NORMALIZE INDICES ---
    # print("\n--- Normalizing indices (removing time component) ---") # Optional: Keep if you want this message
    try:
        price_df_normalized = price_df.copy()
        price_df_normalized.index = price_df_normalized.index.normalize()

        entries_series_normalized = entries_series.copy()
        entries_series_normalized.index = entries_series_normalized.index.normalize()

        exits_series_normalized = exits_series.copy()
        exits_series_normalized.index = exits_series_normalized.index.normalize()
        # print("Normalization complete.") # Optional: Keep if you want this message

        price_df_to_use = price_df_normalized
        entries_series_to_use = entries_series_normalized
        exits_series_to_use = exits_series_normalized
    except Exception as e:
        print(f"WARNING: Index normalization failed: {e}. Using original indices.")
        price_df_to_use = price_df
        entries_series_to_use = entries_series
        exits_series_to_use = exits_series

    # --- REINDEX SIGNALS ---
    target_index = price_df_to_use.index
    # print(f"Reindexing signals to target index (Length: {len(target_index)}, dtype: {target_index.dtype})...") # Optional: Keep if you want this message
    try:
        reindexed_entries = entries_series_to_use.reindex(target_index, fill_value=False).astype(bool)
        reindexed_exits = exits_series_to_use.reindex(target_index, fill_value=False).astype(bool)
        # print("Reindexing complete.") # Optional: Keep if you want this message
    except Exception as e:
        print(f"ERROR during reindexing: {e}")
        raise

    # --- Prepare kwargs for vbt.Portfolio.from_signals ---
    # Signal-related arguments (stops)
    final_signal_kwargs = {
        'sl_stop': sl_stop,
        'tp_stop': tp_stop,
    }
    if signal_kwargs:
        final_signal_kwargs.update(signal_kwargs) # Allow user overrides/additions

    # Portfolio-related arguments (sizing, costs, etc.)
    final_portfolio_kwargs = {
        'size': size,               # Use function arg/default
        'size_type': size_type,     # Use function arg/default
        'fees': fees,               # Use function arg/default
        'slippage': slippage,         # Use function arg/default
        'freq': frequency,
        'init_cash': initial_capital,
        # Add any other standard params you want to control via run_backtest args
    }
    if portfolio_kwargs:
        # Allow user overrides/additions for any other portfolio param
        final_portfolio_kwargs.update(portfolio_kwargs)

    print("Running vectorbt Portfolio.from_signals simulation...")
    try:
        # Use the normalized price data and reindexed signals
        sim_price_df = price_df_to_use
        sim_open_col = sim_price_df['Open'] if 'Open' in sim_price_df.columns else sim_price_df['Close']
        sim_high_col = sim_price_df['High'] if 'High' in sim_price_df.columns else None
        sim_low_col = sim_price_df['Low'] if 'Low' in sim_price_df.columns else None

        portfolio = vbt.Portfolio.from_signals(
            close=sim_price_df['Close'],
            open=sim_open_col,
            high=sim_high_col,
            low=sim_low_col,
            entries=reindexed_entries,    # Use reindexed
            exits=reindexed_exits,        # Use reindexed
            **final_signal_kwargs,      # Unpack signal kwargs
            **final_portfolio_kwargs    # Unpack portfolio kwargs
        )

        print("Simulation complete.")
        return portfolio
    except Exception as e:
        # Check specifically for the 'shares' error if it occurs again
        if "'shares'" in str(e):
             print("\n*** NOTE: Encountered known issue with size_type='shares'.")
             print("*** Consider using size_type='percent' or 'value', or investigate compatibility with your vectorbt version.\n")
        print(f"Error during vectorbt simulation: {e}")
        raise # Re-raise the exception