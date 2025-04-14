# scripts/run_spy_rsi_backtest.py

import vectorbt as vbt
import pandas as pd
import numpy as np
import sys
import os
import traceback # Import traceback for detailed error printing
import time # Import time module for estimating runtime
# from itertools import product # No longer needed
from typing import Optional, Union, Tuple, Any # For type hints

# --- Add Project Root to Python Path ---
# (Keep Path Modification as is)
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    if project_root not in sys.path: sys.path.insert(0, str(project_root))
except NameError:
    print("Warning: Could not determine script directory."); project_root = '.'
    if project_root not in sys.path: sys.path.insert(0, str(project_root))

# --- Import necessary modules ---
# (Keep Imports as is)
from signals import rsi_threshold
from portfolio import simulator
from analysis import metrics, plotting
from utils import config_parser
from data import data_loader, data_cleaner

# --- Load Configuration ---
# (Keep Config Loading as is)
try:
    config = config_parser.load_config('config/settings.py')
    DATA_CONFIG = config.get('DATA_CONFIG', {})
    STRATEGY_CONFIG = config.get('STRATEGY_RSI', {})
    BACKTEST_CONFIG = config.get('BACKTEST_CONFIG', {})
    print(f"Configuration loaded successfully from: {os.path.join(project_root, 'config/settings.py')}")
except FileNotFoundError: print("FATAL ERROR: Config file not found."); exit()
except Exception as e: print(f"FATAL ERROR loading config: {e}"); exit()

# --- Extract Parameters ---
# (Keep Parameter Extraction as is)
SYMBOL = DATA_CONFIG.get('SYMBOL', 'SPY')
START_DATE = DATA_CONFIG.get('START_DATE', '2020-01-01')
END_DATE = DATA_CONFIG.get('END_DATE', '2023-12-31')
INTERVAL = DATA_CONFIG.get('INTERVAL', '1D')
RSI_WINDOW_START = STRATEGY_CONFIG.get('RSI_WINDOW_START', 10)
RSI_WINDOW_END = STRATEGY_CONFIG.get('RSI_WINDOW_END', 31)
RSI_WINDOW_STEP = STRATEGY_CONFIG.get('RSI_WINDOW_STEP', 1)
rsi_window_range = np.arange(RSI_WINDOW_START, RSI_WINDOW_END, RSI_WINDOW_STEP, dtype=int)
ENTRY_THRESHOLD_START = STRATEGY_CONFIG.get('ENTRY_THRESHOLD_START', 20.0)
ENTRY_THRESHOLD_END = STRATEGY_CONFIG.get('ENTRY_THRESHOLD_END', 40.0)
ENTRY_THRESHOLD_STEP = STRATEGY_CONFIG.get('ENTRY_THRESHOLD_STEP', 1.0)
num_entry_steps = max(1, int(round((ENTRY_THRESHOLD_END - ENTRY_THRESHOLD_START) / ENTRY_THRESHOLD_STEP)) + 1)
entry_threshold_range = np.linspace(ENTRY_THRESHOLD_START, ENTRY_THRESHOLD_END, num_entry_steps)
EXIT_THRESHOLD_START = STRATEGY_CONFIG.get('EXIT_THRESHOLD_START', 60.0)
EXIT_THRESHOLD_END = STRATEGY_CONFIG.get('EXIT_THRESHOLD_END', 80.0)
EXIT_THRESHOLD_STEP = STRATEGY_CONFIG.get('EXIT_THRESHOLD_STEP', 1.0)
num_exit_steps = max(1, int(round((EXIT_THRESHOLD_END - EXIT_THRESHOLD_START) / EXIT_THRESHOLD_STEP)) + 1)
exit_threshold_range = np.linspace(EXIT_THRESHOLD_START, EXIT_THRESHOLD_END, num_exit_steps)
ENABLE_SHORTING = BACKTEST_CONFIG.get('ENABLE_SHORTING', False)
short_entry_threshold_range = None # Simplified for brevity, assume None or loaded as before
short_exit_threshold_range = None  # Simplified for brevity, assume None or loaded as before
final_param_names = ['entry_threshold', 'rsi_window', 'exit_threshold'] # Corrected order
num_combinations = len(rsi_window_range) * len(entry_threshold_range) * len(exit_threshold_range) # Simplified
INITIAL_CAPITAL = BACKTEST_CONFIG.get('INITIAL_CAPITAL', 100000.0); FEES = BACKTEST_CONFIG.get('FEES_PERCENT', 0.001)
SLIPPAGE = BACKTEST_CONFIG.get('SLIPPAGE_PERCENT', 0.0005); DEFAULT_SIZE = BACKTEST_CONFIG.get('DEFAULT_SIZE', 0.99)
DEFAULT_SIZE_TYPE = BACKTEST_CONFIG.get('DEFAULT_SIZE_TYPE', 'percent'); DEFAULT_FREQ = BACKTEST_CONFIG.get('DEFAULT_FREQ', 'D')
USE_SL = BACKTEST_CONFIG.get('USE_STOP_LOSS', False); SL_PERCENT = BACKTEST_CONFIG.get('STOP_LOSS_PERCENT', 0.05)
USE_TP = BACKTEST_CONFIG.get('USE_TAKE_PROFIT', False); TP_PERCENT = BACKTEST_CONFIG.get('TAKE_PROFIT_PERCENT', 0.10)
SL_STOP = SL_PERCENT if USE_SL else None; TP_STOP = TP_PERCENT if USE_TP else None

