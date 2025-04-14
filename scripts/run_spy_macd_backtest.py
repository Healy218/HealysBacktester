# scripts/run_spy_macd_backtest.py

import vectorbt as vbt
import pandas as pd
import numpy as np
import sys
import os
import traceback
import time # For timing
import warnings # Import warnings

# --- Add Project Root to Python Path ---
# (Keep Path Modification as is)
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    if project_root not in sys.path: sys.path.insert(0, str(project_root))
except NameError:
    print("Warning: Could not determine script directory automatically."); project_root = '.'
    if project_root not in sys.path: sys.path.insert(0, str(project_root))

# --- Import necessary modules ---
from signals import macd_signals
from portfolio import simulator
from analysis import metrics, plotting
from utils import config_parser
from data import data_loader, data_cleaner

# --- Load Configuration ---
# (Keep Config Loading as is)
try:
    config = config_parser.load_config('config/settings.py')
    DATA_CONFIG = config.get('DATA_CONFIG', {})
    STRATEGY_CONFIG = config.get('STRATEGY_MACD', {})
    BACKTEST_CONFIG = config.get('BACKTEST_CONFIG', {})
    print(f"Configuration loaded successfully from: {os.path.join(project_root, 'config/settings.py')}")
except FileNotFoundError: print("FATAL ERROR: Configuration file 'config/settings.py' not found."); exit()
except Exception as e: print(f"FATAL ERROR: Could not load configuration: {e}"); exit()


# --- Extract Parameters ---
# (Keep Parameter Extraction as is)
SYMBOL = DATA_CONFIG.get('SYMBOL', 'SPY')
START_DATE = DATA_CONFIG.get('START_DATE', '2020-01-01')
END_DATE = DATA_CONFIG.get('END_DATE', '2023-12-31')
INTERVAL = DATA_CONFIG.get('INTERVAL', '1D')

try:
    fast_start = STRATEGY_CONFIG.get('FAST_WINDOW_START', 10)
    fast_end = STRATEGY_CONFIG.get('FAST_WINDOW_END', 21)
    fast_step = STRATEGY_CONFIG.get('FAST_WINDOW_STEP', 1)
    fast_windows = np.arange(fast_start, fast_end, fast_step, dtype=int)
    if len(fast_windows) == 0: raise ValueError("Fast window range resulted in empty array.")

    slow_start = STRATEGY_CONFIG.get('SLOW_WINDOW_START', 20)
    slow_end = STRATEGY_CONFIG.get('SLOW_WINDOW_END', 51)
    slow_step = STRATEGY_CONFIG.get('SLOW_WINDOW_STEP', 1)
    slow_windows = np.arange(slow_start, slow_end, slow_step, dtype=int)
    if len(slow_windows) == 0: raise ValueError("Slow window range resulted in empty array.")

    signal_start = STRATEGY_CONFIG.get('SIGNAL_WINDOW_START', 5)
    signal_end = STRATEGY_CONFIG.get('SIGNAL_WINDOW_END', 16)
    signal_step = STRATEGY_CONFIG.get('SIGNAL_WINDOW_STEP', 1)
    signal_windows = np.arange(signal_start, signal_end, signal_step, dtype=int)
    if len(signal_windows) == 0: raise ValueError("Signal window range resulted in empty array.")

except KeyError as e: print(f"FATAL ERROR: Missing MACD range parameter in settings.py: {e}"); exit()
except ValueError as e: print(f"FATAL ERROR: Invalid MACD range parameter in settings.py: {e}"); exit()

num_combinations = len(fast_windows) * len(slow_windows) * len(signal_windows)
ENABLE_MACD_SHORTS = STRATEGY_CONFIG.get('SHORT_ENTRIES_ENABLED', False)
ENABLE_MACD_SHORT_EXITS = STRATEGY_CONFIG.get('SHORT_EXITS_ENABLED', False)
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
SL_STOP = SL_PERCENT if USE_SL else None
TP_STOP = TP_PERCENT if USE_TP else None

# --- Print Run Info ---
# (Keep Print Run Info as is)
print(f"--- Starting MACD Crossover Backtest (Optimized) ---")
print(f"Symbol: {SYMBOL}, Period: {START_DATE} to {END_DATE} ({INTERVAL})")
print(f"Strategy Params (Ranges):")
print(f"  Fast Window: {fast_start}-{fast_end-1} (Step: {fast_step}) -> {len(fast_windows)} values")
print(f"  Slow Window: {slow_start}-{slow_end-1} (Step: {slow_step}) -> {len(slow_windows)} values")
print(f"  Signal Window: {signal_start}-{signal_end-1} (Step: {signal_step}) -> {len(signal_windows)} values")
print(f"Total Parameter Combinations (theoretically): {num_combinations:,}")
print(f"Note: vectorbt automatically generates combinations. Invalid ones (fast >= slow) might result in NaNs or be excluded.")
print(f"Backtest Settings: Initial Capital=${INITIAL_CAPITAL:,.2f}, Fees={FEES*100:.3f}%, Slippage={SLIPPAGE*100:.3f}%")
print(f"Sizing: Size={DEFAULT_SIZE}, Size Type='{DEFAULT_SIZE_TYPE}'")
print(f"Stop Loss: {'Enabled - ' + str(SL_STOP*100) + '%' if SL_STOP else 'Disabled'}")
print(f"Take Profit: {'Enabled - ' + str(TP_STOP*100) + '%' if TP_STOP else 'Disabled'}")
print(f"MACD Shorting Enabled: {ENABLE_MACD_SHORTS}")
print("-" * 35)

