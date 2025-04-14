# filename: HealysBacktester/scripts/run_spy_ma_backtest.py

# --- Standard Imports ---
import pandas as pd
import numpy as np
import sys
import os
import traceback
import vectorbt as vbt

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

# --- Import project modules ---
from signals import ma_crossover # Import the updated MA signal generator
from portfolio import simulator
from analysis import metrics, plotting
from utils import config_parser
from data import data_loader, data_cleaner


# --- Load Configuration ---
try:
    config = config_parser.load_config('config/settings.py') # Ensure path is correct
    DATA_CONFIG = config.get('DATA_CONFIG', {})
    # Load MA Crossover specific config
    STRATEGY_CONFIG = config.get('STRATEGY_MA_CROSSOVER', {})
    BACKTEST_CONFIG = config.get('BACKTEST_CONFIG', {})
    print(f"Configuration loaded successfully from: {os.path.join(project_root, 'config/settings.py')}")
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
DEFAULT_SIZE = BACKTEST_CONFIG.get('DEFAULT_SIZE', 0.99)
DEFAULT_SIZE_TYPE = BACKTEST_CONFIG.get('DEFAULT_SIZE_TYPE', 'percent')

# Stop Loss / Take Profit Settings
USE_SL = BACKTEST_CONFIG.get('USE_STOP_LOSS', False)
SL_PERCENT = BACKTEST_CONFIG.get('STOP_LOSS_PERCENT', None)
USE_TP = BACKTEST_CONFIG.get('USE_TAKE_PROFIT', False)
TP_PERCENT = BACKTEST_CONFIG.get('TAKE_PROFIT_PERCENT', None)

# Determine SL/TP values to pass
sl_stop_value = SL_PERCENT if USE_SL and SL_PERCENT is not None else None
tp_stop_value = TP_PERCENT if USE_TP and TP_PERCENT is not None else None

# MA Crossover Strategy Parameters (from STRATEGY_MA_CROSSOVER section)
MA_WINDOW_START = STRATEGY_CONFIG.get('MA_WINDOW_START', 2)
MA_WINDOW_END = STRATEGY_CONFIG.get('MA_WINDOW_END', 101) # Default to 100 if not set
MA_WINDOW_STEP = STRATEGY_CONFIG.get('MA_WINDOW_STEP', 1)

# Create the window range array
windows_range = np.arange(MA_WINDOW_START, MA_WINDOW_END, MA_WINDOW_STEP)
if windows_range.size < 2:
    print(f"FATAL ERROR: Window range defined in settings ({MA_WINDOW_START} to {MA_WINDOW_END-1}) is too small for dual MA combinations.")
    exit()

num_combinations = windows_range.size * (windows_range.size - 1) // 2


# --- Print Run Info ---
print(f"\n--- Starting MA Crossover Parameter Optimization (vectorbt) ---")
print(f"Symbol: {SYMBOL}, Period: {START_DATE} to {END_DATE} ({INTERVAL})")
print(f"MA Window Range for Combinations: {MA_WINDOW_START} to {MA_WINDOW_END - 1}")
print(f"Estimated Number of Combinations (short < long): {num_combinations}")
print(f"Backtest Settings: Initial Capital=${INITIAL_CAPITAL:,.2f}, Fees={FEES:.3%}, Slippage={SLIPPAGE:.3%}")
print(f"Sizing: Size={DEFAULT_SIZE}, Size Type='{DEFAULT_SIZE_TYPE}'")
print(f"Stop Loss: {'Enabled' if sl_stop_value else 'Disabled'}{f' ({SL_PERCENT:.1%})' if sl_stop_value else ''}")
print(f"Take Profit: {'Enabled' if tp_stop_value else 'Disabled'}{f' ({TP_PERCENT:.1%})' if tp_stop_value else ''}")
print("-" * 35)

# --- Initialize Variables ---
price_data = None
entries, exits = None, None
portfolio = None
best_params = None # Use tuple (fast_window, slow_window)

# --- Workflow ---

# 1. Load and Clean Data using Modules
print(f"\n[1/4] Loading and cleaning data for {SYMBOL}...")
try:
    raw_data = data_loader.load_price_data(
        symbol=SYMBOL, start_date=START_DATE, end_date=END_DATE, interval=INTERVAL
    )
    if raw_data is None or raw_data.empty: raise ValueError(f"Data loading failed for {SYMBOL}.")
    price_data = data_cleaner.clean_ohlcv_data(raw_data)
    if price_data is None or price_data.empty: raise ValueError(f"Data cleaning failed for {SYMBOL}.")
    print(f"Data loading and cleaning successful. Final shape: {price_data.shape}")
except Exception as e:
    print(f"FATAL ERROR during data loading/cleaning: {e}")
    traceback.print_exc()
    exit()

# 2. Generate MA Crossover Signals using the updated module
print(f"\n[2/4] Generating MA Crossover signals using vectorbt combinations...")
try:
    # Call the updated signal generator
    entries, exits = ma_crossover.generate_ma_signals(
        close_prices_series=price_data['Close'],
        windows_range=windows_range
    )
    print("MA Crossover signals generated.")
    if isinstance(entries, pd.DataFrame): print(f"Entries/Exits Shape: {entries.shape}")

except ImportError:
     print("FATAL ERROR: Could not import ma_crossover module from signals.")
     exit()
except Exception as e:
    print(f"FATAL ERROR generating signals: {e}")
    traceback.print_exc()
    exit()

# 3. Run Simulation
print(f"\n[3/4] Running backtest simulation...")
portfolio = None
# Check if any entry signals were generated
simulation_possible = entries is not None and not entries.empty and entries.any().any()