# --- Helper function to format parameter tuples ---
# (Keep Formatter function as is)
def format_param_tuple(param_tuple: Union[Tuple[Any, ...], Any], actual_names: list[str]) -> str:
    if not isinstance(param_tuple, tuple):
        if actual_names and len(actual_names) == 1: return f"({actual_names[0]}={param_tuple})"
        else: return str(param_tuple)
    num_params = len(param_tuple); names_to_use = actual_names[:num_params]; formatted_params = []
    for i, val in enumerate(param_tuple):
        name = names_to_use[i] if i < len(names_to_use) else f"param_{i}"
        if "window" in name.lower():
             try: formatted_params.append(f"{name}={int(float(val))}")
             except: formatted_params.append(f"{name}={val}")
        elif "thresh" in name.lower():
             try: formatted_params.append(f"{name}={float(val):.2f}")
             except: formatted_params.append(f"{name}={val}")
        else: formatted_params.append(f"{name}={val}")
    return f"({', '.join(formatted_params)})"

# --- Print Run Info ---
# (Keep Print section as is)
print(f"--- Starting RSI Threshold Parameter Optimization ---"); print(f"Symbol: {SYMBOL}, Period: {START_DATE} to {END_DATE} ({INTERVAL})")
print(f"RSI Window Range: {RSI_WINDOW_START} to {rsi_window_range[-1]} (Step: {RSI_WINDOW_STEP})")
print(f"Long Entry Threshold Range: {entry_threshold_range.min():.2f} to {entry_threshold_range.max():.2f} (Steps: {len(entry_threshold_range)})")
print(f"Long Exit Threshold Range: {exit_threshold_range.min():.2f} to {exit_threshold_range.max():.2f} (Steps: {len(exit_threshold_range)})")
print(f"Shorting Enabled: {ENABLE_SHORTING}") # Simplified short printout
print(f"Input Parameter Combinations: {num_combinations:,}")
print(f"Backtest Settings: Initial Capital=${INITIAL_CAPITAL:,.2f}, Fees={FEES*100:.3f}%, Slippage={SLIPPAGE*100:.3f}%")
print(f"Sizing: Size={DEFAULT_SIZE}, Size Type='{DEFAULT_SIZE_TYPE}'")
print(f"Stop Loss: {'Enabled - ' + str(SL_STOP*100) + '%' if SL_STOP else 'Disabled'}")
print(f"Take Profit: {'Enabled - ' + str(TP_STOP*100) + '%' if TP_STOP else 'Disabled'}")
if num_combinations > 50000: print(f"\nWARNING: Testing a very large number of combinations ({num_combinations:,}).")
print("-" * 35)


# --- Initialize Variables ---
price_data = None; entries, exits, short_entries, short_exits = None, None, None, None
portfolio = None; best_params_for_saving = None; actual_portfolio_param_names = None
overall_start_time = time.time()

# 1. Load and Clean Data
# (Keep data loading section as is)
print(f"\n[1/4] Loading and cleaning data for {SYMBOL}...")
load_start = time.time()
try:
    raw_data = data_loader.load_price_data(symbol=SYMBOL, start_date=START_DATE, end_date=END_DATE, interval=INTERVAL)
    if raw_data is None or raw_data.empty: raise ValueError(f"Data loading failed.")
    price_data = data_cleaner.clean_ohlcv_data(raw_data)
    if price_data is None or price_data.empty: raise ValueError(f"Data cleaning failed.")
    print(f"Data loading successful. Shape: {price_data.shape}. (Took {time.time() - load_start:.2f}s)")