# --- Initialize Variables ---
# (Keep Initialization as is)
price_data = None
entries, exits, short_entries, short_exits = None, None, None, None
portfolio = None
best_col_name = None
overall_start_time = time.time()


# --- Workflow ---

# 1. Load and Clean Data
# (Keep Data Loading as is)
print(f"\n[1/4] Loading and cleaning data for {SYMBOL}...")
load_start = time.time()
try:
    raw_data = data_loader.load_price_data(symbol=SYMBOL, start_date=START_DATE, end_date=END_DATE, interval=INTERVAL)
    if raw_data is None or raw_data.empty: raise ValueError(f"Data loading failed for {SYMBOL}.")
    price_data = data_cleaner.clean_ohlcv_data(raw_data)
    if price_data is None or price_data.empty: raise ValueError(f"Data cleaning failed for {SYMBOL}.")
    print(f"Data loading and cleaning successful. Final shape: {price_data.shape}. (Took {time.time() - load_start:.2f}s)")
except Exception as e: print(f"FATAL ERROR during data loading/cleaning: {e}"); traceback.print_exc(); exit()


# 2. Generate MACD Signals
# (Keep Signal Generation as is)
print(f"\n[2/4] Generating MACD signals using parameter ranges (Shorting: {ENABLE_MACD_SHORTS})...")
signal_start = time.time()
try:
    entries, exits, short_entries, short_exits = macd_signals.generate_macd_signals(
        close_prices_series=price_data['Close'],
        fast_window=fast_windows,
        slow_window=slow_windows,
        signal_window=signal_windows,
        short_entries=ENABLE_MACD_SHORTS,
        short_exits=ENABLE_MACD_SHORT_EXITS
    )
    print(f"Signals generated. (Took {time.time() - signal_start:.2f}s)")
    if isinstance(entries, pd.DataFrame): print(f"Long Entries Shape: {entries.shape}")
    if ENABLE_MACD_SHORTS and short_entries is not None:
        print(f"Short Entries Shape: {short_entries.shape}")

except ImportError: print("FATAL ERROR: Could not import macd_signals module."); exit()
except Exception as e: print(f"FATAL ERROR generating signals: {e}"); traceback.print_exc(); exit()


# 3. Run Simulation
print(f"\n[3/4] Running backtest simulation...")
sim_start = time.time()
portfolio = None
simulation_possible = False
long_entries_exist = entries is not None and not entries.empty and entries.any().any()
short_entries_exist = False
if ENABLE_MACD_SHORTS and short_entries is not None and not short_entries.empty:
    short_entries_exist = short_entries.any().any()

simulation_possible = long_entries_exist or short_entries_exist

if simulation_possible:
    try:
        # --- MODIFIED CALL: Removed broadcast_named_kwargs ---
        portfolio = simulator.run_backtest(
            price_df=price_data,
            entries_series=entries,
            exits_series=exits,
            short_entries_series=short_entries,
            short_exits_series=short_exits,
            initial_capital=INITIAL_CAPITAL,
            fees=FEES,
            slippage=SLIPPAGE,
            frequency=DEFAULT_FREQ,
            size=DEFAULT_SIZE,
            size_type=DEFAULT_SIZE_TYPE,
            sl_stop=SL_STOP,
            tp_stop=TP_STOP
            # broadcast_named_kwargs removed
        )
        # --- End Modification ---

        print(f"Simulation complete. (Took {time.time() - sim_start:.2f}s)")
        if portfolio is not None and hasattr(portfolio.wrapper, 'columns'):
             print(f"Portfolio created with {len(portfolio.wrapper.columns)} parameter combinations.")
             if len(portfolio.wrapper.columns) == 0:
                 print("Warning: Simulation ran but resulted in 0 portfolio columns.")
                 simulation_possible = False
        else:
             print("Warning: Simulation finished but portfolio object is None or invalid.")
             simulation_possible = False

    except Exception as e:
        print(f"Error during simulation: {e}")
        traceback.print_exc()
        simulation_possible = False
else:
     print("Skipping simulation because no valid entry signals were generated.")


# 4. Analyze and Plot Results
# (Keep Analysis and Saving as is)
print(f"\n[4/4] Analyzing results...")
analysis_start = time.time()
best_col_name = None
aggregate_stats_df = None

