# scripts/run_spy_rsi_backtest.py

import vectorbt as vbt
import pandas as pd
import numpy as np
import sys
import os
import traceback # Import traceback for detailed error printing
from itertools import product # To help generate combo strings if needed
from typing import Optional, Union, Tuple # Import needed types

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
from signals import rsi_threshold  # Import the RSI signal generator
from portfolio import simulator
from analysis import metrics, plotting
from utils import config_parser
from data import data_loader, data_cleaner # ADD data module imports

# --- Load Configuration ---
try:
    config = config_parser.load_config('config/settings.py')
    DATA_CONFIG = config.get('DATA_CONFIG', {})
    STRATEGY_CONFIG = config.get('STRATEGY_RSI', {}) # Load RSI specific config
    BACKTEST_CONFIG = config.get('BACKTEST_CONFIG', {})
    print(f"Configuration loaded successfully from: {os.path.join(project_root, 'config/settings.py')}")
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

# Strategy Params (RSI specific) - MODIFIED FOR MULTI-PARAM & SHORTING
RSI_WINDOWS_LIST = STRATEGY_CONFIG.get('RSI_WINDOW', [14])
if isinstance(RSI_WINDOWS_LIST, int): RSI_WINDOWS_LIST = [RSI_WINDOWS_LIST]
RSI_WINDOWS = np.array(RSI_WINDOWS_LIST)

# Long thresholds
ENTRY_THRESHOLDS_LIST = STRATEGY_CONFIG.get('ENTRY_THRESHOLD', [30])
if isinstance(ENTRY_THRESHOLDS_LIST, (int, float)): ENTRY_THRESHOLDS_LIST = [ENTRY_THRESHOLDS_LIST]
ENTRY_THRESHOLDS = np.array(ENTRY_THRESHOLDS_LIST)

EXIT_THRESHOLDS_LIST = STRATEGY_CONFIG.get('EXIT_THRESHOLD', [70])
if isinstance(EXIT_THRESHOLDS_LIST, (int, float)): EXIT_THRESHOLDS_LIST = [EXIT_THRESHOLDS_LIST]
EXIT_THRESHOLDS = np.array(EXIT_THRESHOLDS_LIST)

# Shorting Control and Thresholds
ENABLE_SHORTING = BACKTEST_CONFIG.get('ENABLE_SHORTING', False) # Get shorting flag

SHORT_ENTRY_THRESHOLDS_LIST = STRATEGY_CONFIG.get('SHORT_ENTRY_THRESHOLD', None) # Optional short entry
if SHORT_ENTRY_THRESHOLDS_LIST is None and ENABLE_SHORTING:
    SHORT_ENTRY_THRESHOLDS = None # Let signal generator use defaults
else:
    if isinstance(SHORT_ENTRY_THRESHOLDS_LIST, (int, float)): SHORT_ENTRY_THRESHOLDS_LIST = [SHORT_ENTRY_THRESHOLDS_LIST]
    SHORT_ENTRY_THRESHOLDS = np.array(SHORT_ENTRY_THRESHOLDS_LIST) if SHORT_ENTRY_THRESHOLDS_LIST else None

SHORT_EXIT_THRESHOLDS_LIST = STRATEGY_CONFIG.get('SHORT_EXIT_THRESHOLD', None) # Optional short exit
if SHORT_EXIT_THRESHOLDS_LIST is None and ENABLE_SHORTING:
    SHORT_EXIT_THRESHOLDS = None # Let signal generator use defaults
else:
    if isinstance(SHORT_EXIT_THRESHOLDS_LIST, (int, float)): SHORT_EXIT_THRESHOLDS_LIST = [SHORT_EXIT_THRESHOLDS_LIST]
    SHORT_EXIT_THRESHOLDS = np.array(SHORT_EXIT_THRESHOLDS_LIST) if SHORT_EXIT_THRESHOLDS_LIST else None

