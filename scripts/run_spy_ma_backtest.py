# scripts/run_spy_ma_backtest.py

# --- Standard Imports ---
import pandas as pd
import numpy as np
import sys
import os
import itertools
import vectorbt as vbt
from collections import defaultdict # To store results

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
from portfolio import simulator
from analysis import metrics, plotting
from utils import config_parser

# --- Load Configuration ---
try:
    config = config_parser.load_config('config/settings.py')
    DATA_CONFIG = config.get('DATA_CONFIG', {})
    BACKTEST_CONFIG = config.get('BACKTEST_CONFIG', {})
except FileNotFoundError:
    print("FATAL ERROR: Configuration file 'config/settings.py' not found.")
    exit()
except Exception as e:
    print(f"FATAL ERROR: Could not load configuration: {e}")
    exit()

# --- Extract Parameters from Config (Base Settings) ---
SYMBOL = DATA_CONFIG.get('SYMBOL', 'SPY')
START_DATE = DATA_CONFIG.get('START_DATE', '2020-01-01')
END_DATE = DATA_CONFIG.get('END_DATE', '2023-12-31')
INTERVAL = DATA_CONFIG.get('INTERVAL', '1D')

INITIAL_CAPITAL = BACKTEST_CONFIG.get('INITIAL_CAPITAL', 100000.0)
FEES = BACKTEST_CONFIG.get('FEES_PERCENT', 0.001)
SLIPPAGE = BACKTEST_CONFIG.get('SLIPPAGE_PERCENT', 0.0005)
DEFAULT_SIZE = BACKTEST_CONFIG.get('DEFAULT_SIZE', 0.99)
DEFAULT_SIZE_TYPE = BACKTEST_CONFIG.get('DEFAULT_SIZE_TYPE', 'percent')
DEFAULT_FREQ = BACKTEST_CONFIG.get('DEFAULT_FREQ', 'D')
SL_STOP = BACKTEST_CONFIG.get('STOP_LOSS_PERCENT', None) if BACKTEST_CONFIG.get('USE_STOP_LOSS', False) else None
TP_STOP = BACKTEST_CONFIG.get('TAKE_PROFIT_PERCENT', None) if BACKTEST_CONFIG.get('USE_TAKE_PROFIT', False) else None

# --- Parameter Optimization Ranges ---
short_windows = np.arange(10, 51, 10)
long_windows = np.arange(30, 101, 10)

# --- Print Run Info ---
print(f"--- Starting MA Crossover Parameter Optimization (Manual Loop Workaround) ---")
print(f"Symbol: {SYMBOL}")
print(f"Period: {START_DATE} to {END_DATE} ({INTERVAL})")
print(f"Short Window Range: {short_windows}")
print(f"Long Window Range: {long_windows}")
# ... (rest of print info) ...
print("-" * 35)

# --- Initialize Variables ---
price_data = pd.DataFrame()
all_portfolios = {}
all_stats_list = []

# --- Workflow ---

# 1. Load Data
print(f"\n[1/X] Loading data for {SYMBOL}...")
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


# 2. Iterate Through Parameters, Generate Signals, and Simulate
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
        # 2a. Calculate SMAs using pandas
        short_sma = price_data['Close'].rolling(window=short_w).mean()
        long_sma = price_data['Close'].rolling(window=long_w).mean()

        # 2b. Generate signals for this pair using the .vbt accessor
        print("Generating signals...") # Moved print here
        if short_sma.notna().any() and long_sma.notna().any():
            # --- CORRECTED: Use .vbt accessor ---
            entries = short_sma.vbt.crossed_above(long_sma)
            exits = short_sma.vbt.crossed_below(long_sma)
            # --- END CORRECTION ---

            # Ensure boolean type (accessor methods should already return bool)
            entries = entries.astype(bool)
            exits = exits.astype(bool)
            # Assign names for clarity if needed later (optional)
            entries.name = f'entries_{short_w}_{long_w}'
            exits.name = f'exits_{short_w}_{long_w}'

            print(f"Signal sums: Entries={entries.sum()}, Exits={exits.sum()}")

            if not entries.any():
                print("Warning: No entry signals generated for this combination.")
        else:
            print(f"Warning: NaN in SMA for {param_label}, skipping signals.")
            entries = pd.Series(False, index=price_data.index)
            exits = pd.Series(False, index=price_data.index)

        # 2c. Run simulation for this pair
        if entries.any():
            print("Running simulation...")
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
            # Store results
            all_portfolios[(short_w, long_w)] = portfolio
            stats = metrics.get_summary_stats(portfolio)
            if stats is not None:
                 stats.name = (short_w, long_w)
                 all_stats_list.append(stats)
            print(f"Simulation successful for {param_label}. Trades: {portfolio.trades.count()}")
        else:
            print(f"Skipping simulation for {param_label} (no entry signals).")

    except Exception as e:
        print(f"ERROR processing combination {param_label}: {e}")
        # Continue to next combination

# 3. Analyze Aggregate Results (Same as before)
print(f"\n[3/X] Analyzing aggregate results...")
if not all_stats_list:
    print("No simulations completed successfully. Cannot analyze results.")
else:
    try:
        all_stats_df = pd.concat(all_stats_list, axis=1)

        print("\n--- Performance Summary (All Combinations) ---")
        key_stats = ['Total Return [%]', 'Win Rate [%]', 'Sharpe Ratio', 'Max Drawdown [%]']
        stats_to_print = all_stats_df.loc[all_stats_df.index.intersection(key_stats)]
        print(stats_to_print)

        if 'Total Return [%]' in all_stats_df.index:
            best_col_idx = all_stats_df.loc['Total Return [%]'].idxmax()
            best_params = best_col_idx
            best_stats = all_stats_df[best_col_idx]
            print(f"\n--- Best Performing Parameters (based on Total Return) ---")
            if isinstance(best_params, tuple) and len(best_params) >= 2:
                 print(f"Short Window: {best_params[0]}, Long Window: {best_params[1]}")
            else:
                 print(f"Best Column Index: {best_params} (Unexpected format)")
            print("Stats for Best Combination:")
            print(best_stats)

            if best_params in all_portfolios:
                print("\nGenerating plots for the best performing combination...")
                best_portfolio_obj = all_portfolios[best_params]
                plotting.plot_portfolio_summary(best_portfolio_obj)
                plotting.plot_trades(best_portfolio_obj, price_data)
                print("Plots generated.")
            else:
                print("Could not find portfolio object for the best parameters to plot.")
        else:
            print("Could not determine best parameters - 'Total Return [%]' missing from stats.")

    except ImportError:
        print("ERROR: Could not import analysis or plotting modules.")
    except Exception as e:
        print(f"ERROR during aggregate analysis or plotting: {e}")


print(f"\n--- Backtest Finished ---")