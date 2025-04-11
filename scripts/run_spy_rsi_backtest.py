# scripts/run_spy_rsi_backtest.py

import vectorbt as vbt
import pandas as pd
import numpy as np
import sys
import os

# --- Add Project Root to Python Path ---
# (Same as before)
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    if project_root not in sys.path:
        sys.path.insert(0, str(project_root))
except NameError:
    print("Warning: Could not determine script directory automatically.")
    project_root = '.'
    if project_root not in sys.path:
       sys.path.insert(0, str(project_root))
# --- End Path Modification ---

# --- Import necessary modules ---
from signals import rsi_threshold  # Import the RSI signal generator
from portfolio import simulator
from analysis import metrics, plotting
from utils import config_parser

# --- Load Configuration ---
try:
    config = config_parser.load_config('config/settings.py')
    DATA_CONFIG = config.get('DATA_CONFIG', {})
    STRATEGY_CONFIG = config.get('STRATEGY_RSI', {}) # Load RSI specific config
    BACKTEST_CONFIG = config.get('BACKTEST_CONFIG', {})
except FileNotFoundError:
    print("FATAL ERROR: Configuration file 'config/settings.py' not found.")
    exit()
except Exception as e:
    print(f"FATAL ERROR: Could not load configuration: {e}")
    exit()

# --- Extract Parameters ---
# Data Params
SYMBOL = DATA_CONFIG.get('SYMBOL', 'SPY')
START_DATE = DATA_CONFIG.get('START_DATE', '2020-01-01')
END_DATE = DATA_CONFIG.get('END_DATE', '2023-12-31')
INTERVAL = DATA_CONFIG.get('INTERVAL', '1D')

# Strategy Params (RSI specific)
RSI_WINDOW = STRATEGY_CONFIG.get('RSI_WINDOW', 14)
ENTRY_THRESHOLD = STRATEGY_CONFIG.get('ENTRY_THRESHOLD', 30)
EXIT_THRESHOLD = STRATEGY_CONFIG.get('EXIT_THRESHOLD', 70)

# Backtest Settings
INITIAL_CAPITAL = BACKTEST_CONFIG.get('INITIAL_CAPITAL', 100000.0)
FEES = BACKTEST_CONFIG.get('FEES_PERCENT', 0.001)
SLIPPAGE = BACKTEST_CONFIG.get('SLIPPAGE_PERCENT', 0.0005)
DEFAULT_SIZE = BACKTEST_CONFIG.get('DEFAULT_SIZE', 0.99)
DEFAULT_SIZE_TYPE = BACKTEST_CONFIG.get('DEFAULT_SIZE_TYPE', 'percent')
DEFAULT_FREQ = BACKTEST_CONFIG.get('DEFAULT_FREQ', 'D')
SL_STOP = BACKTEST_CONFIG.get('STOP_LOSS_PERCENT', None) if BACKTEST_CONFIG.get('USE_STOP_LOSS', False) else None
TP_STOP = BACKTEST_CONFIG.get('TAKE_PROFIT_PERCENT', None) if BACKTEST_CONFIG.get('USE_TAKE_PROFIT', False) else None

# --- Print Run Info ---
print(f"--- Starting RSI Threshold Backtest ---")
print(f"Symbol: {SYMBOL}, Period: {START_DATE} to {END_DATE} ({INTERVAL})")
print(f"Strategy Params: RSI Window={RSI_WINDOW}, Entry Threshold={ENTRY_THRESHOLD}, Exit Threshold={EXIT_THRESHOLD}")
print(f"Backtest Settings: Initial Capital=${INITIAL_CAPITAL:,.2f}, Fees={FEES*100:.3f}%, Slippage={SLIPPAGE*100:.3f}%")
print(f"Sizing: Size={DEFAULT_SIZE}, Size Type='{DEFAULT_SIZE_TYPE}'")
print(f"Stop Loss: {'Enabled - ' + str(SL_STOP*100) + '%' if SL_STOP else 'Disabled'}")
print(f"Take Profit: {'Enabled - ' + str(TP_STOP*100) + '%' if TP_STOP else 'Disabled'}")
print("-" * 35)

