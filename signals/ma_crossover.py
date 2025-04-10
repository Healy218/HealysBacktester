# signals/ma_crossover.py

import pandas as pd
import vectorbt as vbt
from indicators import moving_averages # Import your indicator calculation functions

def generate_ma_signals(
    close_prices_series: pd.Series,
    short_window: int,
    long_window: int,
    short_ma_func=moving_averages.calculate_sma, # Allow specifying MA type
    long_ma_func=moving_averages.calculate_sma
    ) -> tuple[pd.Series, pd.Series]:
    """
    Generates entry and exit signals based on a moving average crossover strategy.

    Args:
        close_prices_series: pandas Series of close prices.
        short_window: The window period for the short MA.
        long_window: The window period for the long MA.
        short_ma_func: Function to calculate the short MA (default: SMA).
        long_ma_func: Function to calculate the long MA (default: SMA).

    Returns:
        A tuple containing:
            - entries (pd.Series): Boolean series indicating entry signals (True).
            - exits (pd.Series): Boolean series indicating exit signals (True).
    """
    if short_window >= long_window:
        raise ValueError("Short window must be less than long window")

    # 1. Calculate indicators using functions from the indicators module
    short_ma = short_ma_func(close_prices_series, window=short_window)
    long_ma = long_ma_func(close_prices_series, window=long_window)

    # 2. Generate signals using vectorbt's crossover functions
    # entries: True when short_ma crosses above long_ma
    entries = short_ma.vbt.crossed_above(long_ma)

    # exits: True when short_ma crosses below long_ma
    exits = short_ma.vbt.crossed_below(long_ma)

    # Optional: Apply signal cleaning/constraints if needed (e.g., prevent entry/exit on same bar)
    # clean_entries, clean_exits = entries.vbt.signals.clean(exits)
    # return clean_entries, clean_exits

    print(f"MA Crossover ({short_window}/{long_window}) signals generated.")
    return entries, exits
