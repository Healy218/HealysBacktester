# scripts/run_spy_ma_rsi_backtest.py

import vectorbt as vbt
import pandas as pd
import numpy as np
import sys
import os
import traceback
from itertools import product # For potential analysis/naming needs

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
from signals import rsi_threshold, ma_crossover, signal_combiners # [cite: HealysBacktester/signals/rsi_threshold.py, HealysBacktester/signals/ma_crossover.py, HealysBacktester/signals/signal_combiners.py]
from portfolio import simulator # [cite: HealysBacktester/portfolio/simulator.py]
from analysis import metrics, plotting # [cite: HealysBacktester/analysis/metrics.py, HealysBacktester/analysis/plotting.py]
from utils import config_parser # [cite: HealysBacktester/utils/config_parser.py]
from data import vbt_data_loader as data_loader, data_cleaner

# --- Load Configuration ---
try:
    config = config_parser.load_config('config/settings.py') # [cite: HealysBacktester/utils/config_parser.py, HealysBacktester/config/settings.py]
    DATA_CONFIG = config.get('DATA_CONFIG', {})
    STRATEGY_MA_CONFIG = config.get('STRATEGY_MA_CROSSOVER', {}) # [cite: HealysBacktester/config/settings.py]
    STRATEGY_RSI_CONFIG = config.get('STRATEGY_RSI', {}) # [cite: HealysBacktester/config/settings.py]
    BACKTEST_CONFIG = config.get('BACKTEST_CONFIG', {}) # [cite: HealysBacktester/config/settings.py]
    print(f"Configuration loaded successfully from: {os.path.join(project_root, 'config/settings.py')}") # [cite: HealysBacktester/config/settings.py]
except FileNotFoundError:
    print("FATAL ERROR: Configuration file 'config/settings.py' not found.") # [cite: HealysBacktester/config/settings.py]
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

# MA Strategy Params - Convert to numpy arrays
SHORT_WINDOWS_LIST = STRATEGY_MA_CONFIG.get('SHORT_WINDOW', [20])
if isinstance(SHORT_WINDOWS_LIST, int): SHORT_WINDOWS_LIST = [SHORT_WINDOWS_LIST]
SHORT_WINDOWS = np.array(SHORT_WINDOWS_LIST)

LONG_WINDOWS_LIST = STRATEGY_MA_CONFIG.get('LONG_WINDOW', [50])
if isinstance(LONG_WINDOWS_LIST, int): LONG_WINDOWS_LIST = [LONG_WINDOWS_LIST]
LONG_WINDOWS = np.array(LONG_WINDOWS_LIST)

# RSI Strategy Params - Convert to numpy arrays
RSI_WINDOWS_LIST = STRATEGY_RSI_CONFIG.get('RSI_WINDOW', [14])
if isinstance(RSI_WINDOWS_LIST, int): RSI_WINDOWS_LIST = [RSI_WINDOWS_LIST]
RSI_WINDOWS = np.array(RSI_WINDOWS_LIST)

ENTRY_THRESHOLDS_LIST = STRATEGY_RSI_CONFIG.get('ENTRY_THRESHOLD', [30])
if isinstance(ENTRY_THRESHOLDS_LIST, (int, float)): ENTRY_THRESHOLDS_LIST = [ENTRY_THRESHOLDS_LIST]
ENTRY_THRESHOLDS = np.array(ENTRY_THRESHOLDS_LIST)

EXIT_THRESHOLDS_LIST = STRATEGY_RSI_CONFIG.get('EXIT_THRESHOLD', [70])
if isinstance(EXIT_THRESHOLDS_LIST, (int, float)): EXIT_THRESHOLDS_LIST = [EXIT_THRESHOLDS_LIST]
EXIT_THRESHOLDS = np.array(EXIT_THRESHOLDS_LIST)

ENABLE_SHORTING = BACKTEST_CONFIG.get('ENABLE_SHORTING', False)

