# scripts/run_spy_volume_breakout_backtest.py

import vectorbt as vbt
import pandas as pd
import numpy as np
import sys
import os
import traceback

# --- Add Project Root to Python Path ---
# ... (copy from other run scripts) ...
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
# ****** Import the new Volume Breakout signal generator ******
from signals import volume_breakout
from portfolio import simulator
from analysis import metrics, plotting
from utils import config_parser
from data import data_loader, data_cleaner

# --- Load Configuration ---
try:
    config = config_parser.load_config('config/settings.py')
    DATA_CONFIG = config.get('DATA_CONFIG', {})
    # ****** Load Volume Breakout specific config ******
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

# ****** Strategy Params (Volume Breakout specific) ******
VOLUME_WINDOWS_LIST = STRATEGY_CONFIG.get('VOLUME_WINDOW', [20])
if isinstance(VOLUME_WINDOWS_LIST, int): VOLUME_WINDOWS_LIST = [VOLUME_WINDOWS_LIST]
VOLUME_WINDOWS = np.array(VOLUME_WINDOWS_LIST)

VOLUME_MULTIPLIERS_LIST = STRATEGY_CONFIG.get('VOLUME_MULTIPLIER', [2.0])
if isinstance(VOLUME_MULTIPLIERS_LIST, (int, float)): VOLUME_MULTIPLIERS_LIST = [VOLUME_MULTIPLIERS_LIST]
VOLUME_MULTIPLIERS = np.array(VOLUME_MULTIPLIERS_LIST)

CONFIRM_PRICE_INCREASE = STRATEGY_CONFIG.get('CONFIRM_PRICE_INCREASE', True)

# ****** ADD THIS: Extract Exit MA Window ******
EXIT_MA_WINDOWS_LIST = STRATEGY_CONFIG.get('EXIT_MA_WINDOW', [10]) # Default to 10 if not in config
if isinstance(EXIT_MA_WINDOWS_LIST, int): EXIT_MA_WINDOWS_LIST = [EXIT_MA_WINDOWS_LIST]
EXIT_MA_WINDOWS = np.array(EXIT_MA_WINDOWS_LIST)
# **********************************************

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

SL_STOP = SL_PERCENT if USE_SL else None
TP_STOP = TP_PERCENT if USE_TP else None


# --- Print Run Info ---
print(f"--- Starting Volume Breakout Backtest ---")
print(f"Symbol: {SYMBOL}, Period: {START_DATE} to {END_DATE} ({INTERVAL})")
window_str = ', '.join(map(str, VOLUME_WINDOWS_LIST))
multi_str = ', '.join(map(str, VOLUME_MULTIPLIERS_LIST))
print(f"Strategy Params: Volume Windows=[{window_str}], Multipliers=[{multi_str}]")
print(f"Require Price Increase Confirmation: {CONFIRM_PRICE_INCREASE}")
print(f"Parameter Combinations will be generated.") # By the signal generator
print(f"Backtest Settings: Initial Capital=${INITIAL_CAPITAL:,.2f}, Fees={FEES*100:.3f}%, Slippage={SLIPPAGE*100:.3f}%")
print(f"Sizing: Size={DEFAULT_SIZE}, Size Type='{DEFAULT_SIZE_TYPE}'")
print(f"Stop Loss: {'Enabled - ' + str(SL_STOP*100) + '%' if SL_STOP else 'Disabled'}")
print(f"Take Profit: {'Enabled - ' + str(TP_STOP*100) + '%' if TP_STOP else 'Disabled'}")
print("-" * 35)

# --- Initialize Variables ---
price_data = None
# Renamed signals for clarity
vb_entries, vb_exits = None, None
portfolio = None
aggregate_stats_df = None
best_col_name = None

# --- Workflow ---

# 1. Load and Clean Data
print(f"\n[1/4] Loading and cleaning data for {SYMBOL}...")
try:
    raw_data = data_loader.load_price_data(
        symbol=SYMBOL, start_date=START_DATE, end_date=END_DATE, interval=INTERVAL
    )
    if raw_data is None or raw_data.empty: raise ValueError(f"Data loading failed for {SYMBOL}.")
    # ****** Ensure Volume column exists ******
    if 'Volume' not in raw_data.columns:
        raise ValueError("Volume column missing from loaded data. Cannot run Volume Breakout strategy.")
    price_data = data_cleaner.clean_ohlcv_data(raw_data)
    if price_data is None or price_data.empty: raise ValueError(f"Data cleaning failed for {SYMBOL}.")
    print(f"Data loading and cleaning successful. Final shape: {price_data.shape}")
except Exception as e:
    print(f"FATAL ERROR during data loading/cleaning: {e}")
    traceback.print_exc()
    exit()