# Backtest Settings
INITIAL_CAPITAL = BACKTEST_CONFIG.get('INITIAL_CAPITAL', 100000.0)
FEES = BACKTEST_CONFIG.get('FEES_PERCENT', 0.001)
SLIPPAGE = BACKTEST_CONFIG.get('SLIPPAGE_PERCENT', 0.0005)
DEFAULT_SIZE = BACKTEST_CONFIG.get('DEFAULT_SIZE', 10000.0) # Default to value sizing amount
DEFAULT_SIZE_TYPE = BACKTEST_CONFIG.get('DEFAULT_SIZE_TYPE', 'value') # Default to value sizing type
DEFAULT_FREQ = BACKTEST_CONFIG.get('DEFAULT_FREQ', 'D')
USE_SL = BACKTEST_CONFIG.get('USE_STOP_LOSS', False)
SL_PERCENT = BACKTEST_CONFIG.get('STOP_LOSS_PERCENT', 0.05)
USE_TP = BACKTEST_CONFIG.get('USE_TAKE_PROFIT', False)
TP_PERCENT = BACKTEST_CONFIG.get('TAKE_PROFIT_PERCENT', 0.10)

SL_STOP = SL_PERCENT if USE_SL else None
TP_STOP = TP_PERCENT if USE_TP else None


# --- Print Run Info --- MODIFIED
print(f"--- Starting RSI Threshold Backtest ---")
print(f"Symbol: {SYMBOL}, Period: {START_DATE} to {END_DATE} ({INTERVAL})")
windows_str = ', '.join(map(str, RSI_WINDOWS_LIST))
entry_str = ', '.join(map(str, ENTRY_THRESHOLDS_LIST))
exit_str = ', '.join(map(str, EXIT_THRESHOLDS_LIST))
print(f"Strategy Params: RSI Windows=[{windows_str}], Long Entry=[{entry_str}], Long Exit=[{exit_str}]")
if ENABLE_SHORTING:
    s_entry_str = 'Default' if SHORT_ENTRY_THRESHOLDS is None else ', '.join(map(str, SHORT_ENTRY_THRESHOLDS_LIST))
    s_exit_str = 'Default' if SHORT_EXIT_THRESHOLDS is None else ', '.join(map(str, SHORT_EXIT_THRESHOLDS_LIST))
    print(f"               Short Entry=[{s_entry_str}], Short Exit=[{s_exit_str}]")
# Calculate total combinations based on inputs provided
num_combos = len(RSI_WINDOWS)
num_combos *= len(ENTRY_THRESHOLDS) if ENTRY_THRESHOLDS is not None else 1
num_combos *= len(EXIT_THRESHOLDS) if EXIT_THRESHOLDS is not None else 1
if ENABLE_SHORTING:
     # This calculation might slightly overestimate if default logic reuses threshold arrays of different lengths
     num_combos_short_entry = len(SHORT_ENTRY_THRESHOLDS) if SHORT_ENTRY_THRESHOLDS is not None else (len(EXIT_THRESHOLDS) if EXIT_THRESHOLDS is not None else 1)
     num_combos_short_exit = len(SHORT_EXIT_THRESHOLDS) if SHORT_EXIT_THRESHOLDS is not None else (len(ENTRY_THRESHOLDS) if ENTRY_THRESHOLDS is not None else 1)
     # Rough estimate assuming independent combination (actual depends on itertools.product in signal gen)
     # A more accurate way is to count columns AFTER signal gen if needed
     # num_combos *= num_combos_short_entry * num_combos_short_exit # This is likely wrong if using product
     pass # Keep it simple, print the number calculated by the signal generator later
