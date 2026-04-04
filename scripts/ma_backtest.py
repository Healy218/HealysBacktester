# filename: HealysBacktester/scripts/run_spy_ma_backtest.py

# --- Standard Imports ---
import pandas as pd
import numpy as np
import sys
import os
import traceback # Keep for potential explicit use if needed, but logger.exception is preferred
import vectorbt as vbt
import logging # Import logging first

# --- Print Versions (Before Logging is Setup) ---
# These prints are okay here as they provide immediate startup info
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
    # project_root = os.path.dirname(os.path.dirname(script_dir)) # Go up two levels <--- INCORRECT
    project_root = os.path.dirname(script_dir) # Go up ONE level <--- CORRECT
    if project_root not in sys.path:
        sys.path.insert(0, str(project_root))
    print(f"Project Root added to path: {project_root}")
except NameError:
    print("Warning: Could not determine script directory automatically.")
    project_root = '.' # Assume running from project root
    if project_root not in sys.path:
        sys.path.insert(0, str(project_root))
# --- End Path Modification ---

# --- Setup Logging (AFTER path modification) ---
# It's crucial to set up logging after the path is potentially modified
# so it can find the logging_utils module correctly.
try:
    from utils.logging_utils import setup_logging
    # Configure logging - adjust log file path/name as needed
    log_file_path = os.path.join(project_root, "logs", "ma_backtest.log")
    logger = setup_logging(log_level=logging.INFO, log_file=log_file_path)
    logger.info("Logging setup complete.")
except ImportError:
    # Fallback basic logging if setup fails (e.g., utils not found)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    logger.error("Failed to import setup_logging from utils.logging_utils. Using basic console logging.")
except Exception as log_setup_err:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    logger.error(f"Error setting up file logging: {log_setup_err}. Using basic console logging.")


# --- Import project modules (AFTER logging setup) ---
# Now import other modules. If they use logging, they'll use the config we just set.
try:
    from signals import ma_crossover # Import the updated MA signal generator
    from portfolio import simulator
    from analysis import metrics, plotting
    from utils import config_parser, freq_utils
    from data import data_loader, data_cleaner
    # Import custom error types to potentially catch them specifically
    from utils.error_handling import DataError, SignalError, PortfolioError, ConfigurationError
except ImportError as import_err:
    logger.exception(f"FATAL ERROR: Failed to import necessary project modules: {import_err}")
    sys.exit(1) # Use sys.exit for cleaner exit

# --- Load Configuration ---
logger.info("Loading configuration...")
try:
    config_file = os.path.join(project_root, 'config', 'settings.py')
    config = config_parser.load_config(config_file)
    DATA_CONFIG = config.get('DATA_CONFIG', {})
    STRATEGY_CONFIG = config.get('STRATEGY_MA_CROSSOVER', {})
    BACKTEST_CONFIG = config.get('BACKTEST_CONFIG', {})
    logger.info(f"Configuration loaded successfully from: {config_file}")
except FileNotFoundError:
    logger.exception(f"FATAL ERROR: Configuration file '{config_file}' not found.") # Use exception logger
    sys.exit(1)
except ConfigurationError as config_err: # Catch specific config error
     logger.exception(f"FATAL ERROR: Configuration error: {config_err}")
     sys.exit(1)
except Exception as e:
    logger.exception(f"FATAL ERROR: Could not load configuration: {e}") # Use exception logger
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

    # Determine SL/TP values to pass
    sl_stop_value = SL_PERCENT if USE_SL and SL_PERCENT is not None else None
    tp_stop_value = TP_PERCENT if USE_TP and TP_PERCENT is not None else None

    # MA Crossover Strategy Parameters
    MA_WINDOW_START = STRATEGY_CONFIG.get('MA_WINDOW_START', 2)
    MA_WINDOW_END = STRATEGY_CONFIG.get('MA_WINDOW_END', 101)
    MA_WINDOW_STEP = STRATEGY_CONFIG.get('MA_WINDOW_STEP', 1)

    # Create the window range array
    windows_range = np.arange(MA_WINDOW_START, MA_WINDOW_END, MA_WINDOW_STEP)
    if windows_range.size < 2:
        # Use logger for fatal errors and exit
        logger.critical(f"FATAL ERROR: Window range defined in settings ({MA_WINDOW_START} to {MA_WINDOW_END-1}) is too small for dual MA combinations.")
        sys.exit(1)

    num_combinations = windows_range.size * (windows_range.size - 1) // 2
    logger.info("Parameters extracted successfully.")

