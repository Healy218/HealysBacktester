# scripts/run_spy_rsi_backtest.py

# --- Standard Imports ---
import pandas as pd
import numpy as np
import sys
import os
import time # Import time module for estimating runtime
import warnings
import logging # Import logging first
import vectorbt as vbt # Import vbt early for version check
from typing import Optional, Union, Tuple, Any, List # For type hints, added List

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
    log_file_path = os.path.join(project_root, "logs", "rsi_backtest.log") # Specific log file
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
    from signals import rsi_threshold # Import the RSI signal generator
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
entries, exits, short_entries, short_exits = None, None, None, None
portfolio = None
best_params_for_saving = None # Will store the index tuple of the best combo
actual_portfolio_param_names = None # Store actual names from portfolio columns
aggregate_stats_df = None # Store stats df
config_file = os.path.join(project_root, 'config', 'settings.py')
overall_start_time = time.time()

# --- Load Configuration ---
logger.info("Loading configuration...")
try:
    config = config_parser.load_config(config_file)
    DATA_CONFIG = config.get('DATA_CONFIG', {})
    STRATEGY_CONFIG = config.get('STRATEGY_RSI', {}) # Use RSI section
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
    SL_PERCENT = BACKTEST_CONFIG.get('STOP_LOSS_PERCENT', None)
    USE_TP = BACKTEST_CONFIG.get('USE_TAKE_PROFIT', False)
    TP_PERCENT = BACKTEST_CONFIG.get('TAKE_PROFIT_PERCENT', None)

    sl_stop_value = SL_PERCENT if USE_SL and SL_PERCENT is not None else None
    tp_stop_value = TP_PERCENT if USE_TP and TP_PERCENT is not None else None

    # RSI Strategy Parameters
    RSI_WINDOW_START = STRATEGY_CONFIG.get('RSI_WINDOW_START', 10)
    RSI_WINDOW_END = STRATEGY_CONFIG.get('RSI_WINDOW_END', 31) # End is exclusive for arange
    RSI_WINDOW_STEP = STRATEGY_CONFIG.get('RSI_WINDOW_STEP', 1)
    rsi_window_range = np.arange(RSI_WINDOW_START, RSI_WINDOW_END, RSI_WINDOW_STEP, dtype=int)
    if rsi_window_range.size == 0: raise ValueError("RSI window range resulted in empty array.")

    ENTRY_THRESHOLD_START = STRATEGY_CONFIG.get('ENTRY_THRESHOLD_START', 20.0)
    ENTRY_THRESHOLD_END = STRATEGY_CONFIG.get('ENTRY_THRESHOLD_END', 40.0) # End is inclusive for linspace
    ENTRY_THRESHOLD_STEP = STRATEGY_CONFIG.get('ENTRY_THRESHOLD_STEP', 1.0)
    num_entry_steps = max(1, int(round((ENTRY_THRESHOLD_END - ENTRY_THRESHOLD_START) / ENTRY_THRESHOLD_STEP)) + 1)
    entry_threshold_range = np.linspace(ENTRY_THRESHOLD_START, ENTRY_THRESHOLD_END, num_entry_steps)
    if entry_threshold_range.size == 0: raise ValueError("Entry threshold range resulted in empty array.")


    EXIT_THRESHOLD_START = STRATEGY_CONFIG.get('EXIT_THRESHOLD_START', 60.0)
    EXIT_THRESHOLD_END = STRATEGY_CONFIG.get('EXIT_THRESHOLD_END', 80.0) # End is inclusive for linspace
    EXIT_THRESHOLD_STEP = STRATEGY_CONFIG.get('EXIT_THRESHOLD_STEP', 1.0)
    num_exit_steps = max(1, int(round((EXIT_THRESHOLD_END - EXIT_THRESHOLD_START) / EXIT_THRESHOLD_STEP)) + 1)
    exit_threshold_range = np.linspace(EXIT_THRESHOLD_START, EXIT_THRESHOLD_END, num_exit_steps)
    if exit_threshold_range.size == 0: raise ValueError("Exit threshold range resulted in empty array.")

    # Shorting parameters (simplified - assume they are handled similarly if enabled)
    ENABLE_SHORTING = STRATEGY_CONFIG.get('ENABLE_SHORTING', False) # Check if shorting is enabled in RSI config
    short_entry_threshold_range = None
    short_exit_threshold_range = None
    if ENABLE_SHORTING:
        # Example: Load short thresholds if enabled (replace with actual config keys)
        SHORT_ENTRY_START = STRATEGY_CONFIG.get('SHORT_ENTRY_THRESHOLD_START', 60.0)
        SHORT_ENTRY_END = STRATEGY_CONFIG.get('SHORT_ENTRY_THRESHOLD_END', 80.0)
        SHORT_ENTRY_STEP = STRATEGY_CONFIG.get('SHORT_ENTRY_THRESHOLD_STEP', 1.0)
        num_short_entry_steps = max(1, int(round((SHORT_ENTRY_END - SHORT_ENTRY_START) / SHORT_ENTRY_STEP)) + 1)
        short_entry_threshold_range = np.linspace(SHORT_ENTRY_START, SHORT_ENTRY_END, num_short_entry_steps)

        SHORT_EXIT_START = STRATEGY_CONFIG.get('SHORT_EXIT_THRESHOLD_START', 20.0)
        SHORT_EXIT_END = STRATEGY_CONFIG.get('SHORT_EXIT_THRESHOLD_END', 40.0)
        SHORT_EXIT_STEP = STRATEGY_CONFIG.get('SHORT_EXIT_THRESHOLD_STEP', 1.0)
        num_short_exit_steps = max(1, int(round((SHORT_EXIT_END - SHORT_EXIT_START) / SHORT_EXIT_STEP)) + 1)
        short_exit_threshold_range = np.linspace(SHORT_EXIT_START, SHORT_EXIT_END, num_short_exit_steps)
        if short_entry_threshold_range.size == 0 or short_exit_threshold_range.size == 0:
             raise ValueError("Short entry or exit threshold range resulted in empty array when shorting enabled.")


    # Expected parameter names in the order they are passed to the signal generator
    # This helps in formatting the output later.
    final_param_names = ['window', 'entry_threshold', 'exit_threshold']
    if ENABLE_SHORTING:
        final_param_names.extend(['short_entry_threshold', 'short_exit_threshold'])

    # Calculate theoretical combinations
    num_combinations = len(rsi_window_range) * len(entry_threshold_range) * len(exit_threshold_range)
    if ENABLE_SHORTING:
         num_combinations *= len(short_entry_threshold_range) * len(short_exit_threshold_range)

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


