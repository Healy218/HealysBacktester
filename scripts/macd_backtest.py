# scripts/run_spy_macd_backtest.py

# --- Standard Imports ---
import pandas as pd
import numpy as np
import sys
import os
import time # For timing
import warnings
import logging # Import logging first
import vectorbt as vbt # Import vbt early for version check

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
    log_file_path = os.path.join(project_root, "logs", "macd_backtest.log")
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
    from signals import macd_signals # Import the MACD signal generator
    from portfolio import simulator
    from analysis import metrics, plotting
    from utils import config_parser, freq_utils
    from data import vbt_data_loader as data_loader, data_cleaner
    # Import custom error types
    from utils.error_handling import DataError, SignalError, PortfolioError, ConfigurationError
except ImportError as import_err:
    logger.exception(f"FATAL ERROR: Failed to import necessary project modules: {import_err}")
    sys.exit(1)

# --- Initialize Variables ---
# Initialize key variables to None or default values
price_data = None
entries, exits, short_entries, short_exits = None, None, None, None
portfolio = None
best_col_name = None
aggregate_stats_df = None
config_file = os.path.join(project_root, 'config', 'settings.py')
overall_start_time = time.time() # Start overall timer

# --- Load Configuration ---
logger.info("Loading configuration...")
try:
    config = config_parser.load_config(config_file)
    DATA_CONFIG = config.get('DATA_CONFIG', {})
    STRATEGY_CONFIG = config.get('STRATEGY_MACD', {}) # Use MACD section
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

    # Backtest Settings
    INITIAL_CAPITAL = BACKTEST_CONFIG.get('INITIAL_CAPITAL', 100000.0)
    FEES = BACKTEST_CONFIG.get('FEES_PERCENT', 0.001)
    SLIPPAGE = BACKTEST_CONFIG.get('SLIPPAGE_PERCENT', 0.0005)
    DEFAULT_FREQ = freq_utils.resolve_freq(BACKTEST_CONFIG.get('DEFAULT_FREQ'), INTERVAL)

    # Sizing Settings
    DEFAULT_SIZE = BACKTEST_CONFIG.get('DEFAULT_SIZE', 0.99)
    DEFAULT_SIZE_TYPE = BACKTEST_CONFIG.get('DEFAULT_SIZE_TYPE', 'percent')

    # Stop Loss / Take Profit Settings
    USE_SL = BACKTEST_CONFIG.get('USE_STOP_LOSS', False)
    SL_PERCENT = BACKTEST_CONFIG.get('STOP_LOSS_PERCENT', None) # Default to None if not specified
    USE_TP = BACKTEST_CONFIG.get('USE_TAKE_PROFIT', False)
    TP_PERCENT = BACKTEST_CONFIG.get('TAKE_PROFIT_PERCENT', None) # Default to None if not specified

    # Determine SL/TP values to pass (explicitly handle None)
    sl_stop_value = SL_PERCENT if USE_SL and SL_PERCENT is not None else None
    tp_stop_value = TP_PERCENT if USE_TP and TP_PERCENT is not None else None

    # MACD Strategy Parameters
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

    # MACD Shorting Flags
    ENABLE_MACD_SHORTS = STRATEGY_CONFIG.get('SHORT_ENTRIES_ENABLED', False)
    ENABLE_MACD_SHORT_EXITS = STRATEGY_CONFIG.get('SHORT_EXITS_ENABLED', False) # Often same as entry flag for simple crossovers

    num_combinations = len(fast_windows) * len(slow_windows) * len(signal_windows)
    logger.info("Parameters extracted successfully.")

except KeyError as e:
    logger.exception(f"FATAL ERROR: Missing expected key in configuration: {e}")
    sys.exit(1)
except ValueError as e: # Catch specific value errors from np.arange checks
    logger.exception(f"FATAL ERROR: Invalid MACD range parameter in settings.py: {e}")
    sys.exit(1)
except Exception as e:
    logger.exception(f"FATAL ERROR: Error processing configuration parameters: {e}")
    sys.exit(1)