if simulation_possible:
    try:
        portfolio = simulator.run_backtest(
            price_df=price_data,
            entries_series=entries,
            exits_series=exits,
            # No short signals for this strategy currently
            short_entries_series=None,
            short_exits_series=None,
            # Pass other backtest settings
            initial_capital=INITIAL_CAPITAL,
            fees=FEES,
            slippage=SLIPPAGE,
            frequency=DEFAULT_FREQ,
            size=DEFAULT_SIZE,
            size_type=DEFAULT_SIZE_TYPE,
            sl_stop=sl_stop_value,
            tp_stop=tp_stop_value
        )
        print("Simulation complete.")
        if portfolio is not None:
            print(f"Portfolio object created with {len(portfolio.wrapper.columns)} columns (combinations).")
        else:
            print("Warning: Simulation finished but portfolio object is None.")
            simulation_possible = False # Prevent further analysis if portfolio is None

    except Exception as e:
        print(f"Error during simulation: {e}")
        traceback.print_exc()
        simulation_possible = False # Prevent further analysis
else:
     print("Skipping simulation because no valid entry signals were generated.")


# 4. Analyze Results (Find best combination) and Plot
print(f"\n[4/4] Analyzing results...")
best_params = None
# Removed aggregate_stats_df initialization here, as we calculate it differently now

if simulation_possible and portfolio is not None:
    try:
        # --- Identify Best Combination using portfolio.total_return() ---
        metric_to_optimize = 'Total Return' # Use the metric name as returned by portfolio.total_return()
        best_params = None
        best_return_value = None

        print(f"\n--- Identifying best combination based on '{metric_to_optimize}' ---")
        try:
            # Calculate total return for ALL combinations
            total_returns_series = portfolio.total_return() # Returns a Series indexed by the columns (param combinations)

            if not total_returns_series.empty:
                best_params = total_returns_series.idxmax() # Get the index (column name tuple) of the max value
                best_return_value = total_returns_series.max() # Get the max value itself

                print(f"Selected Best Combination Parameters: {best_params}")
                # Note: total_return is decimal, multiply by 100 for percentage
                print(f"   Best {metric_to_optimize}: {best_return_value * 100:.2f}%")
            else:
                print("Warning: portfolio.total_return() returned an empty Series.")

        except Exception as best_e:
            print(f"Error finding best parameters using total_return(): {best_e}")
            best_params = None # Ensure best_params is None if error occurs

        # --- Fallback if best parameters couldn't be found ---
        if best_params is None:
             print(f"Warning: Could not determine best parameters based on '{metric_to_optimize}'.")
             if not portfolio.wrapper.columns.empty:
                  best_params = portfolio.wrapper.columns[0]
                  print(f"Using first available combination as fallback: {best_params}")
             else:
                  print("Error: Portfolio has no columns to analyze.")


        # --- Analyze and Plot details for BEST Combination ---
        if best_params is not None and best_params in portfolio.wrapper.columns:
            print(f"\n--- Detailed Analysis for Best Combination {best_params} ---")
            best_portfolio_slice = portfolio[best_params] # Select the best column
            best_stats = metrics.get_summary_stats(best_portfolio_slice) # Get stats for the single best slice

            if best_stats is not None and not best_stats.empty:
                 print("\n--- Performance Summary (Best Combination) ---")
                 print(best_stats) # Print the detailed stats Series

                 # Plotting for the best combination
                 print("\nGenerating plots for the best performing combination...")
                 try:
                     # Pass the single-column portfolio slice to plotting functions
                     plotting.plot_portfolio_summary(best_portfolio_slice)
                     plotting.plot_trades(best_portfolio_slice, price_data)
                     print("Plots generated for best combination.")
                 except AttributeError:
                      print("ERROR: Plotting functions not found or incorrect in analysis.plotting.")
                 except Exception as plot_err:
                      print(f"ERROR generating plots for best combination: {plot_err}")
            else:
                 print("Could not retrieve detailed stats for the best combination.")

            best_trades_df = metrics.get_trade_records(best_portfolio_slice)
            if best_trades_df is not None and not best_trades_df.empty:
                print("\n--- Trade Records (Best Combination - First 5) ---")
                print(best_trades_df.head())
                print(f"Total trades for best combination: {len(best_trades_df)}")
            elif best_portfolio_slice.trades.count() > 0:
                 print("\nPortfolio object indicates trades for best combo, but fetching failed.")
            else:
                 print("\nNo trades were executed for the best combination.")
        else:
            print(f"\nSkipping detailed analysis as no valid best parameters ({best_params}) could be determined or found in portfolio.")

    except Exception as e:
        print(f"ERROR during analysis: {e}")
        traceback.print_exc()

# --- Save Results ---
# We don't have the aggregate_stats_df calculated in the same way anymore.
# We will pass aggregate_stats=None to the save function.
# The save function should already be saving the stats and trades for the 'best_params' slice separately.
if portfolio is not None and best_params is not None:
     if best_params in portfolio.wrapper.columns:
        print("\n--- Saving Run Results ---")
        metrics.save_run_results(
            portfolio=portfolio,                # Pass full portfolio object (contains all combos)
            aggregate_stats=None,               # Pass None for aggregate stats
            best_params=best_params,            # Pass the best combination identifier (tuple)
            config_path='config/settings.py',
            strategy_name='ma_crossover',       # Strategy name
            symbol=SYMBOL,
            price_data_for_plots=price_data     # Pass price data for saving trade plot
        )
     else:
          print(f"Warning: Best parameters {best_params} determined but not found in portfolio columns. Skipping saving results.")
elif portfolio is not None:
     print("Warning: Portfolio exists but best combination not determined. Skipping saving results.")
else:
    print("Warning: No portfolio object generated or simulation failed. Skipping saving results.")


print(f"\n--- Backtest Finished ---")