# --- Helper function to format parameter tuples ---
# (Keep this function as is, it's used for logging output)
def format_param_tuple(param_tuple: Union[Tuple[Any, ...], Any], actual_names: List[str]) -> str:
    if not isinstance(param_tuple, tuple):
        # Handle single parameter case
        if actual_names and len(actual_names) == 1:
            name = actual_names[0]
            val = param_tuple
            if "window" in name.lower(): return f"({name}={int(float(val))})"
            elif "thresh" in name.lower(): return f"({name}={float(val):.2f})"
            else: return f"({name}={val})"
        else:
             return str(param_tuple) # Fallback for unexpected single value

    num_params = len(param_tuple)
    names_to_use = actual_names[:num_params] # Use only available names
    formatted_params = []
    for i, val in enumerate(param_tuple):
        name = names_to_use[i] if i < len(names_to_use) else f"param_{i}" # Fallback name
        try:
            if "window" in name.lower():
                formatted_params.append(f"{name}={int(float(val))}")
            elif "thresh" in name.lower():
                formatted_params.append(f"{name}={float(val):.2f}")
            else:
                formatted_params.append(f"{name}={val}")
        except (ValueError, TypeError):
             formatted_params.append(f"{name}={val}") # Append raw value on format error
    return f"({', '.join(formatted_params)})"


