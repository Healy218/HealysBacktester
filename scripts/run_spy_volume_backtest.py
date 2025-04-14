# filename: HealysBacktester/scripts/run_spy_volume_backtest.py

import vectorbt as vbt
import pandas as pd
import numpy as np
import sys
import os
import traceback
import time # Import time module for estimating runtime

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
from signals import volume_breakout
from portfolio import simulator
from analysis import metrics, plotting
from utils import config_parser
from data import data_loader, data_cleaner

# --- Load Configuration ---
try:
    config = config_parser.load_config('config/settings.py')
    DATA_CONFIG = config.get('DATA_CONFIG', {})
    STRATEGY_CONFIG = config.get('STRATEGY_VOLUME_BREAKOUT', {})
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

# Strategy Params (Volume Breakout specific) - USING RANGES FOR ALL
VOLUME_WINDOW_START = STRATEGY_CONFIG.get('VOLUME_WINDOW_START', 30)
VOLUME_WINDOW_END = STRATEGY_CONFIG.get('VOLUME_WINDOW_END', 151)
VOLUME_WINDOW_STEP = STRATEGY_CONFIG.get('VOLUME_WINDOW_STEP', 2)
volume_window_range = np.arange(VOLUME_WINDOW_START, VOLUME_WINDOW_END, VOLUME_WINDOW_STEP)

VOLUME_MULTIPLIER_START = STRATEGY_CONFIG.get('VOLUME_MULTIPLIER_START', 1.05)
VOLUME_MULTIPLIER_END = STRATEGY_CONFIG.get('VOLUME_MULTIPLIER_END', 2.00)
VOLUME_MULTIPLIER_STEP = STRATEGY_CONFIG.get('VOLUME_MULTIPLIER_STEP', 0.05)
# Use np.linspace for float steps to avoid precision issues with np.arange
num_multiplier_steps = int(round((VOLUME_MULTIPLIER_END - VOLUME_MULTIPLIER_START) / VOLUME_MULTIPLIER_STEP)) + 1
volume_multiplier_range = np.linspace(VOLUME_MULTIPLIER_START, VOLUME_MULTIPLIER_END, num_multiplier_steps)


EXIT_MA_WINDOW_START = STRATEGY_CONFIG.get('EXIT_MA_WINDOW_START', 45)
EXIT_MA_WINDOW_END = STRATEGY_CONFIG.get('EXIT_MA_WINDOW_END', 151)
EXIT_MA_WINDOW_STEP = STRATEGY_CONFIG.get('EXIT_MA_WINDOW_STEP', 1)
exit_ma_window_range = np.arange(EXIT_MA_WINDOW_START, EXIT_MA_WINDOW_END, EXIT_MA_WINDOW_STEP)

CONFIRM_PRICE_INCREASE = STRATEGY_CONFIG.get('CONFIRM_PRICE_INCREASE', False) # Default to False if not set

# Calculate total combinations
num_combinations = len(volume_window_range) * len(volume_multiplier_range) * len(exit_ma_window_range)

# Backtest Settings (Shared)
INITIAL_CAPITAL = BACKTEST_CONFIG.get('INITIAL_CAPITAL', 100000.0)
FEES = BACKTEST_CONFIG.get('FEES_PERCENT', 0.001)
SLIPPAGE = BACKTEST_CONFIG.get('SLIPPAGE_PERCENT', 0.0005)
DEFAULT_SIZE = BACKTEST_CONFIG.get('DEFAULT_SIZE', 0.99)
DEFAULT_SIZE_TYPE = BACKTEST_CONFIG.get('DEFAULT_SIZE_TYPE', 'percent')
DEFAULT_FREQ = BACKTEST_CONFIG.get('DEFAULT_FREQ', 'D')
USE_SL = BACKTEST_CONFIG.get('USE_STOP_LOSS', False)
SL_PERCENT = BACKTEST_CONFIG.get('STOP_LOSS_PERCENT', 0.05)
USE_TP = BACKTEST_CONFIG.get('USE_TAKE_PROFIT', False)
TP_PERCENT = BACKTEST_CONFIG.get('TAKE_PROFIT_PERCENT', 0.10)

SL_STOP = SL_PERCENT if USE_SL and SL_PERCENT is not None else None
TP_STOP = TP_PERCENT if USE_TP and TP_PERCENT is not None else None


