# scripts/run_spy_ma_backtest.py

# --- Standard Imports ---
import pandas as pd
import numpy as np
import sys
import os
import itertools
import vectorbt as vbt

# Removed defaultdict as all_portfolios is a regular dict and all_stats_list handles stats
# from collections import defaultdict

# --- Print Versions ---
try:
    print(f"--- Library Versions ---")
    print(f"vectorbt: {vbt.__version__}")
    print(f"pandas: {pd.__version__}")
    print(f"numpy: {np.__version__}")
    print(f"------------------------")
except Exception as e:
    print(f"Warning: Could not print library versions - {e}")
# --- End Print Versions ---

# --- Add Project Root to Python Path ---
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
# Make sure these are the correct paths based on your project structure
from portfolio import simulator
from analysis import metrics, plotting
from utils import config_parser
from data import data_loader, data_cleaner
import traceback
# Removed signal imports as they are generated manually below

# --- Load Configuration --- <<< MOVED UP
try:
    config = config_parser.load_config('config/settings.py') # Ensure path is correct
    DATA_CONFIG = config.get('DATA_CONFIG', {})
    # STRATEGY_MA_CONFIG might still be needed if other MA params exist
    STRATEGY_MA_CONFIG = config.get('STRATEGY_MA_CROSSOVER', {})
    BACKTEST_CONFIG = config.get('BACKTEST_CONFIG', {})
    print("Configuration loaded successfully.") # Added confirmation
except FileNotFoundError:
    print("FATAL ERROR: Configuration file 'config/settings.py' not found.")
    exit()
except Exception as e:
    print(f"FATAL ERROR: Could not load configuration: {e}")
    exit()

# --- Extract Parameters from Config ---
# Data Params
SYMBOL = DATA_CONFIG.get('SYMBOL', 'SPY')
START_DATE = DATA_CONFIG.get('START_DATE', '2020-01-01')
END_DATE = DATA_CONFIG.get('END_DATE', '2023-12-31')
INTERVAL = DATA_CONFIG.get('INTERVAL', '1D')

# Backtest Settings
INITIAL_CAPITAL = BACKTEST_CONFIG.get('INITIAL_CAPITAL', 100000.0)
FEES = BACKTEST_CONFIG.get('FEES_PERCENT', 0.001)
SLIPPAGE = BACKTEST_CONFIG.get('SLIPPAGE_PERCENT', 0.0005)
DEFAULT_FREQ = BACKTEST_CONFIG.get('DEFAULT_FREQ', 'D')

# Sizing Settings
DEFAULT_SIZE = BACKTEST_CONFIG.get('DEFAULT_SIZE', 0.99) # Provide a default if None is not desired
DEFAULT_SIZE_TYPE = BACKTEST_CONFIG.get('DEFAULT_SIZE_TYPE', 'percent')

# Stop Loss / Take Profit Settings
USE_SL = BACKTEST_CONFIG.get('USE_STOP_LOSS', False)
SL_PERCENT = BACKTEST_CONFIG.get('STOP_LOSS_PERCENT', None)
USE_TP = BACKTEST_CONFIG.get('USE_TAKE_PROFIT', False)
TP_PERCENT = BACKTEST_CONFIG.get('TAKE_PROFIT_PERCENT', None)

# --- Determine SL/TP values to pass --- <<< MOVED HERE
sl_stop_value = SL_PERCENT if USE_SL and SL_PERCENT is not None else None
tp_stop_value = TP_PERCENT if USE_TP and TP_PERCENT is not None else None

# --- Parameter Optimization Ranges ---
# These could also potentially come from config if desired
short_windows = np.arange(10, 51, 10)
long_windows = np.arange(30, 101, 10)