print(f"Parameter Combinations will be generated by vectorbt/signal generator.")
print(f"Backtest Settings: Initial Capital=${INITIAL_CAPITAL:,.2f}, Fees={FEES*100:.3f}%, Slippage={SLIPPAGE*100:.3f}%")
print(f"Sizing: Size={DEFAULT_SIZE}, Size Type='{DEFAULT_SIZE_TYPE}'") # Reflect loaded sizing
print(f"Stop Loss: {'Enabled - ' + str(SL_STOP*100) + '%' if SL_STOP else 'Disabled'}")
print(f"Take Profit: {'Enabled - ' + str(TP_STOP*100) + '%' if TP_STOP else 'Disabled'}")
print(f"Shorting Enabled: {ENABLE_SHORTING}")
print("-" * 35)

# --- Initialize Variables ---
# price_data = pd.DataFrame()
entries, exits, short_entries, short_exits = None, None, None, None # Expect 4 signals
portfolio = None
aggregate_stats_df = None # Initialize aggregate stats df
best_col_name = None # Initialize best column name

# --- Workflow ---

# 1. Load and Clean Data using Modules
print(f"\n[1/4] Loading and cleaning data for {SYMBOL}...")
price_data = None
try:
    raw_data = data_loader.load_price_data(
        symbol=SYMBOL, start_date=START_DATE, end_date=END_DATE, interval=INTERVAL
    )
    if raw_data is None or raw_data.empty: raise ValueError(f"Data loading failed for symbol {SYMBOL}.")
    price_data = data_cleaner.clean_ohlcv_data(raw_data)
    if price_data is None or price_data.empty: raise ValueError(f"Data cleaning failed for symbol {SYMBOL}.")
    print(f"Data loading and cleaning successful. Final shape: {price_data.shape}")
except Exception as e:
    print(f"FATAL ERROR during data loading/cleaning: {e}")
    traceback.print_exc()
    exit()

# 2. Generate Signals (Using updated RSI logic)
print(f"\n[2/4] Generating signals (Shorting: {ENABLE_SHORTING})...")
try:
    entries, exits, short_entries, short_exits = rsi_threshold.generate_rsi_signals(
        close_prices_series=price_data['Close'],
        window=RSI_WINDOWS,
        entry_threshold=ENTRY_THRESHOLDS,
        exit_threshold=EXIT_THRESHOLDS,
        enable_shorting=ENABLE_SHORTING,
        short_entry_threshold=SHORT_ENTRY_THRESHOLDS,
        short_exit_threshold=SHORT_EXIT_THRESHOLDS
    )
    print("Signals generated.")
    # Check shapes and sums
    if isinstance(entries, pd.DataFrame): print(f"Long Entries Shape: {entries.shape}")
    if isinstance(short_entries, pd.DataFrame): print(f"Short Entries Shape: {short_entries.shape}") # Will be None if disabled
    total_long_entries = entries.sum().sum() if isinstance(entries, pd.DataFrame) else (entries.sum() if isinstance(entries, pd.Series) else 0)
    total_long_exits = exits.sum().sum() if isinstance(exits, pd.DataFrame) else (exits.sum() if isinstance(exits, pd.Series) else 0)
    print(f"Total Long Entries: {total_long_entries}, Total Long Exits: {total_long_exits}")
    if ENABLE_SHORTING and short_entries is not None: # Check if short_entries is not None
        total_short_entries = short_entries.sum().sum() if isinstance(short_entries, pd.DataFrame) else (short_entries.sum() if isinstance(short_entries, pd.Series) else 0)
        total_short_exits = short_exits.sum().sum() if isinstance(short_exits, pd.DataFrame) else (short_exits.sum() if isinstance(short_exits, pd.Series) else 0)
        print(f"Total Short Entries: {total_short_entries}, Total Short Exits: {total_short_exits}")

except ImportError:
     print("FATAL ERROR: Could not import rsi_threshold module.")
     exit()
except Exception as e:
    print(f"FATAL ERROR generating signals: {e}")
    traceback.print_exc()
    exit()

# 3. Run Simulation (Passing short signals)
print(f"\n[3/4] Running backtest simulation...")
portfolio = None
# Check if any long or short entry signals were generated
simulation_possible = False
long_entries_exist = entries is not None and (entries.any().any() if isinstance(entries, pd.DataFrame) else entries.any())
short_entries_exist = False
if ENABLE_SHORTING and short_entries is not None:
    short_entries_exist = short_entries.any().any() if isinstance(short_entries, pd.DataFrame) else short_entries.any()