# --- Print Run Info ---
print(f"--- Starting Volume Breakout Parameter Optimization ---")
print(f"Symbol: {SYMBOL}, Period: {START_DATE} to {END_DATE} ({INTERVAL})")
print(f"Volume Window Range: {VOLUME_WINDOW_START} to {VOLUME_WINDOW_END - 1} (Step: {VOLUME_WINDOW_STEP})")
# Use .min() .max() for linspace range display
print(f"Volume Multiplier Range: {volume_multiplier_range.min():.2f} to {volume_multiplier_range.max():.2f} (Step: ~{VOLUME_MULTIPLIER_STEP})")
print(f"Exit MA Window Range: {EXIT_MA_WINDOW_START} to {EXIT_MA_WINDOW_END - 1} (Step: {EXIT_MA_WINDOW_STEP})")
print(f"Estimated Number of Combinations: {num_combinations:,}")
print(f"Require Price Increase Confirmation: {CONFIRM_PRICE_INCREASE}")
print(f"Backtest Settings: Initial Capital=${INITIAL_CAPITAL:,.2f}, Fees={FEES*100:.3f}%, Slippage={SLIPPAGE*100:.3f}%")
print(f"Sizing: Size={DEFAULT_SIZE}, Size Type='{DEFAULT_SIZE_TYPE}'")
print(f"Stop Loss: {'Enabled - ' + str(SL_STOP*100) + '%' if SL_STOP else 'Disabled'}")
print(f"Take Profit: {'Enabled - ' + str(TP_STOP*100) + '%' if TP_STOP else 'Disabled'}")

if num_combinations > 50000:
    print(f"\nWARNING: Testing a very large number of combinations ({num_combinations:,}). This will likely take considerable time and memory.")
print("-" * 35)

# --- Initialize Variables ---
price_data = None
vb_entries, vb_exits = None, None
portfolio = None
best_params = None

# --- Workflow ---
start_time = time.time() # Start timer

# 1. Load and Clean Data
print(f"\n[1/4] Loading and cleaning data for {SYMBOL}...")
load_start = time.time()
try:
    raw_data = data_loader.load_price_data(
        symbol=SYMBOL, start_date=START_DATE, end_date=END_DATE, interval=INTERVAL
    )
    if raw_data is None or raw_data.empty: raise ValueError(f"Data loading failed for {SYMBOL}.")
    if 'Volume' not in raw_data.columns:
        raise ValueError("Volume column missing from loaded data. Cannot run Volume Breakout strategy.")
    price_data = data_cleaner.clean_ohlcv_data(raw_data)
    if price_data is None or price_data.empty: raise ValueError(f"Data cleaning failed for {SYMBOL}.")
    print(f"Data loading and cleaning successful. Shape: {price_data.shape}. (Took {time.time() - load_start:.2f}s)")
except Exception as e:
    print(f"FATAL ERROR during data loading/cleaning: {e}")
    traceback.print_exc()
    exit()

# 2. Generate Volume Breakout Signals using updated module
print(f"\n[2/4] Generating Volume Breakout signals for {num_combinations:,} combinations...")
signal_start = time.time()
try:
    # Call the signal generator with the ranges
    vb_entries, vb_exits, _, _ = volume_breakout.generate_volume_signals(
        ohlcv_df=price_data,
        volume_window_range=volume_window_range,
        volume_multiplier_range=volume_multiplier_range, # Pass multiplier range
        exit_ma_window_range=exit_ma_window_range,
        confirm_price_increase=CONFIRM_PRICE_INCREASE
    )
    print(f"Signals generated. Shape: {vb_entries.shape}. (Took {time.time() - signal_start:.2f}s)")

except ImportError:
     print("FATAL ERROR: Could not import volume_breakout module.")
     exit()
except Exception as e:
    print(f"FATAL ERROR generating signals: {e}")
    traceback.print_exc()
    exit()

# 3. Run Simulation
print(f"\n[3/4] Running backtest simulation for {num_combinations:,} combinations...")
sim_start = time.time()
portfolio = None
simulation_possible = vb_entries is not None and not vb_entries.empty and vb_entries.any().any()