except KeyError as e:
    logger.exception(f"FATAL ERROR: Missing expected key in configuration: {e}")
    sys.exit(1)
except Exception as e:
    logger.exception(f"FATAL ERROR: Error processing configuration parameters: {e}")
    sys.exit(1)


# --- Print Run Info ---
logger.info(f"\n--- Starting MA Crossover Parameter Optimization (vectorbt) ---")
logger.info(f"Symbol: {SYMBOL}, Period: {START_DATE} to {END_DATE} ({INTERVAL})")
logger.info(f"MA Window Range for Combinations: {MA_WINDOW_START} to {MA_WINDOW_END - 1}")
logger.info(f"Estimated Number of Combinations (short < long): {num_combinations}")
logger.info(f"Backtest Settings: Initial Capital=${INITIAL_CAPITAL:,.2f}, Fees={FEES:.3%}, Slippage={SLIPPAGE:.3%}")
logger.info(f"Sizing: Size={DEFAULT_SIZE}, Size Type='{DEFAULT_SIZE_TYPE}'")
logger.info(f"Stop Loss: {'Enabled' if sl_stop_value else 'Disabled'}{f' ({SL_PERCENT:.1%})' if sl_stop_value else ''}")
logger.info(f"Take Profit: {'Enabled' if tp_stop_value else 'Disabled'}{f' ({TP_PERCENT:.1%})' if tp_stop_value else ''}")
logger.info("-" * 35)

# --- Initialize Variables ---
price_data = None
entries, exits = None, None
portfolio = None
best_params = None # Use tuple (fast_window, slow_window)

# --- Workflow ---

# 1. Load and Clean Data using Modules
logger.info(f"\n[1/4] Loading and cleaning data for {SYMBOL}...")
try:
    # Assume load_price_data and clean_ohlcv_data might raise DataError or other exceptions
    # If they have the @handle_errors decorator, errors will be logged there too.
    raw_data = data_loader.load_price_data(
        symbol=SYMBOL, start_date=START_DATE, end_date=END_DATE, interval=INTERVAL
    )
    # Add checks for None or empty dataframes after loading/cleaning
    if raw_data is None or raw_data.empty:
         raise DataError(f"Data loading returned empty or None for {SYMBOL}.") # Raise specific error

    price_data = data_cleaner.clean_ohlcv_data(raw_data)
    if price_data is None or price_data.empty:
         raise DataError(f"Data cleaning returned empty or None for {SYMBOL}.") # Raise specific error

    logger.info(f"Data loading and cleaning successful. Final shape: {price_data.shape}")

except DataError as e: # Catch specific data errors
    logger.exception(f"FATAL ERROR during data loading/cleaning: {e}")
    sys.exit(1)
except Exception as e: # Catch any other unexpected errors
    logger.exception(f"FATAL ERROR during data loading/cleaning: {e}") # Use logger.exception
    sys.exit(1)

# 2. Generate MA Crossover Signals using the updated module
logger.info(f"\n[2/4] Generating MA Crossover signals using vectorbt combinations...")
try:
    # Assume generate_ma_signals might raise SignalError or other exceptions
    entries, exits = ma_crossover.generate_ma_signals(
        close_prices_series=price_data['Close'],
        windows_range=windows_range
    )
    if entries is None or exits is None:
        raise SignalError("Signal generation returned None for entries or exits.")
    logger.info("MA Crossover signals generated.")
    if isinstance(entries, pd.DataFrame): logger.info(f"Entries/Exits Shape: {entries.shape}")

except SignalError as e: # Catch specific signal errors
    logger.exception(f"FATAL ERROR generating signals: {e}")
    sys.exit(1)
