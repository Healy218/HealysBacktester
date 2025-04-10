# scripts/run_spy_ma_backtest.py

import vectorbt as vbt
import pandas as pd
import numpy as np
import sys
import os

# --- Add Project Root to Python Path ---
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, str(project_root))
# --- End Path Modification ---

# Use absolute imports relative to the project root (HealysBacktester)
from indicators import moving_averages
from signals import ma_crossover
from portfolio import simulator
from analysis import metrics, plotting
# from config import settings # Import your settings if using config file

# --- Configuration ---
SYMBOL = 'SPY'
START_DATE = '2020-01-01'
END_DATE = '2023-12-31'
INTERVAL = '1D'

# Strategy Parameters
SHORT_WINDOW = 20
LONG_WINDOW = 50

# Backtest Settings
INITIAL_CAPITAL = 100000.0
FEES = 0.001 # 0.1% fee per trade
SLIPPAGE = 0.0005 # 0.05% slippage per trade
DEFAULT_FREQ = 'D' # Frequency for portfolio simulation

print(f"Starting backtest for {SYMBOL} MA({SHORT_WINDOW}/{LONG_WINDOW})...")
print(f"Period: {START_DATE} to {END_DATE}")

# --- Initialize Variables ---
price_data = pd.DataFrame()
entries = pd.Series(dtype=bool)
exits = pd.Series(dtype=bool)
portfolio = None

# --- Workflow ---

# 1. Load Data using vectorbt
print(f"\n[1/4] Downloading data for {SYMBOL}...")
try:
    price_data_raw = vbt.YFData.download(
        SYMBOL,
        start=START_DATE,
        end=END_DATE,
        interval=INTERVAL,
        missing_index='drop'
    )
    price_data = price_data_raw.get(['Open', 'High', 'Low', 'Close', 'Volume'])

    # Remove timezone information
    price_data.index = price_data.index.tz_localize(None)
    print("Timezone info removed from index.")

    print(f"Data downloaded successfully. Shape: {price_data.shape}")

    if price_data.isnull().values.any():
        print("Warning: NaNs found in downloaded data. Applying ffill/bfill.")
        price_data = price_data.ffill().bfill()
    if price_data.empty:
         raise ValueError("Downloaded data is empty.")

except Exception as e:
    print(f"FATAL ERROR downloading or processing data for {SYMBOL}: {e}")
    exit()

# 2. Generate Signals
print(f"\n[2/4] Generating signals for MA({SHORT_WINDOW}/{LONG_WINDOW})...")
try:
    entries, exits = ma_crossover.generate_ma_signals(
        close_prices_series=price_data['Close'],
        short_window=SHORT_WINDOW,
        long_window=LONG_WINDOW
    )
    print("Signals generated.")
    print(f"Total Entries: {entries.sum()}, Total Exits: {exits.sum()}")
    if not entries.any():
        print("Warning: No entry signals were generated.")

except ImportError:
     print("FATAL ERROR: Could not import signal generation module.")
     exit()
except Exception as e:
    print(f"FATAL ERROR generating signals: {e}")
    exit()

# 3. Run Simulation
print(f"\n[3/4] Running backtest simulation...")
portfolio = None
if entries.sum() > 0:
    try:
        # Note: simulator now defaults to size=np.inf, size_type='shares'
        portfolio = simulator.run_backtest(
            price_df=price_data,
            entries_series=entries,
            exits_series=exits,
            initial_capital=INITIAL_CAPITAL,
            fees=FEES,
            slippage=SLIPPAGE,
            frequency=DEFAULT_FREQ
            # You can override size/size_type here if needed, e.g.:
            # size=100, size_type='shares'
            # size=1.0, size_type='percent'
        )
        print("Simulation complete.")

    except ImportError:
        print("FATAL ERROR: Could not import portfolio simulator module.")
        exit()
    except Exception as e:
        print(f"Error during simulation: {e}")
        # Allow script to continue
else:
    print("Skipping simulation because no entry signals were generated.")

# 4. Analyze and Plot Results
print(f"\n[4/4] Analyzing results...")
if portfolio is not None:
    metrics.display_summary_stats(portfolio)
    trades_df = metrics.get_trade_records(portfolio)
    if not trades_df.empty:
        print("\n--- Trade Records (First 5) ---")
        print(trades_df.head())
    else:
        print("\nNo trades were executed.") # Check if this still prints

    plotting.plot_portfolio_summary(portfolio)
    plotting.plot_trades(portfolio, price_data)

else:
    print("Skipping analysis because simulation did not run or failed.")


print(f"\nBacktest script for {SYMBOL} finished.")