if long_entries_exist or short_entries_exist:
    simulation_possible = True
else:
    print("No valid entry signals (long or short) found.")

if simulation_possible:
    try:
        portfolio = simulator.run_backtest(
            price_df=price_data,
            entries_series=entries,
            exits_series=exits,
            short_entries_series=short_entries, # Pass short entries (will be None if disabled)
            short_exits_series=short_exits,     # Pass short exits (will be None if disabled)
            initial_capital=INITIAL_CAPITAL,
            fees=FEES,
            slippage=SLIPPAGE,
            frequency=DEFAULT_FREQ,
            size=DEFAULT_SIZE,
            size_type=DEFAULT_SIZE_TYPE, # Use configured sizing
            sl_stop=SL_STOP,
            tp_stop=TP_STOP
        )
    except Exception as e:
        print(f"Error during simulation: {e}")
        traceback.print_exc()
else:
     print("Skipping simulation because no valid entry signals were generated.")


# --- ADDED BLOCK: Get Aggregate Stats ---
aggregate_stats_df = None # Initialize
if portfolio is not None:
    print("\nAttempting to generate aggregate stats DataFrame...")
    try:
        # Get stats for ALL columns/combinations from the multi-column portfolio
        aggregate_stats_df = portfolio.stats()

        # Validate the result
        if not isinstance(aggregate_stats_df, pd.DataFrame):
             print("Warning: portfolio.stats() did not return a DataFrame for aggregate results. Cannot save aggregate CSV.")
             aggregate_stats_df = None # Reset if not DataFrame
        elif len(portfolio.wrapper.columns) > 1 and not isinstance(aggregate_stats_df.columns, pd.MultiIndex):
             # If portfolio had >1 column but stats columns are not MultiIndex, something might be wrong
             print("Warning: Aggregate stats DataFrame columns are not the expected MultiIndex for multiple combinations.")
        else:
             print(f"Successfully generated aggregate stats DataFrame. Shape: {aggregate_stats_df.shape}")

    except Exception as agg_e:
        print(f"Error generating aggregate stats DataFrame: {agg_e}")
        traceback.print_exc()
        aggregate_stats_df = None
# --- END ADDED BLOCK ---