except Exception as e: print(f"FATAL ERROR loading/cleaning: {e}"); traceback.print_exc(); exit()

# 2. Generate Signals
# (Keep signal generation section as is)
print(f"\n[2/4] Generating signals ({num_combinations:,} input combos, Shorting: {ENABLE_SHORTING})...")
signal_start = time.time()
try:
    entries, exits, short_entries, short_exits = rsi_threshold.generate_rsi_signals(
        close_prices_series=price_data['Close'], window=rsi_window_range, entry_threshold=entry_threshold_range,
        exit_threshold=exit_threshold_range, enable_shorting=ENABLE_SHORTING,
        short_entry_threshold=short_entry_threshold_range, short_exit_threshold=short_exit_threshold_range)
    print(f"Signals generated. (Took {time.time() - signal_start:.2f}s)")
except ImportError: print("FATAL ERROR: Import failed."); exit()
except Exception as e: print(f"FATAL ERROR generating signals: {e}"); traceback.print_exc(); exit()

# 3. Run Simulation
# (Keep simulation section as is)
print(f"\n[3/4] Running backtest simulation...")
sim_start = time.time()
portfolio = None; simulation_possible = False
if entries is not None and not entries.empty: simulation_possible = True
if ENABLE_SHORTING and short_entries is not None and not short_entries.empty: simulation_possible = True
if simulation_possible:
    try:
        portfolio = simulator.run_backtest(price_df=price_data, entries_series=entries, exits_series=exits, short_entries_series=short_entries, short_exits_series=short_exits,
            initial_capital=INITIAL_CAPITAL, fees=FEES, slippage=SLIPPAGE, frequency=DEFAULT_FREQ, size=DEFAULT_SIZE, size_type=DEFAULT_SIZE_TYPE,
            sl_stop=SL_STOP, tp_stop=TP_STOP)
        print(f"Simulation complete. (Took {time.time() - sim_start:.2f}s)")
        if portfolio is not None:
             num_simulated_combos = len(portfolio.wrapper.columns)
             print(f"Portfolio created with {num_simulated_combos} columns.")
             if num_simulated_combos > 0:
                 actual_portfolio_param_names = list(portfolio.wrapper.columns.names) # Get actual names
                 print(f"Portfolio column index name(s): {actual_portfolio_param_names}")
                 print(f"Example column index: {portfolio.wrapper.columns[0]}")
             else: simulation_possible = False
        else: print("Warning: Sim finished but portfolio is None."); simulation_possible = False
    except Exception as e: print(f"Error during simulation: {e}"); traceback.print_exc(); simulation_possible = False
else: print("Skipping simulation: no valid entry signals.")


# 4. Analyze Results - Logic updated for stats() structure
print(f"\n[4/4] Analyzing results...")
analysis_start = time.time()
best_params_for_saving = None

