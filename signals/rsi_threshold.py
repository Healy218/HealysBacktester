# signals/rsi_threshold.py

import pandas as pd
import vectorbt as vbt
from indicators import rsi # Import your indicator calculation functions

def generate_rsi_signals(
    close_prices_series: pd.Series,
    window: int = 14,
    entry_threshold: float = 30, # RSI level to enter (e.g., cross above oversold)
    exit_threshold: float = 70   # RSI level to exit (e.g., cross below overbought)
    ) -> tuple[pd.Series, pd.Series]:
    """
    Generates entry and exit signals based on RSI crossing thresholds.

    Enters when RSI crosses *above* the entry_threshold (oversold level).
    Exits when RSI crosses *below* the exit_threshold (overbought level).

    Args:
        close_prices_series: pandas Series of close prices.
        window: The window period for the RSI calculation (default: 14).
        entry_threshold: The RSI level to trigger an entry signal upon crossing above.
        exit_threshold: The RSI level to trigger an exit signal upon crossing below.

    Returns:
        A tuple containing:
            - entries (pd.Series): Boolean series indicating entry signals (True).
            - exits (pd.Series): Boolean series indicating exit signals (True).
    """

    # 1. Calculate RSI indicator
    rsi_series = rsi.calculate_rsi(close_prices_series, window=window)

    # 2. Generate signals using vectorbt's threshold crossing functions
    # entries: True when RSI crosses above the entry_threshold (oversold level)
    entries = rsi_series.vbt.crossed_above(entry_threshold)

    # exits: True when RSI crosses below the exit_threshold (overbought level)
    exits = rsi_series.vbt.crossed_below(exit_threshold)

    # Optional: Apply signal cleaning/constraints
    # clean_entries, clean_exits = entries.vbt.signals.clean(exits)
    # return clean_entries, clean_exits

    print(f"RSI Threshold ({window}, {entry_threshold}/{exit_threshold}) signals generated.")
    return entries, exits
