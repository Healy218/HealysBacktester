# filename: HealysBacktester/scripts/run_spy_volume_backtest.py

# --- Standard Imports ---
import pandas as pd
import numpy as np
import sys
import os
import time # Import time module for estimating runtime
import warnings
import logging # Import logging first
import vectorbt as vbt # Import vbt early for version check
from typing import Optional, Union, Tuple, Any, List # For type hints

# --- Print Versions (Before Logging is Setup) ---
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
    project_root = os.path.dirname(script_dir) # Go up ONE level
    if project_root not in sys.path:
        sys.path.insert(0, str(project_root))
    print(f"Project Root added to path: {project_root}") # Keep this print for immediate feedback
except NameError:
    print("Warning: Could not determine script directory automatically.")
    project_root = '.' # Assume running from project root
    if project_root not in sys.path:
        sys.path.insert(0, str(project_root))
# --- End Path Modification ---

# --- Setup Logging (AFTER path modification) ---
try:
    from utils.logging_utils import setup_logging
    # Configure logging
    log_file_path = os.path.join(project_root, "logs", "volume_backtest.log") # Specific log file
    logger = setup_logging(log_level=logging.INFO, log_file=log_file_path)
    logger.info("Logging setup complete.")
except ImportError:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    logger.error("Failed to import setup_logging from utils.logging_utils. Using basic console logging.")
except Exception as log_setup_err:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    logger.error(f"Error setting up file logging: {log_setup_err}. Using basic console logging.")

# --- Import project modules (AFTER logging setup) ---
try:
    from signals import volume_breakout # Import the Volume Breakout signal generator
    from portfolio import simulator
    from analysis import metrics, plotting
    from utils import config_parser, freq_utils
    from data import data_loader, data_cleaner
    # Import custom error types
    from utils.error_handling import DataError, SignalError, PortfolioError, ConfigurationError
except ImportError as import_err:
    logger.exception(f"FATAL ERROR: Failed to import necessary project modules: {import_err}")
    sys.exit(1)

# --- Initialize Variables ---
price_data = None
vb_entries, vb_exits = None, None # Use specific names if signal generator returns them
portfolio = None
best_params = None # Will store the index tuple of the best combo
aggregate_stats_df = None # Store stats df (though not used for optimization here)
config_file = os.path.join(project_root, 'config', 'settings.py')
overall_start_time = time.time()

# --- Load Configuration ---
logger.info("Loading configuration...")
try:
    config = config_parser.load_config(config_file)
    DATA_CONFIG = config.get('DATA_CONFIG', {})
    STRATEGY_CONFIG = config.get('STRATEGY_VOLUME_BREAKOUT', {}) # Use Volume Breakout section
    BACKTEST_CONFIG = config.get('BACKTEST_CONFIG', {})
    logger.info(f"Configuration loaded successfully from: {config_file}")
except FileNotFoundError:
    logger.exception(f"FATAL ERROR: Configuration file '{config_file}' not found.")
    sys.exit(1)
except ConfigurationError as config_err:
     logger.exception(f"FATAL ERROR: Configuration error: {config_err}")
     sys.exit(1)
except Exception as e:
    logger.exception(f"FATAL ERROR: Could not load configuration: {e}")
    sys.exit(1)