# --- Print Run Info ---
print(f"\n--- Starting MA Crossover Parameter Optimization (Manual Loop) ---") # Clarified title
print(f"Symbol: {SYMBOL}, Period: {START_DATE} to {END_DATE} ({INTERVAL})")
print(f"Short Window Range: {short_windows}")
print(f"Long Window Range: {long_windows}")
print(f"Backtest Settings: Initial Capital=${INITIAL_CAPITAL:,.2f}, Fees={FEES:.3%}, Slippage={SLIPPAGE:.3%}")
# Use the loaded config values directly here for sizing
print(f"Sizing: Size={DEFAULT_SIZE}, Size Type='{DEFAULT_SIZE_TYPE}'")
# Use the calculated sl_stop_value and tp_stop_value for printing
print(f"Stop Loss: {'Enabled' if sl_stop_value else 'Disabled'}{f' ({SL_PERCENT:.1%})' if sl_stop_value else ''}")
print(f"Take Profit: {'Enabled' if tp_stop_value else 'Disabled'}{f' ({TP_PERCENT:.1%})' if tp_stop_value else ''}")
print("-" * 35)


# --- Initialize Variables ---
price_data = pd.DataFrame()
all_portfolios = {} # Regular dictionary is fine
all_stats_list = []

# --- Workflow ---

# 1. Load and Clean Data using Modules <<< MODIFIED STEP 1
print(f"\n[1/X] Loading and cleaning data for {SYMBOL}...")
price_data = None # Initialize price_data to None
try:
    # Call the data loader
    raw_data = data_loader.load_price_data(
        symbol=SYMBOL,
        start_date=START_DATE,
        end_date=END_DATE,
        interval=INTERVAL
        # cache_dir can be omitted to use default 'data/cache'
    )

    # Check if data loading was successful
    if raw_data is None or raw_data.empty:
        raise ValueError(f"Data loading failed for symbol {SYMBOL}.")

    # Call the data cleaner
    price_data = data_cleaner.clean_ohlcv_data(raw_data)

    # Check if data cleaning was successful
    if price_data is None or price_data.empty:
        raise ValueError(f"Data cleaning failed for symbol {SYMBOL}.")

    print(f"Data loading and cleaning successful. Final shape: {price_data.shape}")

except Exception as e:
    print(f"FATAL ERROR during data loading/cleaning: {e}")
    traceback.print_exc() # Optional: Print detailed error
    exit() # Exit if data is not available/valid


# 2. Iterate Through Parameters, Generate Signals, and Simulate - CORRECTED LOOP
print(f"\n[2/X] Iterating through parameter combinations...")
param_combinations = list(itertools.product(short_windows, long_windows))
valid_combinations = [(sw, lw) for sw, lw in param_combinations if sw < lw]
print(f"Total combinations to test: {len(valid_combinations)}")

combination_count = 0
for short_w, long_w in valid_combinations:
    combination_count += 1
    param_label = f"({short_w}, {long_w})"
    print(f"\n-- Testing Combination {combination_count}/{len(valid_combinations)}: {param_label} --")

    try:
        # --- Generate Signals ---
        print("Generating signals...")
        short_sma = price_data['Close'].rolling(window=short_w, min_periods=short_w).mean()
        long_sma = price_data['Close'].rolling(window=long_w, min_periods=long_w).mean()
        entries = short_sma.vbt.crossed_above(long_sma).astype(bool)
        exits = short_sma.vbt.crossed_below(long_sma).astype(bool)
        print(f"Signal sums: Entries={entries.sum()}, Exits={exits.sum()}")

        # --- Run Simulation (Only if Entries Exist) ---
        portfolio = None # Reset portfolio for each combo
        if entries.any():
            print("Running simulation...")
            # *** SINGLE CORRECT CALL inside the TRY block ***
            portfolio = simulator.run_backtest(
                price_data,                 # 1st arg: positional
                entries,                    # 2nd arg: positional
                exits,                      # 3rd arg: positional
                DEFAULT_FREQ,               # 4th arg: positional
                # --- Remaining args by keyword ---
                initial_capital=INITIAL_CAPITAL,
                fees=FEES,
                slippage=SLIPPAGE,
                size=DEFAULT_SIZE,
                size_type=DEFAULT_SIZE_TYPE,
                sl_stop=sl_stop_value,
                tp_stop=tp_stop_value
                # No short signals passed for MA crossover
            )

            # --- Store Results (Only if simulation succeeded) ---
            if portfolio is not None:
                all_portfolios[(short_w, long_w)] = portfolio
                stats = metrics.get_summary_stats(portfolio)
                if stats is not None:
                    stats.name = (short_w, long_w) # Use tuple directly as name for column indexing later
                    all_stats_list.append(stats)
                    print(f"Simulation successful for {param_label}. Trades: {portfolio.trades.count()}")
                else:
                    print(f"Warning: get_summary_stats returned None for {param_label}.")
            else:
                 print(f"Warning: Simulation returned None for {param_label}.")
        else:
            print(f"Skipping simulation for {param_label} (no entry signals generated).")

    # --- Catch errors for this specific combination ---
    except Exception as e:
        print(f"ERROR processing combination {param_label}: {e}")
        # Optionally print traceback for debugging
        # import traceback
        # print(traceback.format_exc())
        # Continue to the next combination in the loop