if simulation_possible and portfolio is not None:
    try:
        print(f"\n--- Identifying Top Combinations using portfolio.stats(agg_func=None) ---")

        # Get the full stats table (Metrics=Columns, Combos=Index)
        all_stats_df = portfolio.stats(agg_func=None)

        if all_stats_df.empty:
            print("Error: portfolio.stats(agg_func=None) returned an empty DataFrame.")
        else:
            # Use actual parameter names identified after simulation for formatting
            param_names_for_fmt = actual_portfolio_param_names if actual_portfolio_param_names else final_param_names

            # --- Find Best Total Return ---
            metric_col_name = 'Total Return [%]' # Use exact name from stats df columns
            if metric_col_name in all_stats_df.columns:
                try:
                    metric_series = all_stats_df[metric_col_name] # Select COLUMN by name
                    best_return_params = metric_series.idxmax()   # Get INDEX tuple (params)
                    best_return_value = metric_series.loc[best_return_params]
                    print(f"Best {metric_col_name}: {best_return_value:.2f}%")
                    print(f"   Params: {format_param_tuple(best_return_params, param_names_for_fmt)}")
                    best_params_for_saving = best_return_params
                except Exception as e:
                    print(f"Could not determine best for {metric_col_name}: {e}")
                    traceback.print_exc()
            else:
                print(f"Metric '{metric_col_name}' not found. Available: {list(all_stats_df.columns)}")


            # --- Find Best Total Trades ---
            metric_col_name = 'Total Trades'
            if metric_col_name in all_stats_df.columns:
                try:
                    metric_series = all_stats_df[metric_col_name]
                    best_trades_params = metric_series.idxmax()
                    best_trades_value = metric_series.loc[best_trades_params]
                    print(f"Most {metric_col_name}: {int(best_trades_value)}")
                    print(f"   Params: {format_param_tuple(best_trades_params, param_names_for_fmt)}")
                except Exception as e:
                    print(f"Could not determine best for {metric_col_name}: {e}")
            else:
                print(f"Metric '{metric_col_name}' not found.")


            # --- Find Best Sharpe Ratio ---
            metric_col_name = 'Sharpe Ratio'
            if metric_col_name in all_stats_df.columns:
                try:
                     metric_series = all_stats_df[metric_col_name]
                     sharpe_cleaned = metric_series.replace([np.inf, -np.inf], np.nan)
                     if not sharpe_cleaned.dropna().empty:
                         best_sharpe_params = sharpe_cleaned.idxmax()
                         best_sharpe_value = sharpe_cleaned.loc[best_sharpe_params]
                         print(f"Best {metric_col_name}: {best_sharpe_value:.3f}")
                         print(f"   Params: {format_param_tuple(best_sharpe_params, param_names_for_fmt)}")
                     else: print(f"No valid values for {metric_col_name}.")
                except Exception as e:
                     print(f"Could not determine best for {metric_col_name}: {e}")
            else:
                 print(f"Metric '{metric_col_name}' not found.")


        # --- Detailed Analysis for BEST RETURN Combination ---
        # (Keep detailed analysis section logic as is, uses best_params_for_saving)
        if best_params_for_saving is not None:
            if best_params_for_saving not in portfolio.wrapper.columns:
                 print(f"\nError: Best return params '{best_params_for_saving}' not valid.")
                 best_params_for_saving = None
            else:
                param_names_for_fmt_detail = actual_portfolio_param_names if actual_portfolio_param_names else final_param_names
                best_return_params_str = format_param_tuple(best_params_for_saving, param_names_for_fmt_detail)
                print(f"\n--- Detailed Analysis for Best *Return* Combination {best_return_params_str} ---")
                best_portfolio_slice = portfolio[best_params_for_saving]
                best_stats_summary = metrics.get_summary_stats(best_portfolio_slice)
                if best_stats_summary is not None and not best_stats_summary.empty: print("\n--- Performance Summary ---\n", best_stats_summary)
                else: print("Could not retrieve summary stats.")
                best_trades_df = metrics.get_trade_records(best_portfolio_slice)
                if best_trades_df is not None and not best_trades_df.empty:
                    print("\n--- Trade Records (First 5) ---\n", best_trades_df.head())
                    print(f"Total trades: {len(best_trades_df)}")
                elif best_portfolio_slice.trades.count() > 0: print(f"\nTrades exist but fetching failed.")
                else: print(f"\nNo trades were executed.")
        else: print("\nSkipping detailed analysis: No best return combo found.")

    except Exception as e:
        print(f"ERROR during analysis phase: {e}")
        traceback.print_exc()

    print(f"Analysis finished. (Took {time.time() - analysis_start:.2f}s)")

# --- SAVE RESULTS ---
# (Keep saving section as is, uses best_params_for_saving)
save_start = time.time()
if portfolio is not None and best_params_for_saving is not None:
     if best_params_for_saving in portfolio.wrapper.columns:
        print("\n--- Saving Run Results ---")
        metrics.save_run_results(portfolio=portfolio, aggregate_stats=None, best_params=best_params_for_saving, config_path='config/settings.py',
            strategy_name='rsi_threshold_optimized', symbol=SYMBOL, price_data_for_plots=price_data)
        print(f"Saving complete. (Took {time.time() - save_start:.2f}s)")
     else: print(f"Warning: Best params {best_params_for_saving} invalid. Skipping save.")
elif portfolio is not None: print("Warning: Best combo not determined. Skipping save.")
else: print("Warning: No portfolio. Skipping save.")

total_time = time.time() - overall_start_time
print(f"\n--- Backtest Finished ---")
print(f"Total execution time: {total_time:.2f} seconds ({total_time/60:.2f} minutes)")