# --- Extract Parameters from Config ---
logger.info("Extracting parameters from configuration...")
try:
    # Data Params
    SYMBOL = DATA_CONFIG.get('SYMBOL', 'SPY')
    START_DATE = DATA_CONFIG.get('START_DATE', '2020-01-01')
    END_DATE = DATA_CONFIG.get('END_DATE', '2023-12-31')
    INTERVAL = DATA_CONFIG.get('INTERVAL', '1D')

    # Backtest Settings (Shared)
    INITIAL_CAPITAL = BACKTEST_CONFIG.get('INITIAL_CAPITAL', 100000.0)
    FEES = BACKTEST_CONFIG.get('FEES_PERCENT', 0.001)
    SLIPPAGE = BACKTEST_CONFIG.get('SLIPPAGE_PERCENT', 0.0005)
    DEFAULT_FREQ = freq_utils.resolve_freq(BACKTEST_CONFIG.get('DEFAULT_FREQ'), INTERVAL)
    DEFAULT_SIZE = BACKTEST_CONFIG.get('DEFAULT_SIZE', 0.99)
    DEFAULT_SIZE_TYPE = BACKTEST_CONFIG.get('DEFAULT_SIZE_TYPE', 'percent')
    USE_SL = BACKTEST_CONFIG.get('USE_STOP_LOSS', False)
    SL_PERCENT = BACKTEST_CONFIG.get('STOP_LOSS_PERCENT', None)
    USE_TP = BACKTEST_CONFIG.get('USE_TAKE_PROFIT', False)
    TP_PERCENT = BACKTEST_CONFIG.get('TAKE_PROFIT_PERCENT', None)

    sl_stop_value = SL_PERCENT if USE_SL and SL_PERCENT is not None else None
    tp_stop_value = TP_PERCENT if USE_TP and TP_PERCENT is not None else None

    # Strategy Params (Volume Breakout specific) - USING RANGES FOR ALL
    VOLUME_WINDOW_START = STRATEGY_CONFIG.get('VOLUME_WINDOW_START', 30)
    VOLUME_WINDOW_END = STRATEGY_CONFIG.get('VOLUME_WINDOW_END', 151) # Exclusive
    VOLUME_WINDOW_STEP = STRATEGY_CONFIG.get('VOLUME_WINDOW_STEP', 2)
    volume_window_range = np.arange(VOLUME_WINDOW_START, VOLUME_WINDOW_END, VOLUME_WINDOW_STEP, dtype=int)
    if volume_window_range.size == 0: raise ValueError("Volume window range resulted in empty array.")

    VOLUME_MULTIPLIER_START = STRATEGY_CONFIG.get('VOLUME_MULTIPLIER_START', 1.05)
    VOLUME_MULTIPLIER_END = STRATEGY_CONFIG.get('VOLUME_MULTIPLIER_END', 2.00) # Inclusive
    VOLUME_MULTIPLIER_STEP = STRATEGY_CONFIG.get('VOLUME_MULTIPLIER_STEP', 0.05)
    # Use np.linspace for float steps to avoid precision issues with np.arange
    num_multiplier_steps = max(1, int(round((VOLUME_MULTIPLIER_END - VOLUME_MULTIPLIER_START) / VOLUME_MULTIPLIER_STEP)) + 1)
    volume_multiplier_range = np.linspace(VOLUME_MULTIPLIER_START, VOLUME_MULTIPLIER_END, num_multiplier_steps)
    if volume_multiplier_range.size == 0: raise ValueError("Volume multiplier range resulted in empty array.")

    EXIT_MA_WINDOW_START = STRATEGY_CONFIG.get('EXIT_MA_WINDOW_START', 45)
    EXIT_MA_WINDOW_END = STRATEGY_CONFIG.get('EXIT_MA_WINDOW_END', 151) # Exclusive
    EXIT_MA_WINDOW_STEP = STRATEGY_CONFIG.get('EXIT_MA_WINDOW_STEP', 1)
    exit_ma_window_range = np.arange(EXIT_MA_WINDOW_START, EXIT_MA_WINDOW_END, EXIT_MA_WINDOW_STEP, dtype=int)
    if exit_ma_window_range.size == 0: raise ValueError("Exit MA window range resulted in empty array.")

    CONFIRM_PRICE_INCREASE = STRATEGY_CONFIG.get('CONFIRM_PRICE_INCREASE', False) # Default to False if not set

    # Calculate total combinations
    num_combinations = len(volume_window_range) * len(volume_multiplier_range) * len(exit_ma_window_range)

    logger.info("Parameters extracted successfully.")

except KeyError as e:
    logger.exception(f"FATAL ERROR: Missing expected key in configuration: {e}")
    sys.exit(1)
except ValueError as e:
    logger.exception(f"FATAL ERROR: Invalid parameter range in settings.py: {e}")
    sys.exit(1)
except Exception as e:
    logger.exception(f"FATAL ERROR: Error processing configuration parameters: {e}")
    sys.exit(1)