except Exception as e:
    logger.exception(f"FATAL ERROR generating signals: {e}") # Use logger.exception
    sys.exit(1)

# 3. Run Simulation
logger.info(f"\n[3/4] Running backtest simulation...")
portfolio = None
# Check if any entry signals were generated before attempting simulation
simulation_possible = entries is not None and not entries.empty and entries.any().any()

if simulation_possible:
    try:
        # Assume run_backtest might raise PortfolioError or other exceptions
        portfolio = simulator.run_backtest(
            price_df=price_data,
            entries_series=entries,
            exits_series=exits,
            short_entries_series=None, # No short signals for this strategy
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
        if portfolio is not None:
            logger.info(f"Portfolio object created with {len(portfolio.wrapper.columns)} columns (combinations).")
        else:
            # This case might indicate an issue within run_backtest even if no exception was raised
            logger.warning("Simulation finished but portfolio object is None.")
            simulation_possible = False # Prevent further analysis

    except PortfolioError as e: # Catch specific portfolio errors
        logger.exception(f"Error during simulation: {e}")
        simulation_possible = False # Prevent further analysis
    except Exception as e:
        logger.exception(f"Error during simulation: {e}") # Use logger.exception
        simulation_possible = False # Prevent further analysis
else:
     logger.warning("Skipping simulation because no valid entry signals were generated.") # Use warning


# 4. Analyze Results (Find best combination) and Plot
logger.info(f"\n[4/4] Analyzing results...")
best_params = None
best_stats = None # Initialize best_stats
best_trades_df = None # Initialize best_trades_df

if simulation_possible and portfolio is not None:
    try:
        # --- Identify Best Combination using portfolio.total_return() ---
        metric_to_optimize = 'Total Return'
        best_return_value = -np.inf # Initialize with negative infinity

        logger.info(f"\n--- Identifying best combination based on '{metric_to_optimize}' ---")
        try:
            total_returns_series = portfolio.total_return()

            if not total_returns_series.empty:
                best_params = total_returns_series.idxmax()
                best_return_value = total_returns_series.max()
                logger.info(f"Selected Best Combination Parameters: {best_params}")
                logger.info(f"   Best {metric_to_optimize}: {best_return_value * 100:.2f}%")
            else:
                logger.warning("portfolio.total_return() returned an empty Series. Cannot determine best combination.") # Use warning

        except Exception as best_e:
            logger.exception(f"Error finding best parameters using total_return(): {best_e}")
            best_params = None # Ensure best_params is None if error occurs

        # --- Fallback if best parameters couldn't be found ---
        if best_params is None and not total_returns_series.empty: # Check if series was empty too
             logger.warning(f"Could not determine best parameters based on '{metric_to_optimize}'.") # Use warning
             if not portfolio.wrapper.columns.empty:
                  best_params = portfolio.wrapper.columns[0]
                  logger.warning(f"Using first available combination as fallback: {best_params}") # Use warning
             else:
                  logger.error("Portfolio has no columns to analyze. Cannot select fallback.") # Use error

        # --- Analyze and Plot details for BEST Combination ---
        if best_params is not None and best_params in portfolio.wrapper.columns:
            logger.info(f"\n--- Detailed Analysis for Best Combination {best_params} ---")
            best_portfolio_slice = portfolio[best_params]

            # Get Stats
            try:
                best_stats = metrics.get_summary_stats(best_portfolio_slice)
                if best_stats is not None and not best_stats.empty:
                     logger.info("\n--- Performance Summary (Best Combination) ---")
                     # Log the series content line by line for better readability in logs
                     for index, value in best_stats.items():
                         logger.info(f"  {index}: {value}")
                else:
                     logger.warning("Could not retrieve detailed stats for the best combination.") # Use warning
            except Exception as stats_err:
                logger.exception(f"Error getting stats for best combination: {stats_err}")


            # Plotting
            if best_stats is not None: # Only plot if stats were successfully retrieved
                logger.info("\nGenerating plots for the best performing combination...")
                try:
                    # Ensure plotting functions exist and handle potential errors
                    if hasattr(plotting, 'plot_portfolio_summary') and hasattr(plotting, 'plot_trades'):
                         # Call plotting functions without save_fig/results_dir
                         # These functions should ideally just display or return the figure
                         # Saving should be handled by save_run_results if needed
                         fig_summary = plotting.plot_portfolio_summary(best_portfolio_slice) # Assume it returns a fig or displays
                         fig_trades = plotting.plot_trades(best_portfolio_slice, price_data) # Assume it returns a fig or displays
                         logger.info("Plot generation functions called for best combination.")
                         # Optional: Display plots if running interactively (might not work in all environments)
                         # if fig_summary: fig_summary.show()
                         # if fig_trades: fig_trades.show()
                    else:
                         logger.error("Plotting functions (plot_portfolio_summary, plot_trades) not found in analysis.plotting.")
                except Exception as plot_err:
                    # Log the specific error related to plotting
                    logger.exception(f"ERROR during plot generation call for best combination: {plot_err}") # Use logger.exception

            # Get Trades
            try:
                best_trades_df = metrics.get_trade_records(best_portfolio_slice)
                if best_trades_df is not None and not best_trades_df.empty:
                    logger.info("\n--- Trade Records (Best Combination - First 5) ---")
                    # Log head() as string to avoid multi-line issues in basic logging
                    logger.info(best_trades_df.head().to_string())
                    logger.info(f"Total trades for best combination: {len(best_trades_df)}")
                elif best_portfolio_slice is not None and best_portfolio_slice.trades.count() > 0:
                     logger.warning("\nPortfolio object indicates trades exist, but fetching failed.") # Use warning
                else:
                     logger.info("\nNo trades were executed for the best combination.")
            except Exception as trades_err:
                 logger.exception(f"Error getting trades for best combination: {trades_err}")

        elif best_params is None:
             logger.warning("\nSkipping detailed analysis as no best parameters could be determined.") # Use warning
        else: # best_params is not None but not in columns (should be rare)
             logger.error(f"\nBest parameters {best_params} determined but not found in portfolio columns. Skipping detailed analysis.") # Use error

    except Exception as e:
        logger.exception(f"ERROR during analysis phase: {e}") # Use logger.exception

# --- Save Results ---
# Only proceed if simulation was possible, portfolio exists, and best params were found
if simulation_possible and portfolio is not None and best_params is not None and best_params in portfolio.wrapper.columns:
    try:
        # Call save_run_results without the pre-calculated stats/trades
        # Assume save_run_results will extract the best slice, calculate stats/trades, and save plots internally
        results_dir = metrics.save_run_results(
            portfolio=portfolio,             # Pass full portfolio object
            aggregate_stats=None,            # Pass None for aggregate stats (if applicable)
            best_params=best_params,         # Pass the best combination identifier
            config_path=config_file,         # Pass the config file path
            strategy_name='ma_crossover',    # Strategy name
            symbol=SYMBOL,                   # Symbol
            price_data_for_plots=price_data  # Pass price data if needed for plots inside save_run_results
            # REMOVED: best_stats_series=best_stats,
            # REMOVED: best_trades_df=best_trades_df
        )
        if results_dir:
            logger.info(f"Results saved successfully to: {results_dir}")
        else:
            # Changed to warning as the function might not be designed to return a dir path
            logger.warning("Saving results process completed, but no results directory path was returned by the function.")

    except Exception as save_err:
        logger.exception(f"ERROR saving results: {save_err}") # Use logger.exception

elif not simulation_possible:
    logger.warning("Skipping saving results because simulation was not possible or failed.")
elif portfolio is None:
     logger.warning("Skipping saving results because the portfolio object is None.")
elif best_params is None:
     logger.warning("Skipping saving results because best parameters were not determined.")
else: # best_params not in portfolio.wrapper.columns
     logger.warning(f"Skipping saving results because best parameters {best_params} not found in portfolio.")


logger.info(f"\n--- MA Crossover Backtest Script Finished ---")