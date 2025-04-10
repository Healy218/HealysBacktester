# indicators/rsi.py

import vectorbt as vbt
import pandas as pd

# Ensure you have the necessary libraries
# pip install vectorbt talib-binary (or follow TA-Lib installation steps)

def calculate_rsi(close_prices_series: pd.Series, window: int = 14) -> pd.Series:
    """
    Calculates the Relative Strength Index (RSI) using vectorbt's RSI indicator.

    Args:
        close_prices_series: pandas Series of close prices.
        window: The window period for the RSI (default 14).

    Returns:
        pandas Series containing RSI values.
    """
    # Use vectorbt's RSI indicator class
    rsi = vbt.RSI.run(close_prices_series, window=window, short_name='rsi')
    # .rsi returns the calculated RSI series
    return rsi.rsi

# Example using the TALib wrapper within vectorbt (alternative)
def calculate_rsi_talib(close_prices_series: pd.Series, window: int = 14) -> pd.Series:
    """
    Calculates RSI using vectorbt's TA-Lib wrapper.
    """
    # Access TA-Lib functions via the .vbt accessor
    rsi_series = close_prices_series.vbt.talib('RSI', timeperiod=window)
    return rsi_series