# --- Print Run Info ---
logger.info(f"\n--- Starting Volume Breakout Parameter Optimization ---")
logger.info(f"Symbol: {SYMBOL}, Period: {START_DATE} to {END_DATE} ({INTERVAL})")
logger.info(f"Volume Window Range: {VOLUME_WINDOW_START} to {volume_window_range[-1]} (Step: {VOLUME_WINDOW_STEP}) -> {len(volume_window_range)} values")
logger.info(f"Volume Multiplier Range: {volume_multiplier_range.min():.2f} to {volume_multiplier_range.max():.2f} (Steps: {len(volume_multiplier_range)})")
logger.info(f"Exit MA Window Range: {EXIT_MA_WINDOW_START} to {exit_ma_window_range[-1]} (Step: {EXIT_MA_WINDOW_STEP}) -> {len(exit_ma_window_range)} values")
logger.info(f"Estimated Number of Combinations: {num_combinations:,}")
logger.info(f"Require Price Increase Confirmation: {CONFIRM_PRICE_INCREASE}")
logger.info(f"Backtest Settings: Initial Capital=${INITIAL_CAPITAL:,.2f}, Fees={FEES:.3%}, Slippage={SLIPPAGE:.3%}")
logger.info(f"Sizing: Size={DEFAULT_SIZE}, Size Type='{DEFAULT_SIZE_TYPE}'")
logger.info(f"Stop Loss: {'Enabled' if sl_stop_value else 'Disabled'}{f' ({SL_PERCENT:.1%})' if sl_stop_value else ''}")
logger.info(f"Take Profit: {'Enabled' if tp_stop_value else 'Disabled'}{f' ({TP_PERCENT:.1%})' if tp_stop_value else ''}")

if num_combinations > 50000: # Example threshold
    logger.warning(f"Testing a very large number of combinations ({num_combinations:,}). This may take a significant amount of time and memory.")
logger.info("-" * 35)


# --- Workflow ---

# 1. Load and Clean Data
logger.info(f"\n[1/4] Loading and cleaning data for {SYMBOL}...")
load_start_time = time.time()
try:
    raw_data = data_loader.load_price_data(
        symbol=SYMBOL, start_date=START_DATE, end_date=END_DATE, interval=INTERVAL
    )
    if raw_data is None or raw_data.empty:
        raise DataError(f"Data loading returned empty or None for {SYMBOL}.")
    # Specific check for Volume column needed by this strategy
    if 'Volume' not in raw_data.columns:
        raise DataError("Volume column missing from loaded data. Cannot run Volume Breakout strategy.")

    price_data = data_cleaner.clean_ohlcv_data(raw_data)
    if price_data is None or price_data.empty:
        raise DataError(f"Data cleaning returned empty or None for {SYMBOL}.")

    logger.info(f"Data loading and cleaning successful. Final shape: {price_data.shape}. (Took {time.time() - load_start_time:.2f}s)")

except DataError as e:
    logger.exception(f"FATAL ERROR during data loading/cleaning: {e}")
    sys.exit(1)
except Exception as e:
    logger.exception(f"FATAL ERROR during data loading/cleaning: {e}")
    sys.exit(1)


# 2. Generate Volume Breakout Signals
logger.info(f"\n[2/4] Generating Volume Breakout signals for {num_combinations:,} combinations...")
signal_start_time = time.time()
try:
    # Call the signal generator with the ranges
    # Assuming it returns entries, exits, _, _ (ignoring potential short signals if not used)
    vb_entries, vb_exits, _, _ = volume_breakout.generate_volume_signals(
        ohlcv_df=price_data, # Pass the full OHLCV dataframe
        volume_window_range=volume_window_range,
        volume_multiplier_range=volume_multiplier_range,
        exit_ma_window_range=exit_ma_window_range,
        confirm_price_increase=CONFIRM_PRICE_INCREASE
    )

    # Basic validation
    if vb_entries is None or vb_exits is None:
         raise SignalError("Volume signal generation returned None for entries or exits.")

    logger.info(f"Signals generated. Shape: {vb_entries.shape}. (Took {time.time() - signal_start_time:.2f}s)")

except SignalError as e:
     logger.exception(f"FATAL ERROR generating signals: {e}")
     sys.exit(1)
except ImportError:
    logger.exception("FATAL ERROR: Could not import volume_breakout module.")
    sys.exit(1)
except Exception as e:
    logger.exception(f"FATAL ERROR generating signals: {e}")
    sys.exit(1)


# 3. Run Simulation
logger.info(f"\n[3/4] Running backtest simulation...")
sim_start_time = time.time()
portfolio = None # Ensure reset
simulation_possible = False # Reset flag

# Check if any entry signals were generated
simulation_possible = vb_entries is not None and not vb_entries.empty and vb_entries.any().any()

