# indicators/moving_averages.py

import vectorbt as vbt
import pandas as pd

# Ensure you have the necessary libraries, especially if using talib indicators via vbt
# pip install vectorbt talib-binary (or follow TA-Lib installation steps)

def calculate_sma(close_prices_series: pd.Series, window: int) -> pd.Series:
    """
    Calculates the Simple Moving Average using vectorbt's MA indicator.

    Args:
        close_prices_series: pandas Series of close prices.
        window: The window period for the SMA.

    Returns:
        pandas Series containing SMA values.
    """
    # Use vectorbt's Moving Average indicator class
    sma = vbt.MA.run(close_prices_series, window=window, short_name='sma')
    # .ma returns the calculated moving average series
    return sma.ma

def calculate_ema(close_prices_series: pd.Series, window: int) -> pd.Series:
    """
    Calculates the Exponential Moving Average using vectorbt's MA indicator.

    Args:
        close_prices_series: pandas Series of close prices.
        window: The window period for the EMA.

    Returns:
        pandas Series containing EMA values.
    """
    # Use vectorbt's Moving Average indicator class with ewm=True
    ema = vbt.MA.run(close_prices_series, window=window, ewm=True, short_name='ema')
    # .ma returns the calculated moving average series
    return ema.ma

# Example using the TALib wrapper within vectorbt (alternative)
def calculate_sma_talib(close_prices_series: pd.Series, window: int) -> pd.Series:
    """
    Calculates SMA using vectorbt's TA-Lib wrapper.
    """
    # Access TA-Lib functions via the .vbt accessor
    sma_series = close_prices_series.vbt.talib('SMA', timeperiod=window)
    return sma_series