# 2. Generate Volume Breakout Signals
print(f"\n[2/4] Generating Volume Breakout signals...")
try:
    # ****** Call the new Volume Breakout signal generator ******
    vb_entries, vb_exits, _, _ = volume_breakout.generate_volume_signals(
        ohlcv_df=price_data, # Pass full OHLCV df
        window=VOLUME_WINDOWS,
        multiplier=VOLUME_MULTIPLIERS,
        exit_ma_window=EXIT_MA_WINDOWS,
        confirm_price_increase=CONFIRM_PRICE_INCREASE
    )
    print("Signals generated.")
    if isinstance(vb_entries, pd.DataFrame): print(f"Entries Shape: {vb_entries.shape}")
    if isinstance(vb_exits, pd.DataFrame): print(f"Exits Shape: {vb_exits.shape}")

except ImportError:
     print("FATAL ERROR: Could not import volume_breakout module.")
     exit()
except Exception as e:
    print(f"FATAL ERROR generating signals: {e}")
    traceback.print_exc()
    exit()

# 3. Run Simulation
print(f"\n[3/4] Running backtest simulation...")
portfolio = None
simulation_possible = vb_entries is not None and vb_entries.any().any()

if simulation_possible:
    try:
        portfolio = simulator.run_backtest(
            price_df=price_data,
            entries_series=vb_entries,
            exits_series=vb_exits, # Pass the DataFrame of False (exits handled by SL/TP)
            # No short signals for this strategy
            short_entries_series=None,
            short_exits_series=None,
            # Pass other backtest settings
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
        traceback.print_exc()
else:
     print("Skipping simulation because no valid entry signals were generated.")


# 4. Analyze and Plot Results (find best combination)
print(f"\n[4/4] Analyzing results...")
if portfolio is not None:
    try:
        # --- Identify Best Combination ---
        metric_to_optimize = 'Total Return [%]' # Or another metric like Sharpe Ratio
        best_col_name = None # Tuple: (volume_window, volume_multiplier)
        metric_values = {}

        print(f"\n--- Identifying best combination based on '{metric_to_optimize}' ---")
        if hasattr(portfolio.wrapper, 'columns') and not portfolio.wrapper.columns.empty:
            column_names = portfolio.wrapper.columns
            print(f"Checking {len(column_names)} parameter combinations...")

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
                print(f"Selected Best Combination Parameters: {best_col_name}") # Tuple (window, multiplier)
                print(f"   Best {metric_to_optimize}: {metric_values[best_col_name]:.2f}%")
            else:
                print("Warning: Could not collect valid metric values for comparison.")
                if not portfolio.wrapper.columns.empty:
                     best_col_name = portfolio.wrapper.columns[0]
                     print(f"Using first combination as fallback: {best_col_name}")
        else:
            print("Error: Portfolio object exists but has no columns to analyze.")

        # --- Analyze and Print details for BEST Combination ---
        if best_col_name is not None:
            if best_col_name in portfolio.wrapper.columns:
                print(f"\n--- Detailed Analysis for Best Combination ({best_col_name}) ---")
                best_portfolio_slice = portfolio[best_col_name]
                best_stats = metrics.get_summary_stats(best_portfolio_slice)
                if best_stats is not None and not best_stats.empty:
                     print("\n--- Performance Summary (Best Combination) ---")
                     print(best_stats)
                else:
                     print("Could not retrieve detailed stats for the best combination.")

                best_trades_df = metrics.get_trade_records(best_portfolio_slice)
                if best_trades_df is not None and not best_trades_df.empty:
                    print("\n--- Trade Records (Best Combination - First 5) ---")
                    print(best_trades_df.head())
                    print(f"Total trades for best combination: {len(best_trades_df)}")
                elif best_portfolio_slice.trades.count() > 0:
                     print("\nPortfolio object indicates trades, but fetching failed.")
                else:
                     print("\nNo trades were executed for the best combination.")
            else:
                 print(f"Error: Determined best combination name '{best_col_name}' is not valid in portfolio columns.")
        else:
             print("\nSkipping detailed analysis as no best combination could be determined.")

    except Exception as e:
        print(f"ERROR during analysis: {e}")
        traceback.print_exc()

# --- Save Results ---
if portfolio is not None and best_col_name is not None:
     if best_col_name in portfolio.wrapper.columns:
        print("\n--- Saving Run Results ---")
        # Generate aggregate stats if multiple columns exist
        aggregate_stats_df = None
        if len(portfolio.wrapper.columns) > 1:
            try:
                aggregate_stats_df = portfolio.stats()
                if not isinstance(aggregate_stats_df, pd.DataFrame):
                    aggregate_stats_df = None
            except Exception as agg_e:
                print(f"Warning: Could not generate aggregate stats: {agg_e}")
                aggregate_stats_df = None

        metrics.save_run_results(
            portfolio=portfolio,
            aggregate_stats=aggregate_stats_df,
            best_params=best_col_name,
            config_path='config/settings.py',
             # ****** Use 'volume_breakout' as strategy name ******
            strategy_name='volume_breakout',
            symbol=SYMBOL,
            price_data_for_plots=price_data
        )
     else:
          print("Warning: Best parameters determined but not found in portfolio columns. Skipping saving results.")
elif portfolio is not None:
     print("Warning: Portfolio exists but best combination not determined. Skipping saving results.")
else:
    print("Warning: No portfolio object generated. Skipping saving results.")


print(f"\n--- Backtest Finished ---")