if simulation_possible:
    try:
        portfolio = simulator.run_backtest(
            price_df=price_data,
            entries_series=vb_entries,
            exits_series=vb_exits,
            short_entries_series=None, # Volume breakout typically long-only
            short_exits_series=None,
            initial_capital=INITIAL_CAPITAL,
            fees=FEES,
            slippage=SLIPPAGE,
            frequency=DEFAULT_FREQ,
            size=DEFAULT_SIZE,
            size_type=DEFAULT_SIZE_TYPE,
            sl_stop=sl_stop_value,
            tp_stop=tp_stop_value
        )

        logger.info(f"Simulation complete. (Took {time.time() - sim_start_time:.2f}s)")
        # Validate portfolio object after simulation
        if portfolio is not None and hasattr(portfolio.wrapper, 'columns'):
            num_cols = len(portfolio.wrapper.columns)
            logger.info(f"Portfolio created with {num_cols} parameter combinations.")
            if num_cols == 0:
                logger.warning("Simulation ran but resulted in 0 portfolio columns (no valid trades?).")
                simulation_possible = False # Mark as not possible for analysis
        else:
            logger.warning("Simulation finished but portfolio object is None or invalid.")
            simulation_possible = False # Mark as not possible for analysis

    except PortfolioError as e:
        logger.exception(f"Error during simulation: {e}")
        simulation_possible = False
    except Exception as e:
        logger.exception(f"Error during simulation: {e}")
        simulation_possible = False
else:
     logger.warning("Skipping simulation because no valid entry signals were generated.")


# 4. Analyze and Plot Results
logger.info(f"\n[4/4] Analyzing results...")
analysis_start_time = time.time()
best_params = None # Ensure reset (will store the best param tuple)
best_stats = None # Ensure reset
best_trades_df = None # Ensure reset
aggregate_stats_df = None # Reset aggregate stats

if simulation_possible and portfolio is not None: # Re-check simulation_possible
    try:
        metric_to_optimize = 'Total Return [%]' # Use the exact column name from vbt stats
        logger.info(f"--- Identifying best combination based on '{metric_to_optimize}' ---")

        # --- Get Aggregate Stats (Optional but good for saving) ---
        try:
            all_stats_df = portfolio.stats(agg_func=None) # Get stats per column
            if isinstance(all_stats_df, pd.DataFrame) and not all_stats_df.empty:
                aggregate_stats_df = all_stats_df # Store for saving
                logger.info(f"Per-combination stats calculated. Shape: {aggregate_stats_df.shape}")
            else:
                logger.warning("portfolio.stats(agg_func=None) did not return a valid DataFrame.")
                aggregate_stats_df = None
        except Exception as agg_e:
            logger.exception(f"Warning: Could not generate aggregate stats table: {agg_e}")
            aggregate_stats_df = None

        # --- Find Best Combination using total_return() ---
        # total_return() is often simpler if only optimizing for that metric
        try:
            total_returns_series = portfolio.total_return() # Returns a Series indexed by param tuples

            if not total_returns_series.dropna().empty:
                best_params = total_returns_series.idxmax() # Get the index tuple of the max return
                best_return_value = total_returns_series.max()

                # Format best_params before logging for readability
                if isinstance(best_params, tuple) and len(best_params) == 3:
                    # Format: (vol_window, vol_multiplier, exit_ma_window)
                    best_params_print = f"({int(best_params[0])}, {best_params[1]:.2f}, {int(best_params[2])})"
                else:
                    best_params_print = str(best_params) # Fallback

                logger.info(f"Selected Best Combination Parameters: {best_params_print}")
                logger.info(f"   Best {metric_to_optimize}: {best_return_value * 100:.2f}%") # Convert return to percentage
            else:
                logger.warning(f"portfolio.total_return() returned an empty or all-NaN Series. Cannot determine best combination based on Total Return.")
                best_params = None # Ensure best_params is None

        except Exception as best_e:
            logger.exception(f"Error finding best parameters using total_return(): {best_e}")
            best_params = None # Ensure best_params is None if error occurs

        # --- Fallback if best parameters couldn't be found ---
        if best_params is None:
             logger.warning(f"Could not determine best parameters based on '{metric_to_optimize}'.")
             if not portfolio.wrapper.columns.empty:
                 best_params = portfolio.wrapper.columns[0] # Use the first column index tuple
                 logger.warning(f"Using first available combination as fallback: {best_params}")
             else:
                 logger.error("Portfolio has no columns to analyze. Cannot select fallback.")


        # --- Detailed Analysis for the Determined Best Combination ---
        if best_params is not None:
             # Verify the best_params index exists in the portfolio columns
             if best_params in portfolio.wrapper.columns:
                 # Format for display/logging
                 if isinstance(best_params, tuple) and len(best_params) == 3:
                     best_params_display = f"({int(best_params[0])}, {best_params[1]:.2f}, {int(best_params[2])})"
                 else:
                     best_params_display = str(best_params)

                 logger.info(f"\n--- Detailed Analysis for Best Combination {best_params_display} ---")
                 best_portfolio_slice = portfolio[best_params] # Slice the portfolio

                 # Get Stats for the best slice
                 try:
                     best_stats = metrics.get_summary_stats(best_portfolio_slice)
                     if best_stats is not None and not best_stats.empty:
                         logger.info("\n--- Performance Summary (Best Combination) ---")
                         for index, value in best_stats.items(): # Log stats line by line
                              logger.info(f"   {index}: {value}")
                     else:
                         logger.warning("Could not retrieve detailed stats for the best combination slice.")
                 except Exception as stats_err:
                     logger.exception(f"Error getting stats for best combination {best_params}: {stats_err}")

                 # Get Trades for the best slice
                 try:
                     best_trades_df = metrics.get_trade_records(best_portfolio_slice)
                     if best_trades_df is not None and not best_trades_df.empty:
                         logger.info("\n--- Trade Records (Best Combination - First 5) ---")
                         logger.info(best_trades_df.head().to_string()) # Log head() as string
                         logger.info(f"Total trades for best combination: {len(best_trades_df)}")
                     elif best_portfolio_slice is not None and best_portfolio_slice.trades.count() > 0:
                          logger.warning("Portfolio slice indicates trades exist, but fetching failed.")
                     else:
                          logger.info("No trades were executed for the best combination.")
                 except Exception as trades_err:
                     logger.exception(f"Error getting trades for best combination {best_params}: {trades_err}")

                 # Plotting (Optional - Consider moving saving logic to save_run_results)
                 # logger.info("\nGenerating plots for the best performing combination...")
                 # try:
                 #      if hasattr(plotting, 'plot_portfolio_summary') and hasattr(plotting, 'plot_trades'):
                 #          fig_summary = plotting.plot_portfolio_summary(best_portfolio_slice)
                 #          fig_trades = plotting.plot_trades(best_portfolio_slice, price_data)
                 #          logger.info("Plot generation functions called (display/return handled by function).")
                 #          # Optional: fig_summary.show(); fig_trades.show()
                 #      else:
                 #          logger.error("Plotting functions not found in analysis.plotting.")
                 # except Exception as plot_err:
                 #      logger.exception(f"ERROR during plot generation call for best combination: {plot_err}")

             else:
                 logger.error(f"Best parameters {best_params} determined but not found in portfolio columns. Skipping detailed analysis.")
                 best_params = None # Reset if invalid
        else:
             logger.warning("Skipping detailed analysis as no best combination could be determined.")

    except Exception as e:
        logger.exception(f"ERROR during analysis phase: {e}")

    logger.info(f"Analysis finished. (Took {time.time() - analysis_start_time:.2f}s)")
