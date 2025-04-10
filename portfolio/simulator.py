# portfolio/simulator.py

import vectorbt as vbt
import pandas as pd
import numpy as np # Keep numpy import
from typing import Optional, Dict, Any

def run_backtest(
    price_df: pd.DataFrame,
    entries_series: pd.Series,
    exits_series: pd.Series,
    frequency: str,
    initial_capital: float = 100000.0,
    fees: float = 0.001,
    slippage: float = 0.0005,
    size: float = 1.0, # <--- REVERTED: Use 1.0 (interpreted based on size_type)
    size_type: str = 'percent', # <--- REVERTED: Use 'percent' (of equity)
    sl_stop: Optional[float] = None,
    tp_stop: Optional[float] = None,
    signal_kwargs: Optional[Dict[str, Any]] = None,
    portfolio_kwargs: Optional[Dict[str, Any]] = None
    ) -> vbt.Portfolio:
    """
    Runs a vectorbt backtest simulation based on entry and exit signals.

    Args:
        price_df: DataFrame with OHLCV data. Must include 'Close'.
                  'Open' is recommended for more realistic execution.
        entries_series: Boolean Series indicating entry signals (True).
        exits_series: Boolean Series indicating exit signals (True).
        frequency: Data frequency string (e.g., 'D', 'H', '5T'). Crucial for stats.
        initial_capital: Starting cash for the portfolio.
        fees: Proportional fees applied to each trade value.
        slippage: Proportional slippage applied to the execution price.
        size: Order size. Interpretation depends on size_type. Default 1.0.
        size_type: How the 'size' argument is interpreted (string). Default 'percent'.
        sl_stop: Optional stop loss percentage (e.g., 0.10 for 10%).
        tp_stop: Optional take profit percentage (e.g., 0.20 for 20%).
        signal_kwargs: Optional dict passed directly to from_signals for signal handling.
        portfolio_kwargs: Optional dict passed directly to from_signals for portfolio config.

    Returns:
        A vectorbt Portfolio object containing the backtest results.

    Raises:
        ValueError: If 'Close' column is missing from price_df.
    """
    if 'Close' not in price_df.columns:
        raise ValueError("Price DataFrame must contain a 'Close' column.")

    # Use Open price for execution if available, otherwise defaults to Close
    exec_price_col = price_df['Open'] if 'Open' in price_df.columns else price_df['Close']

    # Ensure signal indices align with price data
    entries_series, exits_series = entries_series.align(price_df['Close'], join='right', fill_value=False)

    # Prepare signal kwargs (stop loss, take profit)
    default_signal_kwargs = {
        'sl_stop': sl_stop,
        'tp_stop': tp_stop,
    }
    if signal_kwargs:
        default_signal_kwargs.update(signal_kwargs)

    # Prepare portfolio kwargs (size, fees, etc.)
    default_portfolio_kwargs = {
        'size': size,
        'size_type': size_type, # Use the string directly
        'fees': fees,
        'slippage': slippage,
        'freq': frequency,
        'init_cash': initial_capital,
    }
    if portfolio_kwargs:
        default_portfolio_kwargs.update(portfolio_kwargs)

    print("Running vectorbt Portfolio.from_signals simulation...")
    try:
        portfolio = vbt.Portfolio.from_signals(
            close=price_df['Close'],
            open=exec_price_col,
            entries=entries_series,
            exits=exits_series,
            **default_signal_kwargs,
            **default_portfolio_kwargs
        )
        print("Simulation complete.")
        return portfolio
    except Exception as e:
        print(f"Error during vectorbt simulation: {e}")
        raise # Re-raise the exception