SHORT_ENTRY_THRESHOLDS_LIST = STRATEGY_RSI_CONFIG.get('SHORT_ENTRY_THRESHOLD', None)
SHORT_ENTRY_THRESHOLDS = None
if ENABLE_SHORTING:
    if SHORT_ENTRY_THRESHOLDS_LIST is not None:
        if isinstance(SHORT_ENTRY_THRESHOLDS_LIST, (int, float)): SHORT_ENTRY_THRESHOLDS_LIST = [SHORT_ENTRY_THRESHOLDS_LIST]
        SHORT_ENTRY_THRESHOLDS = np.array(SHORT_ENTRY_THRESHOLDS_LIST)

SHORT_EXIT_THRESHOLDS_LIST = STRATEGY_RSI_CONFIG.get('SHORT_EXIT_THRESHOLD', None)
SHORT_EXIT_THRESHOLDS = None
if ENABLE_SHORTING:
     if SHORT_EXIT_THRESHOLDS_LIST is not None:
        if isinstance(SHORT_EXIT_THRESHOLDS_LIST, (int, float)): SHORT_EXIT_THRESHOLDS_LIST = [SHORT_EXIT_THRESHOLDS_LIST]
        SHORT_EXIT_THRESHOLDS = np.array(SHORT_EXIT_THRESHOLDS_LIST)

# Backtest Settings
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
print(f"--- Starting MA Crossover + RSI Threshold Combined Backtest (AND vs OR) ---") # Updated title
print(f"Symbol: {SYMBOL}, Period: {START_DATE} to {END_DATE} ({INTERVAL})")
ma_short_str = ', '.join(map(str, SHORT_WINDOWS_LIST))
ma_long_str = ', '.join(map(str, LONG_WINDOWS_LIST))
print(f"MA Params: Short Windows=[{ma_short_str}], Long Windows=[{ma_long_str}]")
rsi_windows_str = ', '.join(map(str, RSI_WINDOWS_LIST))
rsi_entry_str = ', '.join(map(str, ENTRY_THRESHOLDS_LIST))
rsi_exit_str = ', '.join(map(str, EXIT_THRESHOLDS_LIST))
print(f"RSI Params: Windows=[{rsi_windows_str}], Long Entry=[{rsi_entry_str}], Long Exit=[{rsi_exit_str}]")
if ENABLE_SHORTING:
    rsi_s_entry_str = 'Default' if SHORT_ENTRY_THRESHOLDS_LIST is None else ', '.join(map(str, SHORT_ENTRY_THRESHOLDS_LIST))
    rsi_s_exit_str = 'Default' if SHORT_EXIT_THRESHOLDS_LIST is None else ', '.join(map(str, SHORT_EXIT_THRESHOLDS_LIST))
    print(f"            Short Entry=[{rsi_s_entry_str}], Short Exit=[{rsi_s_exit_str}]")
print(f"Parameter Combinations will be generated by vectorbt/signal generators.")
print(f"Backtest Settings: Initial Capital=${INITIAL_CAPITAL:,.2f}, Fees={FEES*100:.3f}%, Slippage={SLIPPAGE*100:.3f}%")
print(f"Sizing: Size={DEFAULT_SIZE}, Size Type='{DEFAULT_SIZE_TYPE}'")
print(f"Stop Loss: {'Enabled - ' + str(SL_STOP*100) + '%' if SL_STOP else 'Disabled'}")
print(f"Take Profit: {'Enabled - ' + str(TP_STOP*100) + '%' if TP_STOP else 'Disabled'}")
print(f"Shorting Enabled: {ENABLE_SHORTING} (Using RSI Short Signals)")
print("-" * 35)

# --- Initialize Variables ---
price_data = None
ma_entries, ma_exits = None, None
rsi_entries, rsi_exits, rsi_short_entries, rsi_short_exits = None, None, None, None
# Variables for AND logic
combined_entries_and, combined_exits_and = None, None
portfolio_and = None
best_stats_and = None
best_col_name_and = None
# Variables for OR logic
combined_entries_or, combined_exits_or = None, None
portfolio_or = None
best_stats_or = None
best_col_name_or = None

# --- Workflow ---