# --- Print Run Info ---
logger.info(f"\n--- Starting MACD Crossover Backtest (Optimized) ---")
logger.info(f"Symbol: {SYMBOL}, Period: {START_DATE} to {END_DATE} ({INTERVAL})")
logger.info(f"Strategy Params (Ranges):")
logger.info(f"  Fast Window: {fast_start}-{fast_end-1} (Step: {fast_step}) -> {len(fast_windows)} values")
logger.info(f"  Slow Window: {slow_start}-{slow_end-1} (Step: {slow_step}) -> {len(slow_windows)} values")
logger.info(f"  Signal Window: {signal_start}-{signal_end-1} (Step: {signal_step}) -> {len(signal_windows)} values")
logger.info(f"Total Parameter Combinations (theoretically): {num_combinations:,}")
logger.info(f"Note: vectorbt automatically generates combinations. Invalid ones (fast >= slow) might result in NaNs or be excluded.")
logger.info(f"Backtest Settings: Initial Capital=${INITIAL_CAPITAL:,.2f}, Fees={FEES:.3%}, Slippage={SLIPPAGE:.3%}")
logger.info(f"Sizing: Size={DEFAULT_SIZE}, Size Type='{DEFAULT_SIZE_TYPE}'")
logger.info(f"Stop Loss: {'Enabled' if sl_stop_value else 'Disabled'}{f' ({SL_PERCENT:.1%})' if sl_stop_value else ''}")
logger.info(f"Take Profit: {'Enabled' if tp_stop_value else 'Disabled'}{f' ({TP_PERCENT:.1%})' if tp_stop_value else ''}")
logger.info(f"MACD Shorting Enabled: {ENABLE_MACD_SHORTS}")
logger.info("-" * 35)


# --- Workflow ---

# 1. Load and Clean Data
logger.info(f"\n[1/4] Loading and cleaning data for {SYMBOL}...")
load_start = time.time()
try:
    raw_data = data_loader.load_price_data_smart(
        symbol=SYMBOL, start_date=START_DATE, end_date=END_DATE, interval=INTERVAL
    )
    if raw_data is None or raw_data.empty:
        raise DataError(f"Data loading returned empty or None for {SYMBOL}.")

    price_data = data_cleaner.clean_ohlcv_data(raw_data)
    if price_data is None or price_data.empty:
        raise DataError(f"Data cleaning returned empty or None for {SYMBOL}.")

    logger.info(f"Data loading and cleaning successful. Final shape: {price_data.shape}. (Took {time.time() - load_start:.2f}s)")

except DataError as e:
    logger.exception(f"FATAL ERROR during data loading/cleaning: {e}")
    sys.exit(1)
except Exception as e:
    logger.exception(f"FATAL ERROR during data loading/cleaning: {e}")
    sys.exit(1)

# 2. Generate MACD Signals
logger.info(f"\n[2/4] Generating MACD signals using parameter ranges (Shorting: {ENABLE_MACD_SHORTS})...")
signal_start_time = time.time()
try:
    entries, exits, short_entries, short_exits = macd_signals.generate_macd_signals(
        close_prices_series=price_data['Close'],
        fast_window=fast_windows,
        slow_window=slow_windows,
        signal_window=signal_windows,
        short_entries=ENABLE_MACD_SHORTS,
        short_exits=ENABLE_MACD_SHORT_EXITS # Pass the short exit flag
    )
    # Basic validation
    if entries is None or exits is None:
         raise SignalError("MACD signal generation returned None for long entries or exits.")
    if ENABLE_MACD_SHORTS and (short_entries is None or short_exits is None):
         raise SignalError("MACD signal generation returned None for short entries or exits when shorting enabled.")

    logger.info(f"Signals generated. (Took {time.time() - signal_start_time:.2f}s)")
    if isinstance(entries, pd.DataFrame): logger.info(f"Long Entries/Exits Shape: {entries.shape}")
    if ENABLE_MACD_SHORTS and short_entries is not None:
        logger.info(f"Short Entries/Exits Shape: {short_entries.shape}")

except SignalError as e:
     logger.exception(f"FATAL ERROR generating signals: {e}")
     sys.exit(1)
except ImportError: # Specific error if module not found
    logger.exception("FATAL ERROR: Could not import macd_signals module.")
    sys.exit(1)
