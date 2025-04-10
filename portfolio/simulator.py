# Purpose: Run the vectorbt backtest simulation.

import vectorbt as vbt
import pandas as pd

function run_backtest(price_df, entries_series, exits_series, initial_capital, fee_percent, slippage_percent, frequency):
  # INPUT: Cleaned OHLCV DataFrame, entry Series, exit Series, simulation parameters
  # OUTPUT: vectorbt Portfolio object

  # Ensure inputs are valid (e.g., indices match)
  # ... validation checks ...

  print("Running vectorbt Portfolio simulation...")
  # Use vectorbt's from_signals method
  portfolio = vbt.Portfolio.from_signals(
      close=price_df['Close'],          # Use the 'Close' price for simulation
      entries=entries_series,
      exits=exits_series,
      freq=frequency,                   # e.g., 'D' for daily, 'H' for hourly
      init_cash=initial_capital,
      fees=fee_percent,                 # e.g., 0.001 for 0.1%
      slippage=slippage_percent,        # e.g., 0.0005 for 0.05%
      # Optional: Add 'Open' if needed for execution price simulation
      # open=price_df['Open'],
      # Optional: Set sl_stop, tp_stop for stop-loss/take-profit
      # sl_stop=0.10, # Example: 10% stop loss
      # tp_stop=0.20, # Example: 20% take profit
  )
  print("Simulation complete.")
  return portfolio

end function