# --- Print Run Info ---
logger.info(f"\n--- Starting RSI Threshold Parameter Optimization ---")
logger.info(f"Symbol: {SYMBOL}, Period: {START_DATE} to {END_DATE} ({INTERVAL})")
logger.info(f"RSI Window Range: {RSI_WINDOW_START} to {rsi_window_range[-1]} (Step: {RSI_WINDOW_STEP}) -> {len(rsi_window_range)} values")
logger.info(f"Long Entry Threshold Range: {entry_threshold_range.min():.2f} to {entry_threshold_range.max():.2f} (Steps: {len(entry_threshold_range)})")
logger.info(f"Long Exit Threshold Range: {exit_threshold_range.min():.2f} to {exit_threshold_range.max():.2f} (Steps: {len(exit_threshold_range)})")
logger.info(f"Shorting Enabled: {ENABLE_SHORTING}")
if ENABLE_SHORTING:
    logger.info(f"Short Entry Threshold Range: {short_entry_threshold_range.min():.2f} to {short_entry_threshold_range.max():.2f} (Steps: {len(short_entry_threshold_range)})")
    logger.info(f"Short Exit Threshold Range: {short_exit_threshold_range.min():.2f} to {short_exit_threshold_range.max():.2f} (Steps: {len(short_exit_threshold_range)})")
logger.info(f"Input Parameter Combinations (Theoretical): {num_combinations:,}")
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


# 2. Generate Signals
logger.info(f"\n[2/4] Generating RSI signals ({num_combinations:,} input combos, Shorting: {ENABLE_SHORTING})...")
signal_start_time = time.time()
try:
    # Pass the correct parameter ranges to the signal generator
    entries, exits, short_entries, short_exits = rsi_threshold.generate_rsi_signals(
        close_prices_series=price_data['Close'],
        window=rsi_window_range,
        entry_threshold=entry_threshold_range,
        exit_threshold=exit_threshold_range,
        enable_shorting=ENABLE_SHORTING,
        short_entry_threshold=short_entry_threshold_range, # Pass None if shorting disabled
        short_exit_threshold=short_exit_threshold_range   # Pass None if shorting disabled
        )

    # Basic validation
    if entries is None or exits is None:
         raise SignalError("RSI signal generation returned None for long entries or exits.")
    if ENABLE_SHORTING and (short_entries is None or short_exits is None):
         raise SignalError("RSI signal generation returned None for short entries or exits when shorting enabled.")

    logger.info(f"Signals generated. (Took {time.time() - signal_start_time:.2f}s)")
    if isinstance(entries, pd.DataFrame): logger.info(f"Long Entries/Exits Shape: {entries.shape}")
    if ENABLE_SHORTING and short_entries is not None:
        logger.info(f"Short Entries/Exits Shape: {short_entries.shape}")

except SignalError as e:
     logger.exception(f"FATAL ERROR generating signals: {e}")
     sys.exit(1)
except ImportError:
    logger.exception("FATAL ERROR: Could not import rsi_threshold module.")
    sys.exit(1)
except Exception as e:
    logger.exception(f"FATAL ERROR generating signals: {e}")
    sys.exit(1)


# 3. Run Simulation
logger.info(f"\n[3/4] Running backtest simulation...")
sim_start_time = time.time()
portfolio = None # Ensure reset
simulation_possible = False # Reset flag

# Check if any signals were generated
long_entries_exist = entries is not None and not entries.empty and entries.any().any()
short_entries_exist = False
if ENABLE_SHORTING and short_entries is not None and not short_entries.empty:
    short_entries_exist = short_entries.any().any()

simulation_possible = long_entries_exist or short_entries_exist

