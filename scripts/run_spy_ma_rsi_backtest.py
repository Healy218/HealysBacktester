# scripts/run_spy_ma_rsi_backtest.py

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
from signals import ma_crossover, rsi_threshold, signal_combiners # Import all needed signal modules
from portfolio import simulator
from analysis import metrics, plotting
from utils import config_parser

# --- Load Configuration ---
try:
    config = config_parser.load_config('config/settings.py')
    DATA_CONFIG = config.get('DATA_CONFIG', {})
    STRATEGY_MA_CONFIG = config.get('STRATEGY_MA_CROSSOVER', {}) # Load MA config
    STRATEGY_RSI_CONFIG = config.get('STRATEGY_RSI', {})       # Load RSI config
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

# Strategy Params - MA
SHORT_WINDOW = STRATEGY_MA_CONFIG.get('SHORT_WINDOW', 20)
LONG_WINDOW = STRATEGY_MA_CONFIG.get('LONG_WINDOW', 50)

# Strategy Params - RSI
RSI_WINDOW = STRATEGY_RSI_CONFIG.get('RSI_WINDOW', 14)
# We only need the RSI EXIT threshold for this combined strategy example
RSI_EXIT_THRESHOLD = STRATEGY_RSI_CONFIG.get('EXIT_THRESHOLD', 70)

# Backtest Settings (Same as other scripts)
INITIAL_CAPITAL = BACKTEST_CONFIG.get('INITIAL_CAPITAL', 100000.0)
FEES = BACKTEST_CONFIG.get('FEES_PERCENT', 0.001)
SLIPPAGE = BACKTEST_CONFIG.get('SLIPPAGE_PERCENT', 0.0005)
DEFAULT_SIZE = BACKTEST_CONFIG.get('DEFAULT_SIZE', 0.99)
DEFAULT_SIZE_TYPE = BACKTEST_CONFIG.get('DEFAULT_SIZE_TYPE', 'percent')
DEFAULT_FREQ = BACKTEST_CONFIG.get('DEFAULT_FREQ', 'D')
SL_STOP = BACKTEST_CONFIG.get('STOP_LOSS_PERCENT', None) if BACKTEST_CONFIG.get('USE_STOP_LOSS', False) else None
TP_STOP = BACKTEST_CONFIG.get('TAKE_PROFIT_PERCENT', None) if BACKTEST_CONFIG.get('USE_TAKE_PROFIT', False) else None

# --- Print Run Info ---
print(f"--- Starting Combined MA Crossover + RSI Exit Backtest ---")
print(f"Symbol: {SYMBOL}, Period: {START_DATE} to {END_DATE} ({INTERVAL})")
print(f"Strategy Params: MA({SHORT_WINDOW}/{LONG_WINDOW}) Entry, MA Cross OR RSI({RSI_WINDOW}) > {RSI_EXIT_THRESHOLD} Exit")
# ... (rest of print info) ...
print("-" * 35)

# --- Initialize Variables ---
price_data = pd.DataFrame()
entries = None
exits = None
portfolio = None

# --- Workflow ---

# 1. Load Data (Same as MA script)
print(f"\n[1/4] Loading data for {SYMBOL}...")
# ... (Keep data loading code identical to previous scripts) ...
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

# 2. Generate Signals (Combine MA and RSI)
print(f"\n[2/4] Generating MA & RSI signals and combining...")
try:
    # Generate MA Crossover signals
    ma_entries, ma_exits = ma_crossover.generate_ma_signals(
        close_prices_series=price_data['Close'],
        short_window=SHORT_WINDOW,
        long_window=LONG_WINDOW
    )
    print(f"MA Signals Generated: Entries={ma_entries.sum()}, Exits={ma_exits.sum()}")

    # Generate RSI signals (we only technically need the exit condition)
    # We still generate both for the combiner function signature though
    _, rsi_exits = rsi_threshold.generate_rsi_signals( # Note the rsi_window fix from before
        close_prices_series=price_data['Close'],
        window=RSI_WINDOW, # Corrected parameter name
        entry_threshold=0, # Dummy value, entry not used directly but needed for logic below
        exit_threshold=RSI_EXIT_THRESHOLD
    )
    # Create a dummy entry signal for RSI (always True) to use with combine_signals_and
    # This ensures MA entries aren't filtered out by the AND logic in the combiner
    rsi_entries_dummy = pd.Series(True, index=price_data.index)
    print(f"RSI Exit Signals Generated: Exits={rsi_exits.sum()}")


    # Combine Signals using combine_signals_and:
    # Entry: ma_entries AND rsi_entries_dummy (effectively just ma_entries)
    # Exit: ma_exits OR rsi_exits
    print("\nCombining signals using 'combine_signals_and' for MA Entry / (MA Exit OR RSI Exit)...")
    entries, exits = signal_combiners.combine_signals_and(
        entries1=ma_entries,
        exits1=ma_exits,
        entries2=rsi_entries_dummy, # Use the dummy all-True entries
        exits2=rsi_exits           # Use the actual RSI exits
    )

    print("Combined Signals Generated.")
    print(f"Total Final Entries: {entries.sum()}, Total Final Exits: {exits.sum()}")
    if not entries.any():
        print("Warning: No final entry signals were generated.")

except ImportError as ie:
     print(f"FATAL ERROR: Could not import signal generation modules: {ie}")
     exit()
except Exception as e:
    print(f"FATAL ERROR generating or combining signals: {e}")
    # Consider adding traceback here for detailed debugging if needed
    # import traceback
    # print(traceback.format_exc())
    exit()

# 3. Run Simulation (Same call)
print(f"\n[3/4] Running backtest simulation...")
# ... (Keep simulation code identical to previous scripts) ...
portfolio = None
if entries is not None and isinstance(entries, pd.Series) and entries.any():
    try:
        portfolio = simulator.run_backtest(
            price_df=price_data,
            entries_series=entries, # Use combined signals
            exits_series=exits,     # Use combined signals
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


# 4. Analyze and Plot Results (Same call)
print(f"\n[4/4] Analyzing results...")
# ... (Keep analysis/plotting code identical to RSI script) ...
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