else:
     logger.warning("Skipping analysis because simulation was not possible or portfolio is invalid.")


# --- SAVE RESULTS ---
save_start_time = time.time()
# Proceed only if simulation ran, portfolio exists, and a valid best combination was found
if simulation_possible and portfolio is not None and best_params is not None and best_params in portfolio.wrapper.columns:
    logger.info("\n--- Saving Run Results ---")
    try:
        # Pass aggregate_stats_df if calculated, otherwise None
        results_dir = metrics.save_run_results(
            portfolio=portfolio,                # Pass full portfolio
            aggregate_stats=aggregate_stats_df, # Pass the per-column stats df if available
            best_params=best_params,            # Pass the best combo index (tuple)
            config_path=config_file,            # Pass config path
            strategy_name='volume_breakout',    # Specific strategy name
            symbol=SYMBOL,
            price_data_for_plots=price_data     # Data for plotting inside save function
        )
        if results_dir:
            logger.info(f"Results saved successfully to: {results_dir}")
        else:
            logger.warning("Saving results process completed, but no results directory path was returned.")
        logger.info(f"Saving complete. (Took {time.time() - save_start_time:.2f}s)")
    except Exception as save_err:
        logger.exception(f"ERROR saving results: {save_err}")

# Log reasons for skipping save if applicable
elif not simulation_possible:
    logger.warning("Skipping saving results because simulation was not possible or failed.")
elif portfolio is None:
     logger.warning("Skipping saving results because the portfolio object is None.")
elif best_params is None:
     logger.warning("Skipping saving results because best parameters were not determined or invalid.")
# No need for else, covers all failure cases for saving


# --- Finish ---
total_time = time.time() - overall_start_time
logger.info(f"\n--- Volume Breakout Backtest Script Finished ---")
logger.info(f"Total execution time: {total_time:.2f} seconds ({total_time/60:.2f} minutes)")