# 1. Load and Clean Data
print(f"\n[1/6] Loading and cleaning data for {SYMBOL}...")
try:
    raw_data = data_loader.load_price_data_smart(
        symbol=SYMBOL, start_date=START_DATE, end_date=END_DATE, interval=INTERVAL
    )
    if raw_data is None or raw_data.empty: raise ValueError(f"Data loading failed for {SYMBOL}.")
    price_data = data_cleaner.clean_ohlcv_data(raw_data) # [cite: HealysBacktester/data/data_cleaner.py]
    if price_data is None or price_data.empty: raise ValueError(f"Data cleaning failed for {SYMBOL}.")
    print(f"Data loading and cleaning successful. Final shape: {price_data.shape}")
except Exception as e:
    print(f"FATAL ERROR during data loading/cleaning: {e}")
    traceback.print_exc()
    exit()

# 2. Generate MA Signals
print(f"\n[2/6] Generating MA Crossover signals...")
try:
    ma_entries, ma_exits = ma_crossover.generate_ma_signals(
        close_prices_series=price_data['Close'],
        short_window=SHORT_WINDOWS,
        long_window=LONG_WINDOWS
    ) # [cite: HealysBacktester/signals/ma_crossover.py]
    if ma_entries is None or not isinstance(ma_entries, pd.DataFrame):
         raise ValueError("MA signal generation did not return a valid DataFrame.")
    print(f"MA Signals generated. Shape: {ma_entries.shape}")
except Exception as e:
    print(f"FATAL ERROR generating MA signals: {e}")
    traceback.print_exc()
    exit()

# 3. Generate RSI Signals
print(f"\n[3/6] Generating RSI Threshold signals (Shorting: {ENABLE_SHORTING})...")
try:
    rsi_entries, rsi_exits, rsi_short_entries, rsi_short_exits = rsi_threshold.generate_rsi_signals(
        close_prices_series=price_data['Close'],
        window=RSI_WINDOWS,
        entry_threshold=ENTRY_THRESHOLDS,
        exit_threshold=EXIT_THRESHOLDS,
        enable_shorting=ENABLE_SHORTING,
        short_entry_threshold=SHORT_ENTRY_THRESHOLDS,
        short_exit_threshold=SHORT_EXIT_THRESHOLDS
    ) # [cite: HealysBacktester/signals/rsi_threshold.py]
    if rsi_entries is None or not isinstance(rsi_entries, pd.DataFrame):
         raise ValueError("RSI signal generation did not return a valid DataFrame.")
    print(f"RSI Signals generated. Long Entry Shape: {rsi_entries.shape}")
    if ENABLE_SHORTING and rsi_short_entries is not None:
        print(f"RSI Short Entry Shape: {rsi_short_entries.shape}")
except Exception as e:
    print(f"FATAL ERROR generating RSI signals: {e}")
    traceback.print_exc()
    exit()

# 4. Combine Signals (AND logic)
print(f"\n[4/6] Combining MA and RSI signals (Using AND logic for Long)...")
try:
    combined_entries_and, combined_exits_and = signal_combiners.combine_signals_and(
        entries1_df=ma_entries,
        exits1_df=ma_exits,
        entries2_df=rsi_entries,
        exits2_df=rsi_exits
    ) # [cite: HealysBacktester/signals/signal_combiners.py]
    if combined_entries_and is None: raise ValueError("AND Signal combination failed.")
    print(f"Combined Signals (AND) generated. Shape: {combined_entries_and.shape}")
    if not combined_entries_and.any().any():
         print("Warning: No combined long entry signals generated for AND logic.")
except Exception as e:
    print(f"ERROR combining signals (AND logic): {e}")
    traceback.print_exc()
    # Continue to try OR logic even if AND fails or produces no signals