# 4. Analyze and Plot Results - Using V4 Logic (Iterate Stats per Column)
print(f"\n[4/4] Analyzing results...")
best_col_name = None # Ensure best_col_name is initialized before the try block
if portfolio is not None:
    try:
        # --- Identify Best Combination --- REVISED LOGIC V4 ---
        metric_to_optimize = 'Total Return [%]' # Metric name as it appears in stats output
        # best_col_name = None # Moved initialization up
        metric_values = {} # Dictionary to store {col_name_tuple: metric_value}

        print(f"\n--- Attempting to identify best combination based on '{metric_to_optimize}' by checking stats per column ---")
        try:
            if portfolio is not None and hasattr(portfolio.wrapper, 'columns') and not portfolio.wrapper.columns.empty:
                column_names = portfolio.wrapper.columns
                # Use len() which works for both Index and MultiIndex
                print(f"Checking {len(column_names)} combinations...")

                for col_name in column_names:
                    try:
                        stats_series = portfolio.stats(column=col_name)
                        if isinstance(stats_series, pd.Series) and metric_to_optimize in stats_series.index:
                             metric_value = stats_series.loc[metric_to_optimize]
                             if pd.notna(metric_value):
                                 metric_values[col_name] = metric_value
                    except Exception as col_e:
                         print(f"Warning: Error getting stats for combo {col_name}: {col_e}")

                if metric_values:
                    best_col_name = max(metric_values, key=metric_values.get)
                    # print(f"Metric values per combination ({metric_to_optimize}):")
                    # Sort items by value (descending) for printing
                    for combo, value in sorted(metric_values.items(), key=lambda item: item[1], reverse=True):
                         # Format combo tuple for printing
                         if isinstance(combo, tuple) and len(combo) == 3:
                              combo_str = f"Win={combo[0]}, Entry={combo[1]}, Exit={combo[2]}" # Adjust indices if needed
                         else:
                              combo_str = str(combo)
                         # print(f"  Combo {combo_str}: {value:.2f}%")
                    print(f"Selected Best Combination: {best_col_name}")
                else:
                    print("Warning: Could not collect valid metric values for comparison.")
                    if not portfolio.wrapper.columns.empty:
                         best_col_name = portfolio.wrapper.columns[0]
                         print(f"Using first combination: {best_col_name} as fallback.")
            else:
                print("Error: Portfolio object is None or has no columns to analyze.")

        except Exception as e:
            print(f"Error occurred during best combination identification: {e}")
            traceback.print_exc()
            if portfolio is not None and not portfolio.wrapper.columns.empty:
                 best_col_name = portfolio.wrapper.columns[0]
                 print(f"Using first combination: {best_col_name} due to error during identification.")


        # --- Analyze and Plot BEST Combination ---
        if best_col_name is not None:
            if best_col_name not in portfolio.wrapper.columns:
                 print(f"Error: Determined best combination name '{best_col_name}' not valid in portfolio columns. Aborting analysis.")
            else:
                # Format the tuple name for printing - Adjust indices based on MultiIndex structure
                if isinstance(best_col_name, tuple) and len(best_col_name) >= 3:
                    best_col_name_str = f"Window={best_col_name[0]}, Entry={best_col_name[1]}, Exit={best_col_name[2]}"
                else:
                    best_col_name_str = str(best_col_name)

                print(f"\n--- Detailed Analysis for Best Combination ({best_col_name_str}) ---")

                # Get and print stats for the single best combination column
                best_stats = metrics.get_summary_stats(portfolio[best_col_name])
                if best_stats is not None and not best_stats.empty:
                     print("\n--- Performance Summary (Best Combination) ---")
                     print(best_stats)
                else:
                     print("Could not retrieve stats for the best combination.")

                # Get and print trades for the single best combination
                best_trades_df = metrics.get_trade_records(portfolio[best_col_name])
                if best_trades_df is not None and not best_trades_df.empty:
                    print("\n--- Trade Records (Best Combination - First 5) ---")
                    print(best_trades_df.head())
                    print(f"Total trades for best combination ({best_col_name_str}): {len(best_trades_df)}")
                else:
                     if portfolio[best_col_name].trades.count() > 0:
                          print(f"\nPortfolio object indicates trades for combo {best_col_name_str}, but fetching failed.")
                     else:
                          print(f"\nNo trades were executed for the best combination ({best_col_name_str}).")

                # --- REMOVED DIRECT PLOTTING CALLS from script ---

        else:
             print("\nSkipping detailed analysis and plotting as no best combination could be determined.")

    except Exception as e:
        print(f"ERROR during analysis: {e}")
        traceback.print_exc()

# --- SAVE RESULTS --- (Pass the aggregate_stats_df)
if portfolio is not None and best_col_name is not None:
    metrics.save_run_results(
        portfolio=portfolio, # Pass the full (potentially multi-column) portfolio
        aggregate_stats=aggregate_stats_df, # <<< PASS THE AGGREGATE STATS DF
        best_params=best_col_name,          # Pass the best combo identifier (tuple)
        config_path='config/settings.py',   # Path to the config file used
        strategy_name='rsi_threshold',      # Or derive from config/params
        symbol=SYMBOL,
        price_data_for_plots=price_data     # Pass price data for trade plot saving
    )
elif portfolio is not None:
     print("Warning: Portfolio exists but best combination not determined. Skipping saving results.")

print(f"\n--- Backtest Finished ---")