if simulation_possible:
    try:
        portfolio = simulator.run_backtest(
            price_df=price_data,
            entries_series=entries,
            exits_series=exits,
            short_entries_series=short_entries if ENABLE_SHORTING else None,
            short_exits_series=short_exits if ENABLE_SHORTING else None,
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
        # Validate portfolio and get actual column names/count
        if portfolio is not None and hasattr(portfolio.wrapper, 'columns'):
            num_simulated_combos = len(portfolio.wrapper.columns)
            logger.info(f"Portfolio created with {num_simulated_combos} columns (combinations).")
            if num_simulated_combos > 0:
                actual_portfolio_param_names = list(portfolio.wrapper.columns.names) # Get actual names from MultiIndex
                logger.info(f"Portfolio column index name(s): {actual_portfolio_param_names}")
                logger.info(f"Example column index value: {portfolio.wrapper.columns[0]}") # Log example tuple
            else:
                logger.warning("Simulation ran but resulted in 0 portfolio columns (no valid trades?).")
                simulation_possible = False
        else:
            logger.warning("Simulation finished but portfolio object is None or invalid.")
            simulation_possible = False

    except PortfolioError as e:
        logger.exception(f"Error during simulation: {e}")
        simulation_possible = False
    except Exception as e:
        logger.exception(f"Error during simulation: {e}")
        simulation_possible = False
else:
     logger.warning("Skipping simulation because no valid entry signals (long or short) were generated.")


# 4. Analyze Results
logger.info(f"\n[4/4] Analyzing results...")
analysis_start_time = time.time()
best_params_for_saving = None # Ensure reset
aggregate_stats_df = None # Ensure reset

if simulation_possible and portfolio is not None: # Re-check simulation_possible
    try:
        logger.info(f"--- Identifying Top Combinations using portfolio.stats(agg_func=None) ---")

        # Get the full stats table (Metrics=Columns, Combos=Index)
        all_stats_df = portfolio.stats(agg_func=None) # Get stats per column

        if all_stats_df is None or all_stats_df.empty:
            logger.error("portfolio.stats(agg_func=None) returned an empty or None DataFrame. Cannot analyze.")
            aggregate_stats_df = None # Ensure it's None
        else:
            aggregate_stats_df = all_stats_df # Store for potential saving
            logger.info(f"Per-combination stats calculated. Shape: {aggregate_stats_df.shape}")

            # Use actual parameter names identified after simulation for formatting, fallback to expected names
            param_names_for_fmt = actual_portfolio_param_names if actual_portfolio_param_names else final_param_names

            # --- Find Best Total Return ---
            metric_col_name = 'Total Return [%]'
            if metric_col_name in aggregate_stats_df.columns:
                try:
                    metric_series = aggregate_stats_df[metric_col_name].astype(float)
                    if not metric_series.dropna().empty:
                        best_return_params = metric_series.idxmax() # Get index tuple
                        best_return_value = metric_series.loc[best_return_params]
                        logger.info(f"Best {metric_col_name}: {best_return_value:.2f}%")
                        logger.info(f"   Params: {format_param_tuple(best_return_params, param_names_for_fmt)}")
                        best_params_for_saving = best_return_params # Set the best params based on return
                    else:
                         logger.warning(f"No valid (non-NaN) values found for '{metric_col_name}'.")
                except Exception as e:
                    logger.exception(f"Could not determine best for {metric_col_name}: {e}")
            else:
                logger.error(f"Metric '{metric_col_name}' not found in stats columns: {list(aggregate_stats_df.columns)}")

            # --- Find Best Total Trades (Example of another metric) ---
            metric_col_name = 'Total Trades'
            if metric_col_name in aggregate_stats_df.columns:
                try:
                    metric_series = aggregate_stats_df[metric_col_name].astype(float) # Ensure numeric
                    if not metric_series.dropna().empty:
                         best_trades_params = metric_series.idxmax()
                         best_trades_value = metric_series.loc[best_trades_params]
                         logger.info(f"Most {metric_col_name}: {int(best_trades_value)}")
                         logger.info(f"   Params: {format_param_tuple(best_trades_params, param_names_for_fmt)}")
                    else:
                         logger.warning(f"No valid (non-NaN) values found for '{metric_col_name}'.")
                except Exception as e:
                    logger.exception(f"Could not determine best for {metric_col_name}: {e}")
            else:
                logger.warning(f"Metric '{metric_col_name}' not found in stats columns.") # Warning, not error

            # --- Find Best Sharpe Ratio (Example) ---
            metric_col_name = 'Sharpe Ratio'
            if metric_col_name in aggregate_stats_df.columns:
                try:
                    metric_series = aggregate_stats_df[metric_col_name].replace([np.inf, -np.inf], np.nan).astype(float)
                    if not metric_series.dropna().empty:
                        best_sharpe_params = metric_series.idxmax()
                        best_sharpe_value = metric_series.loc[best_sharpe_params]
                        logger.info(f"Best {metric_col_name}: {best_sharpe_value:.3f}")
                        logger.info(f"   Params: {format_param_tuple(best_sharpe_params, param_names_for_fmt)}")
                    else:
                         logger.warning(f"No valid (non-NaN, non-inf) values found for '{metric_col_name}'.")
                except Exception as e:
                    logger.exception(f"Could not determine best for {metric_col_name}: {e}")
            else:
                logger.warning(f"Metric '{metric_col_name}' not found in stats columns.")

        # --- Detailed Analysis for BEST RETURN Combination ---
        if best_params_for_saving is not None:
             # Verify the best_params_for_saving index exists in the portfolio columns
             if best_params_for_saving in portfolio.wrapper.columns:
                 param_names_for_fmt_detail = actual_portfolio_param_names if actual_portfolio_param_names else final_param_names
                 best_return_params_str = format_param_tuple(best_params_for_saving, param_names_for_fmt_detail)
                 logger.info(f"\n--- Detailed Analysis for Best *Return* Combination {best_return_params_str} ---")
                 best_portfolio_slice = portfolio[best_params_for_saving] # Slice portfolio

                 # Get Stats for the slice
                 try:
                     best_stats_summary = metrics.get_summary_stats(best_portfolio_slice)
                     if best_stats_summary is not None and not best_stats_summary.empty:
                         logger.info("\n--- Performance Summary (Best Return Combo) ---")
                         for index, value in best_stats_summary.items():
                              logger.info(f"   {index}: {value}")
                     else:
                         logger.warning("Could not retrieve summary stats for the best return combination.")
                 except Exception as stats_err:
                     logger.exception(f"Error getting stats for best return combination {best_params_for_saving}: {stats_err}")

                 # Get Trades for the slice
                 try:
                     best_trades_df = metrics.get_trade_records(best_portfolio_slice)
                     if best_trades_df is not None and not best_trades_df.empty:
                         logger.info("\n--- Trade Records (Best Return Combo - First 5) ---")
                         logger.info(best_trades_df.head().to_string())
                         logger.info(f"Total trades for best return combination: {len(best_trades_df)}")
                     elif best_portfolio_slice is not None and best_portfolio_slice.trades.count() > 0:
                          logger.warning("Portfolio slice indicates trades exist, but fetching failed.")
                     else:
                          logger.info("No trades were executed for the best return combination.")
                 except Exception as trades_err:
                      logger.exception(f"Error getting trades for best return combination {best_params_for_saving}: {trades_err}")

             else:
                 logger.error(f"Best return params '{best_params_for_saving}' determined but not found in portfolio columns. Skipping detailed analysis.")
                 best_params_for_saving = None # Reset if invalid
        else:
             logger.warning("Skipping detailed analysis: No best return combination found or determined.")

    except Exception as e:
        logger.exception(f"ERROR during analysis phase: {e}")

    logger.info(f"Analysis finished. (Took {time.time() - analysis_start_time:.2f}s)")
else:
     logger.warning("Skipping analysis because simulation was not possible or portfolio is invalid.")


# --- SAVE RESULTS ---
save_start_time = time.time()
# Proceed only if simulation ran, portfolio exists, and a valid best combination was found
if simulation_possible and portfolio is not None and best_params_for_saving is not None and best_params_for_saving in portfolio.wrapper.columns:
    logger.info("\n--- Saving Run Results ---")
    try:
        # Pass the aggregate_stats_df which contains stats for all valid combinations
        results_dir = metrics.save_run_results(
            portfolio=portfolio,                # Pass full portfolio
            aggregate_stats=aggregate_stats_df, # Pass the per-column stats df
            best_params=best_params_for_saving, # Pass the best combo index (tuple)
            config_path=config_file,            # Pass config path
            strategy_name='rsi_threshold_optimized', # Specific strategy name
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
elif best_params_for_saving is None:
     logger.warning("Skipping saving results because best parameters were not determined or invalid.")
# No need for else, covers all failure cases for saving


# --- Finish ---
total_time = time.time() - overall_start_time
logger.info(f"\n--- RSI Backtest Script Finished ---")
logger.info(f"Total execution time: {total_time:.2f} seconds ({total_time/60:.2f} minutes)")