# 5. Combine Signals (OR logic)
print(f"\n[5/6] Combining MA and RSI signals (Using OR logic for Long)...")
try:
    # Note: Using the default OR exit logic (exit if BOTH originals exit)
    # Change call or function if different OR exit logic is desired
    combined_entries_or, combined_exits_or = signal_combiners.combine_signals_or(
        entries1_df=ma_entries,
        exits1_df=ma_exits,
        entries2_df=rsi_entries,
        exits2_df=rsi_exits
    ) # [cite: HealysBacktester/signals/signal_combiners.py]
    if combined_entries_or is None: raise ValueError("OR Signal combination failed.")
    print(f"Combined Signals (OR) generated. Shape: {combined_entries_or.shape}")
    if not combined_entries_or.any().any():
         print("Warning: No combined long entry signals generated for OR logic.")

except Exception as e:
    print(f"ERROR combining signals (OR logic): {e}")
    traceback.print_exc()

# 6. Run Simulations and Analyze
print(f"\n[6/6] Running backtest simulations and analyzing...")

# --- Run and Analyze AND Logic ---
print("\n--- Analyzing AND Logic Results ---")
if combined_entries_and is not None and combined_exits_and is not None:
    and_long_entries_exist = combined_entries_and.any().any()
    and_short_entries_exist = False # Using only RSI shorts
    if ENABLE_SHORTING and rsi_short_entries is not None:
        and_short_entries_exist = rsi_short_entries.any().any()

    if and_long_entries_exist or and_short_entries_exist:
        try:
            print("Running simulation for AND logic...")
            portfolio_and = simulator.run_backtest(
                price_df=price_data,
                entries_series=combined_entries_and,
                exits_series=combined_exits_and,
                short_entries_series=rsi_short_entries if ENABLE_SHORTING else None,
                short_exits_series=rsi_short_exits if ENABLE_SHORTING else None,
                initial_capital=INITIAL_CAPITAL, fees=FEES, slippage=SLIPPAGE,
                frequency=DEFAULT_FREQ, size=DEFAULT_SIZE, size_type=DEFAULT_SIZE_TYPE,
                sl_stop=SL_STOP, tp_stop=TP_STOP
            ) # [cite: HealysBacktester/portfolio/simulator.py]
            print("AND logic simulation complete.")

            # Analyze AND portfolio
            if portfolio_and is not None:
                 metric_to_optimize = 'Total Return [%]'
                 metric_values_and = {}
                 if hasattr(portfolio_and.wrapper, 'columns') and not portfolio_and.wrapper.columns.empty:
                    for col_name in portfolio_and.wrapper.columns:
                         try:
                             stats_series = portfolio_and.stats(column=col_name)
                             if isinstance(stats_series, pd.Series) and metric_to_optimize in stats_series.index:
                                 metric_value = stats_series.loc[metric_to_optimize]
                                 if pd.notna(metric_value): metric_values_and[col_name] = metric_value
                         except Exception: pass # Ignore errors getting stats for a specific column

                    if metric_values_and:
                        best_col_name_and = max(metric_values_and, key=metric_values_and.get)
                        best_stats_and = portfolio_and.stats(column=best_col_name_and) # Get Series
                        print(f"Best AND Params: {best_col_name_and} -> {metric_to_optimize}: {best_stats_and.loc[metric_to_optimize]:.2f}%")
                    else: print("Could not determine best parameters for AND logic.")
                 else: print("AND Portfolio has no columns to analyze.")
            else: print("AND Simulation resulted in None portfolio object.")

        except Exception as e:
            print(f"Error during AND logic simulation or analysis: {e}")
            traceback.print_exc()
    else:
        print("Skipping AND simulation: No valid entry signals generated.")
else:
    print("Skipping AND analysis: Combined signals not generated.")