except Exception as e:
    logger.exception(f"FATAL ERROR generating signals: {e}")
    sys.exit(1)


# 3. Run Simulation
logger.info(f"\n[3/4] Running backtest simulation...")
sim_start_time = time.time()
portfolio = None # Ensure portfolio is reset before try block
simulation_possible = False # Reset flag

# Check if any signals were generated before attempting simulation
long_entries_exist = entries is not None and not entries.empty and entries.any().any()
short_entries_exist = False
if ENABLE_MACD_SHORTS and short_entries is not None and not short_entries.empty:
    short_entries_exist = short_entries.any().any()

# Simulation is possible if either long or short entries exist
simulation_possible = long_entries_exist or short_entries_exist

if simulation_possible:
    try:
        portfolio = simulator.run_backtest(
            price_df=price_data,
            entries_series=entries,
            exits_series=exits,
            short_entries_series=short_entries if ENABLE_MACD_SHORTS else None, # Pass None if shorting disabled
            short_exits_series=short_exits if ENABLE_MACD_SHORTS else None,     # Pass None if shorting disabled
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
     logger.warning("Skipping simulation because no valid entry signals (long or short) were generated.")


# 4. Analyze and Plot Results
logger.info(f"\n[4/4] Analyzing results...")
analysis_start_time = time.time()
best_col_name = None # Ensure reset
aggregate_stats_df = None # Ensure reset
best_stats = None # Ensure reset
best_trades_df = None # Ensure reset


if simulation_possible and portfolio is not None: # Re-check simulation_possible
    try:
        logger.info("Calculating aggregate performance stats across all combinations...")
        try:
            # Get stats for all columns without aggregation first
            all_stats_df = portfolio.stats(agg_func=None) # Get stats per column

            if isinstance(all_stats_df, pd.DataFrame) and not all_stats_df.empty:
                aggregate_stats_df = all_stats_df # Store the raw per-column stats
                logger.info(f"Per-combination stats calculated. Shape: {aggregate_stats_df.shape}")

                # --- Filter out invalid combinations (fast >= slow) ---
                original_combo_count = len(aggregate_stats_df)
                if isinstance(aggregate_stats_df.index, pd.MultiIndex) and \
                   all(name in aggregate_stats_df.index.names for name in ['fast_window', 'slow_window']):
                    valid_mask = aggregate_stats_df.index.get_level_values('fast_window') < aggregate_stats_df.index.get_level_values('slow_window')
                    aggregate_stats_df = aggregate_stats_df[valid_mask]
                    filtered_count = original_combo_count - len(aggregate_stats_df)
                    if filtered_count > 0:
                         logger.info(f"Filtered out {filtered_count} combinations where fast_window >= slow_window.")
                    else:
                         logger.info("No combinations needed filtering (fast_window < slow_window for all).")
                else:
                    logger.warning("Could not filter fast >= slow: Index is not the expected MultiIndex ('fast_window', 'slow_window', 'signal_window').")
                # --- End Filtering ---

            else:
                logger.warning("portfolio.stats(agg_func=None) did not return a valid DataFrame.")
                aggregate_stats_df = None # Ensure it's None

        except Exception as agg_e:
            logger.exception(f"Warning: Could not generate aggregate stats table: {agg_e}")
            aggregate_stats_df = None # Ensure it's None

        # --- Identify Best Combination ---
        metric_to_optimize = 'Total Return [%]' # Or 'Sharpe Ratio', 'Sortino Ratio', etc.
        logger.info(f"\n--- Identifying best combination based on '{metric_to_optimize}' (after filtering) ---")

        if aggregate_stats_df is not None and not aggregate_stats_df.empty:
            if metric_to_optimize in aggregate_stats_df.columns:
                # Convert to float and handle potential NaNs before finding max
                metric_series = aggregate_stats_df[metric_to_optimize].astype(float)
                if not metric_series.dropna().empty:
                    best_col_name = metric_series.idxmax() # Get the index (MultiIndex tuple)
                    best_metric_value = metric_series.loc[best_col_name]
                    logger.info(f"Selected Best Combination Parameters: {best_col_name}")
                    logger.info(f"   Best {metric_to_optimize}: {best_metric_value:.2f}%")
                else:
                    logger.warning(f"No valid (non-NaN) values found for '{metric_to_optimize}' after filtering.")
                    # Fallback: use first available combination if metric fails
                    if not aggregate_stats_df.index.empty:
                        best_col_name = aggregate_stats_df.index[0]
                        logger.warning(f"Using first valid combination as fallback: {best_col_name}")
                    else:
                        logger.error("No valid combinations left after filtering. Cannot select best.")
            else:
                logger.error(f"Metric '{metric_to_optimize}' not found in stats columns: {list(aggregate_stats_df.columns)}")
        else:
            logger.warning("Could not determine best combination (aggregate stats missing or empty after filtering).")


        # --- Detailed Analysis for Best Combination ---
        if best_col_name is not None:
             # Verify the best_col_name exists in the original portfolio columns before slicing
             if best_col_name in portfolio.wrapper.columns:
                 logger.info(f"\n--- Detailed Analysis for Best Combination {best_col_name} ---")
                 best_portfolio_slice = portfolio[best_col_name] # Slice the portfolio

                 # Get Stats for the best slice
                 try:
                     best_stats = metrics.get_summary_stats(best_portfolio_slice) # Pass the slice
                     if best_stats is not None and not best_stats.empty:
                         logger.info("\n--- Performance Summary (Best Combination) ---")
                         for index, value in best_stats.items(): # Log stats line by line
                              logger.info(f"   {index}: {value}")
                     else:
                         logger.warning("Could not retrieve detailed stats for the best combination slice.")
                 except Exception as stats_err:
                     logger.exception(f"Error getting stats for best combination {best_col_name}: {stats_err}")

                 # Get Trades for the best slice
                 try:
                     best_trades_df = metrics.get_trade_records(best_portfolio_slice) # Pass the slice
                     if best_trades_df is not None and not best_trades_df.empty:
                         logger.info("\n--- Trade Records (Best Combination - First 5) ---")
                         logger.info(best_trades_df.head().to_string()) # Log head() as string
                         logger.info(f"Total trades for best combination: {len(best_trades_df)}")
                     elif best_portfolio_slice is not None and best_portfolio_slice.trades.count() > 0:
                          logger.warning("Portfolio slice indicates trades exist, but fetching failed.")
                     else:
                          logger.info("No trades were executed for the best combination.")
                 except Exception as trades_err:
                     logger.exception(f"Error getting trades for best combination {best_col_name}: {trades_err}")

                 # Plotting (Optional - Consider if plots should be saved by save_run_results instead)
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
                 logger.error(f"Determined best combination index '{best_col_name}' not found in portfolio columns. Analysis skipped.")
                 best_col_name = None # Reset if invalid
        else:
             logger.warning("Skipping detailed analysis as no best combination could be determined.")

    except Exception as e:
        logger.exception(f"ERROR during analysis phase: {e}")

    logger.info(f"Analysis finished. (Took {time.time() - analysis_start_time:.2f}s)")

else:
     logger.warning("Skipping analysis because simulation was not possible or portfolio is invalid.")


# --- Save Results ---
save_start_time = time.time()
# Proceed only if simulation ran, portfolio exists, and a valid best combination was found
if simulation_possible and portfolio is not None and best_col_name is not None and best_col_name in portfolio.wrapper.columns:
    logger.info("\n--- Saving Run Results ---")
    try:
        results_dir = metrics.save_run_results(
            portfolio=portfolio,                # Pass full portfolio
            aggregate_stats=aggregate_stats_df, # Pass the filtered aggregate stats
            best_params=best_col_name,          # Pass the best combo index (tuple)
            config_path=config_file,            # Pass config path
            strategy_name='macd_optimized',     # Specific strategy name
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
elif best_col_name is None:
     logger.warning("Skipping saving results because best parameters were not determined or invalid.")
# No need for else, covers all failure cases for saving

# --- Finish ---
total_time = time.time() - overall_start_time
logger.info(f"\n--- MACD Backtest Script Finished ---")
logger.info(f"Total execution time: {total_time:.2f} seconds ({total_time/60:.2f} minutes)")