# 3. Analyze Aggregate Results (Keep your existing analysis block)
print(f"\n[3/X] Analyzing aggregate results...")
# ... (Your analysis code here - seems generally okay) ...
if not all_stats_list:
    print("No simulations completed successfully. Cannot analyze results.")
else:
    try:
        # Concatenate stats into a DataFrame - index should be metric names, columns should be param tuples
        all_stats_df = pd.concat(all_stats_list, axis=1)
        # Ensure column names are tuples if needed (depends on how concat handles Series names)
        # all_stats_df.columns = pd.MultiIndex.from_tuples(all_stats_df.columns) # Might be needed

        print("\n--- Performance Summary (All Combinations) ---")
        # Ensure the stats you want exist in the index
        key_stats = ['Total Return [%]', 'Win Rate [%]', 'Sharpe Ratio', 'Max Drawdown [%]']
        stats_to_print_idx = all_stats_df.index.intersection(key_stats)
        if not stats_to_print_idx.empty:
            stats_to_print = all_stats_df.loc[stats_to_print_idx]
            print(stats_to_print)
        else:
             print(f"Warning: None of the key stats ({key_stats}) found in results.")
             print("Available stats:", all_stats_df.index.tolist())


        if 'Total Return [%]' in all_stats_df.index:
            # Find the column (parameter tuple) with the max Total Return
            best_col_idx = all_stats_df.loc['Total Return [%]'].idxmax()
            # Ensure best_col_idx is indeed the parameter tuple
            best_params = best_col_idx
            best_stats = all_stats_df[best_col_idx] # Select the column with the best stats

            print(f"\n--- Best Performing Parameters (based on Total Return) ---")
            if isinstance(best_params, tuple) and len(best_params) >= 2:
                 print(f"Short Window: {best_params[0]}, Long Window: {best_params[1]}")
            else:
                 # Handle cases where idxmax might not return tuple as expected
                 print(f"Best Column Index: {best_params} (Column name in DataFrame)")
                 # You might need to re-fetch the tuple if column names aren't tuples:
                 # best_params = tuple(map(int, best_params.strip('()').split(','))) # Example conversion

            print("Stats for Best Combination:")
            print(best_stats)

            # Ensure the best_params tuple matches the keys in all_portfolios dict
            if best_params in all_portfolios:
                 print("\nGenerating plots for the best performing combination...")
                 best_portfolio_obj = all_portfolios[best_params]
                 # Check if plotting functions exist and handle potential errors
                 try:
                     plotting.plot_portfolio_summary(best_portfolio_obj)
                     plotting.plot_trades(best_portfolio_obj, price_data)
                     print("Plots generated.")
                 except AttributeError:
                      print("ERROR: Plotting functions not found or incorrect.")
                 except Exception as plot_err:
                      print(f"ERROR generating plots: {plot_err}")
            else:
                 print(f"Could not find portfolio object for the best parameters {best_params} to plot.")
                 print(f"Available keys: {list(all_portfolios.keys())}")
        else:
            print("Could not determine best parameters - 'Total Return [%]' missing from stats.")

    except ImportError:
        print("ERROR: Could not import analysis or plotting modules.")
    except Exception as e:
        print(f"ERROR during aggregate analysis or plotting: {e}")
        # import traceback
        # print(traceback.format_exc())


print(f"\n--- Backtest Finished ---")