# --- Initialize Variables ---
price_data = pd.DataFrame()
entries = None
exits = None
portfolio = None

# --- Workflow ---

# 1. Load Data (Same as MA script)
print(f"\n[1/4] Loading data for {SYMBOL}...")
try:
    price_data_raw = vbt.YFData.download(
        SYMBOL, start=START_DATE, end=END_DATE, interval=INTERVAL, missing_index='drop'
    )
    price_data = price_data_raw.get(['Open', 'High', 'Low', 'Close', 'Volume'])
    if price_data.index.tz is not None:
         price_data.index = price_data.index.tz_localize(None)
    print(f"Data loaded successfully. Shape: {price_data.shape}")
    if price_data.isnull().values.any():
        print("Warning: NaNs found. Applying ffill/bfill.")
        price_data = price_data.ffill().bfill()
    if price_data.empty or price_data.isnull().values.any() or 'Close' not in price_data.columns or price_data['Close'].isnull().any():
         raise ValueError("Data invalid after loading/cleaning.")
    print(f"Data check complete.")
except Exception as e:
    print(f"FATAL ERROR loading or verifying data: {e}")
    exit()

# 2. Generate Signals (Using RSI logic)
print(f"\n[2/4] Generating RSI({RSI_WINDOW}, {ENTRY_THRESHOLD}/{EXIT_THRESHOLD}) signals...")
try:
    # Generate RSI signals using the dedicated module
    entries, exits = rsi_threshold.generate_rsi_signals(
        close_prices_series=price_data['Close'],
        window=RSI_WINDOW,
        entry_threshold=ENTRY_THRESHOLD,
        exit_threshold=EXIT_THRESHOLD
    )
    print("Signals generated.")
    print(f"Total Entries Generated: {entries.sum()}, Total Exits Generated: {exits.sum()}")
    if not entries.any():
        print("Warning: No entry signals were generated.")

except ImportError:
     print("FATAL ERROR: Could not import rsi_threshold module.")
     exit()
except Exception as e:
    print(f"FATAL ERROR generating signals: {e}")
    exit()

# 3. Run Simulation (Same call as MA script)
print(f"\n[3/4] Running backtest simulation...")
portfolio = None
if entries is not None and isinstance(entries, pd.Series) and entries.any():
    try:
        portfolio = simulator.run_backtest(
            price_df=price_data,
            entries_series=entries,
            exits_series=exits,
            initial_capital=INITIAL_CAPITAL,
            fees=FEES,
            slippage=SLIPPAGE,
            frequency=DEFAULT_FREQ,
            size=DEFAULT_SIZE,
            size_type=DEFAULT_SIZE_TYPE,
            sl_stop=SL_STOP,
            tp_stop=TP_STOP
        )
        print("Simulation complete.")
    except Exception as e:
        print(f"Error during simulation: {e}")
else:
     print("Skipping simulation because no valid entry signals were generated.")


# 4. Analyze and Plot Results (Same as MA script for single run)
print(f"\n[4/4] Analyzing results...")
if portfolio is not None:
    try:
        print("\n--- Performance Summary ---")
        stats = metrics.get_summary_stats(portfolio)
        if stats is not None:
             print(stats)
        else:
             print("Could not retrieve stats.")

        trades_df = metrics.get_trade_records(portfolio)
        if trades_df is not None and not trades_df.empty:
             print("\n--- Trade Records (First 5) ---")
             if isinstance(trades_df, pd.DataFrame):
                 print(trades_df.head())
             else:
                 print("Trade records are not in expected DataFrame format.")
                 print(trades_df)
        else:
             if portfolio.trades.count() > 0:
                 print("\nPortfolio object indicates trades were executed, but fetching records failed.")
             else:
                 print("\nNo trades were executed.")

        print("\nGenerating plots...")
        plotting.plot_portfolio_summary(portfolio)
        plotting.plot_trades(portfolio, price_data)
        print("Plots generated.")

    except Exception as e:
        print(f"ERROR during analysis or plotting: {e}")
else:
    print("Skipping analysis because simulation did not run or failed.")

print(f"\n--- Backtest Finished ---")