if simulation_possible and portfolio is not None and not portfolio.wrapper.columns.empty:
    try:
        print("Calculating aggregate performance stats across all combinations...")
        try:
            all_stats_df = portfolio.stats(agg_func=None)
            if isinstance(all_stats_df, pd.DataFrame) and not all_stats_df.empty:
                aggregate_stats_df = all_stats_df
                print(f"Aggregate stats calculated. Shape: {aggregate_stats_df.shape}")

                original_combo_count = len(aggregate_stats_df)
                if isinstance(aggregate_stats_df.index, pd.MultiIndex) and \
                   all(name in aggregate_stats_df.index.names for name in ['fast_window', 'slow_window']):
                    valid_mask = aggregate_stats_df.index.get_level_values('fast_window') < aggregate_stats_df.index.get_level_values('slow_window')
                    aggregate_stats_df = aggregate_stats_df[valid_mask]
                    print(f"Filtered out {original_combo_count - len(aggregate_stats_df)} combinations where fast_window >= slow_window.")
                else:
                     warnings.warn("Could not filter fast >= slow: Index is not the expected MultiIndex.")

            else:
                 print("Warning: portfolio.stats(agg_func=None) did not return a valid DataFrame.")
                 aggregate_stats_df = None

        except Exception as agg_e:
            print(f"Warning: Could not generate aggregate stats table: {agg_e}")
            traceback.print_exc()
            aggregate_stats_df = None

        metric_to_optimize = 'Total Return [%]'
        print(f"\n--- Identifying best combination based on '{metric_to_optimize}' (after filtering) ---")

        if aggregate_stats_df is not None and not aggregate_stats_df.empty and metric_to_optimize in aggregate_stats_df.columns:
            metric_series = aggregate_stats_df[metric_to_optimize].astype(float)
            if not metric_series.dropna().empty:
                 best_col_name = metric_series.idxmax()
                 best_metric_value = metric_series.loc[best_col_name]
                 print(f"Selected Best Combination Parameters: {best_col_name}")
                 print(f"   Best {metric_to_optimize}: {best_metric_value:.2f}%")
            else:
                print(f"Warning: No valid values found for '{metric_to_optimize}' after filtering.")
                if not aggregate_stats_df.index.empty:
                     best_col_name = aggregate_stats_df.index[0]
                     print(f"Using first valid combination as fallback: {best_col_name}")
                else:
                     print("Error: No valid combinations left after filtering.")
        elif aggregate_stats_df is not None and metric_to_optimize not in aggregate_stats_df.columns:
             print(f"Error: Metric '{metric_to_optimize}' not found in stats columns: {list(aggregate_stats_df.columns)}")
        else:
             print("Warning: Could not determine best combination (aggregate stats missing or empty).")


        if best_col_name is not None:
             if best_col_name in portfolio.wrapper.columns:
                print(f"\n--- Detailed Analysis for Best Combination {best_col_name} ---")
                best_portfolio_slice = portfolio[best_col_name]
                best_stats = metrics.get_summary_stats(best_portfolio_slice)
                if best_stats is not None and not best_stats.empty:
                     print("\n--- Performance Summary (Best Combination) ---")
                     print(best_stats)
                else: print("Could not retrieve detailed stats for the best combination.")

                best_trades_df = metrics.get_trade_records(best_portfolio_slice)
                if best_trades_df is not None and not best_trades_df.empty:
                    print("\n--- Trade Records (Best Combination - First 5) ---")
                    print(best_trades_df.head())
                    print(f"Total trades for best combination: {len(best_trades_df)}")
                elif best_portfolio_slice.trades.count() > 0: print("\nPortfolio object indicates trades, but fetching failed.")
                else: print("\nNo trades were executed for the best combination.")
             else:
                  print(f"Error: Determined best combination index '{best_col_name}' not found in portfolio columns. Analysis skipped.")
                  best_col_name = None
        else:
             print("\nSkipping detailed analysis as no best combination could be determined.")

    except Exception as e:
        print(f"ERROR during analysis: {e}")
        traceback.print_exc()
    print(f"Analysis finished. (Took {time.time() - analysis_start:.2f}s)")


# --- Save Results ---
save_start = time.time()
if portfolio is not None and best_col_name is not None:
     if best_col_name in portfolio.wrapper.columns:
        print("\n--- Saving Run Results ---")
        metrics.save_run_results(
            portfolio=portfolio,
            aggregate_stats=aggregate_stats_df,
            best_params=best_col_name,
            config_path='config/settings.py',
            strategy_name='macd_optimized',
            symbol=SYMBOL,
            price_data_for_plots=price_data
        )
        print(f"Saving complete. (Took {time.time() - save_start:.2f}s)")
     else:
          print("Warning: Best parameters determined but seem invalid for portfolio columns. Skipping saving results.")
elif portfolio is not None:
     print("Warning: Portfolio exists but best combination not determined/valid. Skipping saving results.")
else:
    print("Warning: No portfolio object generated. Skipping saving results.")

total_time = time.time() - overall_start_time
print(f"\n--- Backtest Finished ---")
print(f"Total execution time: {total_time:.2f} seconds ({total_time/60:.2f} minutes)")