# --- Run and Analyze OR Logic ---
print("\n--- Analyzing OR Logic Results ---")
if combined_entries_or is not None and combined_exits_or is not None:
    or_long_entries_exist = combined_entries_or.any().any()
    or_short_entries_exist = False # Using only RSI shorts
    if ENABLE_SHORTING and rsi_short_entries is not None:
         # Align RSI shorts with OR combo columns if needed, or use broadcast
         # For simplicity, assume simulator handles broadcasting RSI shorts to OR columns
        or_short_entries_exist = rsi_short_entries.any().any()


    if or_long_entries_exist or or_short_entries_exist:
        try:
            print("Running simulation for OR logic...")
            portfolio_or = simulator.run_backtest(
                price_df=price_data,
                entries_series=combined_entries_or,
                exits_series=combined_exits_or,
                 # Pass RSI shorts - vectorbt should handle broadcasting against OR columns
                short_entries_series=rsi_short_entries if ENABLE_SHORTING else None,
                short_exits_series=rsi_short_exits if ENABLE_SHORTING else None,
                initial_capital=INITIAL_CAPITAL, fees=FEES, slippage=SLIPPAGE,
                frequency=DEFAULT_FREQ, size=DEFAULT_SIZE, size_type=DEFAULT_SIZE_TYPE,
                sl_stop=SL_STOP, tp_stop=TP_STOP
            ) # [cite: HealysBacktester/portfolio/simulator.py]
            print("OR logic simulation complete.")

            # Analyze OR portfolio
            if portfolio_or is not None:
                 metric_to_optimize = 'Total Return [%]'
                 metric_values_or = {}
                 if hasattr(portfolio_or.wrapper, 'columns') and not portfolio_or.wrapper.columns.empty:
                     for col_name in portfolio_or.wrapper.columns:
                          try:
                              stats_series = portfolio_or.stats(column=col_name)
                              if isinstance(stats_series, pd.Series) and metric_to_optimize in stats_series.index:
                                  metric_value = stats_series.loc[metric_to_optimize]
                                  if pd.notna(metric_value): metric_values_or[col_name] = metric_value
                          except Exception: pass # Ignore errors

                     if metric_values_or:
                         best_col_name_or = max(metric_values_or, key=metric_values_or.get)
                         best_stats_or = portfolio_or.stats(column=best_col_name_or) # Get Series
                         print(f"Best OR Params: {best_col_name_or} -> {metric_to_optimize}: {best_stats_or.loc[metric_to_optimize]:.2f}%")
                     else: print("Could not determine best parameters for OR logic.")
                 else: print("OR Portfolio has no columns to analyze.")
            else: print("OR Simulation resulted in None portfolio object.")

        except Exception as e:
            print(f"Error during OR logic simulation or analysis: {e}")
            traceback.print_exc()
    else:
        print("Skipping OR simulation: No valid entry signals generated.")
else:
    print("Skipping OR analysis: Combined signals not generated.")

# --- Comparison ---
print("\n--- Comparison of Best Results ---")
metrics_to_compare = ['Total Return [%]', 'Sharpe Ratio', 'Max Drawdown [%]', 'Win Rate [%]', 'Total Trades']
comparison_data = {'Metric': metrics_to_compare}

and_values = []
if best_stats_and is not None:
    for m in metrics_to_compare:
        and_values.append(f"{best_stats_and.get(m, 'N/A'):.2f}" if pd.notna(best_stats_and.get(m)) else 'N/A')
else:
    and_values = ['N/A'] * len(metrics_to_compare)
comparison_data['AND Logic (Best)'] = and_values

or_values = []
if best_stats_or is not None:
     for m in metrics_to_compare:
         or_values.append(f"{best_stats_or.get(m, 'N/A'):.2f}" if pd.notna(best_stats_or.get(m)) else 'N/A')
else:
    or_values = ['N/A'] * len(metrics_to_compare)
comparison_data['OR Logic (Best)'] = or_values

comparison_df = pd.DataFrame(comparison_data).set_index('Metric')
print(comparison_df)

# --- Saving Results (Optional - Requires Adaptation) ---
# Decide how/if you want to save results for both runs.
# Could call metrics.save_run_results twice with different strategy names/subdirs.
# Example:
# if portfolio_and is not None and best_col_name_and is not None:
#     metrics.save_run_results(..., portfolio=portfolio_and, best_params=best_col_name_and, strategy_name='ma_rsi_combined_and', ...)
# if portfolio_or is not None and best_col_name_or is not None:
#     metrics.save_run_results(..., portfolio=portfolio_or, best_params=best_col_name_or, strategy_name='ma_rsi_combined_or', ...)

print(f"\n--- Backtest Finished ---")