if simulation_possible:
    try:
        portfolio = simulator.run_backtest(
            price_df=price_data,
            entries_series=vb_entries,
            exits_series=vb_exits,
            short_entries_series=None,
            short_exits_series=None,
            initial_capital=INITIAL_CAPITAL,
            fees=FEES,
            slippage=SLIPPAGE,
            frequency=DEFAULT_FREQ,
            size=DEFAULT_SIZE,
            size_type=DEFAULT_SIZE_TYPE,
            sl_stop=SL_STOP,
            tp_stop=TP_STOP
        )
        print(f"Simulation complete. (Took {time.time() - sim_start:.2f}s)")
        if portfolio is not None:
             print(f"Portfolio object created with {len(portfolio.wrapper.columns)} columns (combinations).")
        else:
             print("Warning: Simulation finished but portfolio object is None.")
             simulation_possible = False
    except Exception as e:
        print(f"Error during simulation: {e}")
        traceback.print_exc()
        simulation_possible = False
else:
     print("Skipping simulation because no valid entry signals were generated.")


# 4. Analyze and Plot Results
print(f"\n[4/4] Analyzing results...")
analysis_start = time.time()
best_params = None

if simulation_possible and portfolio is not None:
    try:
        metric_to_optimize = 'Total Return'
        best_params = None
        best_return_value = None

        print(f"\n--- Identifying best combination based on '{metric_to_optimize}' ---")
        try:
            total_returns_series = portfolio.total_return()

            if not total_returns_series.empty:
                best_params = total_returns_series.idxmax()
                best_return_value = total_returns_series.max()
                # Format best_params before printing for readability
                if isinstance(best_params, tuple) and len(best_params) == 3:
                    # Show multiplier with 2 decimal places
                    best_params_print = f"({int(best_params[0])}, {best_params[1]:.2f}, {int(best_params[2])})"
                else:
                    best_params_print = best_params # Fallback
                print(f"Selected Best Combination Parameters: {best_params_print}")
                print(f"   Best {metric_to_optimize}: {best_return_value * 100:.2f}%")
            else:
                print("Warning: portfolio.total_return() returned an empty Series.")

        except Exception as best_e:
            print(f"Error finding best parameters using total_return(): {best_e}")
            best_params = None

        if best_params is None:
             print(f"Warning: Could not determine best parameters based on '{metric_to_optimize}'.")
             if not portfolio.wrapper.columns.empty:
                  best_params = portfolio.wrapper.columns[0]
                  print(f"Using first available combination as fallback: {best_params}")
             else:
                  print("Error: Portfolio has no columns to analyze.")


        if best_params is not None and best_params in portfolio.wrapper.columns:
            if isinstance(best_params, tuple) and len(best_params) == 3:
                 best_params_display = (int(best_params[0]), float(f"{best_params[1]:.2f}"), int(best_params[2]))
            else:
                 best_params_display = best_params

            print(f"\n--- Detailed Analysis for Best Combination {best_params_display} ---")
            best_portfolio_slice = portfolio[best_params]
            best_stats = metrics.get_summary_stats(best_portfolio_slice)

            if best_stats is not None and not best_stats.empty:
                 print("\n--- Performance Summary (Best Combination) ---")
                 print(best_stats)
                 print("\nGenerating plots for the best performing combination...")
                 try:
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
    print(f"Analysis finished. (Took {time.time() - analysis_start:.2f}s)")

# --- Save Results ---
save_start = time.time()
if portfolio is not None and best_params is not None:
     if best_params in portfolio.wrapper.columns:
        print("\n--- Saving Run Results ---")
        metrics.save_run_results(
            portfolio=portfolio,
            aggregate_stats=None,
            best_params=best_params,
            config_path='config/settings.py',
            strategy_name='volume_breakout',
            symbol=SYMBOL,
            price_data_for_plots=price_data
        )
        print(f"Saving complete. (Took {time.time() - save_start:.2f}s)")
     else:
          print(f"Warning: Best parameters {best_params} determined but not found in portfolio columns. Skipping saving results.")
elif portfolio is not None:
     print("Warning: Portfolio exists but best combination not determined. Skipping saving results.")
else:
    print("Warning: No portfolio object generated or simulation failed. Skipping saving results.")

total_time = time.time() - start_time
print(f"\n--- Backtest Finished ---")
print(f"Total execution time: {total_time:.2f} seconds ({total_time/60:.2f} minutes)")