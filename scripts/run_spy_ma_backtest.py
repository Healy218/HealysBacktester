# scripts/run_spy_ma_backtest.py

import vectorbt as vbt
import pandas as pd
import numpy as np
import sys
import os

# --- Add Project Root to Python Path ---
# (Assuming this part is correct and needed for your structure)
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    if project_root not in sys.path:
        sys.path.insert(0, str(project_root))
except NameError:
    print("Warning: Could not determine script directory automatically.")
    # Add fallback or handle appropriately if running interactively/differently
    project_root = '.' # Example fallback
    if project_root not in sys.path:
       sys.path.insert(0, str(project_root))
# --- End Path Modification ---

# Use absolute imports relative to the project root (HealysBacktester)
from indicators import moving_averages
from signals import ma_crossover
from portfolio import simulator # simulator.py should contain the latest fix (normalize/reindex)
from analysis import metrics, plotting
# from config import settings # Import your settings if using config file

# --- Configuration ---
SYMBOL = 'SPY'
START_DATE = '2020-01-01'
END_DATE = '2023-12-31'
INTERVAL = '1D' # Ensure this matches data frequency

# Strategy Parameters
SHORT_WINDOW = 20
LONG_WINDOW = 50

# Backtest Settings
INITIAL_CAPITAL = 100000.0
FEES = 0.001      # 0.1% fee per trade value
SLIPPAGE = 0.0005 # 0.05% slippage per trade execution price
# Note: Default size/size_type are now handled within simulator.py
# Default is size=0.99, size_type='percent' in the cleaned simulator
DEFAULT_SIZE = 0.99
DEFAULT_SIZE_TYPE = 'percent'
DEFAULT_FREQ = 'D' # Frequency for portfolio simulation stats (usually 'D' for daily)

print(f"Starting backtest for {SYMBOL} MA({SHORT_WINDOW}/{LONG_WINDOW})...")
print(f"Period: {START_DATE} to {END_DATE}")
print(f"Settings: Initial Capital=${INITIAL_CAPITAL:,.2f}, Fees={FEES*100:.3f}%, Slippage={SLIPPAGE*100:.3f}%")
print(f"Sizing: Default Size={DEFAULT_SIZE}, Default Size Type='{DEFAULT_SIZE_TYPE}' (can be overridden)")

# --- Initialize Variables ---
price_data = pd.DataFrame()
entries = pd.Series(dtype=bool)
exits = pd.Series(dtype=bool)
portfolio = None

# --- Workflow ---

# 1. Load Data using vectorbt
print(f"\n[1/4] Downloading data for {SYMBOL}...")
try:
    # Using YFData as before
    price_data_raw = vbt.YFData.download(
        SYMBOL,
        start=START_DATE,
        end=END_DATE,
        interval=INTERVAL,
        missing_index='drop' # Drop rows where index is missing (e.g., market holidays)
    )
    price_data = price_data_raw.get(['Open', 'High', 'Low', 'Close', 'Volume'])

    # Remove timezone information immediately after download
    # This caused issues before if not done consistently
    if price_data.index.tz is not None:
         print("Removing timezone info from price data index...")
         price_data.index = price_data.index.tz_localize(None)
         print("Timezone info removed.")

    print(f"Data downloaded successfully. Shape: {price_data.shape}")

    if price_data.isnull().values.any():
        print("Warning: NaNs found in downloaded data. Applying ffill/bfill.")
        price_data = price_data.ffill().bfill() # Forward fill then backward fill
    if price_data.empty:
         raise ValueError("Downloaded data is empty after cleaning.")
    if price_data.isnull().values.any(): # Check again after fill
        raise ValueError("Data still contains NaNs after ffill/bfill.")


except Exception as e:
    print(f"FATAL ERROR downloading or processing data for {SYMBOL}: {e}")
    exit()

# 2. Generate Signals
print(f"\n[2/4] Generating signals for MA({SHORT_WINDOW}/{LONG_WINDOW})...")
try:
    # Ensure close prices passed are clean and have the correct index
    entries, exits = ma_crossover.generate_ma_signals(
        close_prices_series=price_data['Close'], # Pass the potentially cleaned Close prices
        short_window=SHORT_WINDOW,
        long_window=LONG_WINDOW
    )
    print("Signals generated.")
    # Print sums immediately after generation to verify signal counts
    print(f"Total Entries Generated: {entries.sum()}, Total Exits Generated: {exits.sum()}")
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
if entries.sum() > 0: # Proceed only if there are entry signals
    try:
        # --- CLEANED CALL TO SIMULATOR ---
        # Pass parameters; simulator uses its internal defaults (e.g., size=0.99, type='percent')
        # unless overridden here.
        portfolio = simulator.run_backtest(
            price_df=price_data,       # Pass the original price data (simulator handles normalization)
            entries_series=entries,
            exits_series=exits,
            initial_capital=INITIAL_CAPITAL,
            fees=FEES,                 # Pass the fee rate
            slippage=SLIPPAGE,         # Pass the slippage rate
            frequency=DEFAULT_FREQ,    # Pass the desired frequency for results
            size=DEFAULT_SIZE,             # Explicitly pass the intended size
            size_type=DEFAULT_SIZE_TYPE    # Explicitly pass the intended size type
            # Add other parameters like sl_stop=0.10 if needed
        )
        # --- END CLEANED CALL ---
        print("Simulation complete.")

    except ImportError:
        print("FATAL ERROR: Could not import portfolio simulator module.")
        exit()
    except Exception as e:
        print(f"Error during simulation: {e}")
        # Allow script to continue to analysis if possible, or exit if preferred
else:
    print("Skipping simulation because no entry signals were generated.")

# 4. Analyze and Plot Results
print(f"\n[4/4] Analyzing results...")
if portfolio is not None:
    try:
        metrics.display_summary_stats(portfolio)
        trades_df = metrics.get_trade_records(portfolio)
        if not trades_df.empty:
            print("\n--- Trade Records (First 5) ---")
            # Ensure 'trades_df' is a DataFrame before calling .head()
            if isinstance(trades_df, pd.DataFrame):
                print(trades_df.head())
            else:
                print("Trade records are not in expected DataFrame format.")
                print(trades_df) # Print whatever it is for debugging
        else:
            print("\nNo trades were executed according to portfolio object.") # Should not happen if simulation ran

        # Generate plots
        print("Generating portfolio summary plot...")
        plotting.plot_portfolio_summary(portfolio)
        print("Generating trades plot...")
        # Pass the original price_data for plotting context
        plotting.plot_trades(portfolio, price_data)

    except ImportError:
        print("ERROR: Could not import analysis or plotting modules.")
    except Exception as e:
        print(f"ERROR during analysis or plotting: {e}")

else:
    print("Skipping analysis because simulation did not run or failed.")


print(f"\nBacktest script for {SYMBOL} finished.")