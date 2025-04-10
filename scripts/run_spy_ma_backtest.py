# Purpose: Orchestrate a specific backtest run.

# Import necessary modules from your project
from data import data_loader, data_cleaner
from indicators import moving_averages
from signals import ma_crossover
from portfolio import simulator
from analysis import metrics, plotting
from config import settings # Import your settings

# --- Configuration ---
SYMBOL = 'SPY'
START_DATE = '2020-01-01'
END_DATE = '2023-12-31'
INTERVAL = '1D' # Or 'D' depending on loader/vectorbt freq requirement
SHORT_WINDOW = 20
LONG_WINDOW = 50

# --- Workflow ---
print(f"Starting backtest for {SYMBOL} MA({SHORT_WINDOW},{LONG_WINDOW})...")

# 1. Load Data
raw_data = data_loader.load_price_data(SYMBOL, START_DATE, END_DATE, INTERVAL)
if raw_data is empty or invalid:
  exit("Failed to load data.")

# 2. Clean Data
price_data = data_cleaner.clean_ohlcv_data(raw_data)
if price_data is empty or invalid:
  exit("Failed to clean data.")

# 3. Generate Signals
# (Indicators are calculated within the signal function in this example)
entries, exits = ma_crossover.generate_ma_signals(
    close_prices_series=price_data['Close'],
    short_window=SHORT_WINDOW,
    long_window=LONG_WINDOW
)

# 4. Run Simulation
portfolio = simulator.run_backtest(
    price_df=price_data,
    entries_series=entries,
    exits_series=exits,
    initial_capital=settings.INITIAL_CAPITAL,
    fee_percent=settings.FEES,
    slippage_percent=settings.SLIPPAGE,
    frequency=settings.DEFAULT_FREQ # Match interval, e.g., 'D'
)

# 5. Analyze Results
print("\n--- Results ---")
stats = metrics.get_summary_stats(portfolio)
metrics.display_metrics(stats)

# Optional: Display trades
# trades_df = metrics.get_trade_records(portfolio)
# print("\n--- Trades ---")
# print(trades_df)

# 6. Plot Results
plotting.plot_portfolio_summary(portfolio)
# Optional: Plot signals on price chart (may need to pass indicator data from step 3 if needed)
# plotting.plot_signals(price_data, entries, exits)

print(f"Backtest for {SYMBOL} completed.")