# Purpose: Generate vectorbt-compatible entry and exit signals based on price/indicator data.

import pandas as pd
from indicators import moving_averages # Import necessary indicator functions

function generate_ma_signals(close_prices_series, short_window, long_window):
  # INPUT: pandas Series of close prices, short/long window periods
  # OUTPUT: pandas Series for entries (True/False), pandas Series for exits (True/False)

  # Calculate indicators
  short_ma = moving_averages.calculate_sma(close_prices_series, short_window)
  long_ma = moving_averages.calculate_sma(close_prices_series, long_window)

  # Generate crossover signals (vectorized)
  entries = (short_ma > long_ma) & (short_ma.shift(1) <= long_ma.shift(1))
  exits = (short_ma < long_ma) & (short_ma.shift(1) >= long_ma.shift(1))

  # Clean signals (optional but recommended by vectorbt docs)
  # entries, exits = clean_signals(entries, exits) # (e.g., ensure exit doesn't happen same bar as entry)

  print("MA Crossover signals generated.")
  return entries, exits

end function

# --- Add other signal generation functions (RSI thresholds, etc.) in their respective files ---
