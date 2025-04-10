# Purpose: Calculate specific technical indicators. Functions should be simple and reusable.

import pandas as pd
import talib # Or other indicator libraries

function calculate_sma(prices_series, window):
  # INPUT: pandas Series (e.g., 'Close' prices), window period (int)
  # OUTPUT: pandas Series containing SMA values

  if length(prices_series) < window:
    print("Warning: Not enough data for SMA window:", window)
    return create_series_with_nans_like(prices_series)

  sma_series = talib.SMA(prices_series, timeperiod=window)
  return sma_series

end function

function calculate_ema(prices_series, window):
  # INPUT: pandas Series (e.g., 'Close' prices), window period (int)
  # OUTPUT: pandas Series containing EMA values

  if length(prices_series) < window:
    print("Warning: Not enough data for EMA window:", window)
    return create_series_with_nans_like(prices_series)

  ema_series = talib.EMA(prices_series, timeperiod=window)
  return ema_series

end function

# --- Add other indicator functions (RSI, MACD, etc.) in their respective files ---