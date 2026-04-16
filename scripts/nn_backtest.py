# scripts/nn_backtest.py

import pandas as pd
import numpy as np
import sys
import os
from dotenv import load_dotenv

# Fix for macOS OpenMP/TensorFlow crash
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

# Load .env variables (including ALPACA keys)
load_dotenv()

import vectorbt as vbt
import logging

# --- Add Project Root to Python Path ---
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    if project_root not in sys.path:
        sys.path.insert(0, str(project_root))
except NameError:
    project_root = '.'
    if project_root not in sys.path:
        sys.path.insert(0, str(project_root))

# --- Setup Logging ---
from utils.logging_utils import setup_logging
log_file_path = os.path.join(project_root, "logs", "nn_backtest.log")
logger = setup_logging(log_level=logging.INFO, log_file=log_file_path)

# --- Import project modules ---
from signals import nn_signals
from portfolio import simulator
from analysis import metrics, plotting
from utils import config_parser, freq_utils
from data import data_loader, data_cleaner, alpaca_loader
from models import data_preprocessing, nn_model

# --- Load Configuration ---
config_file = os.path.join(project_root, 'config', 'settings.py')
config = config_parser.load_config(config_file)
DATA_CONFIG = config.get('DATA_CONFIG', {})
STRATEGY_CONFIG = config.get('STRATEGY_NN', {})
BACKTEST_CONFIG = config.get('BACKTEST_CONFIG', {})

# --- Parameters ---
SYMBOL = DATA_CONFIG.get('SYMBOLS', ['SPY'])[0]
START_DATE = DATA_CONFIG.get('START_DATE', '2025-04-15')
END_DATE = DATA_CONFIG.get('END_DATE', '2026-04-15')
INTERVAL = DATA_CONFIG.get('INTERVAL', '5m')
DEFAULT_FREQ = freq_utils.resolve_freq(BACKTEST_CONFIG.get('DEFAULT_FREQ'), INTERVAL)

logger.info(f"--- Starting Neural Network Backtest ---")
logger.info(f"Symbol: {SYMBOL}, Period: {START_DATE} to {END_DATE} ({INTERVAL})")

# 1. Load Data
logger.info("[1/5] Loading and cleaning data from Alpaca...")
try:
    # Use Alpaca Loader specifically for the 1-year 5m data
    raw_data = alpaca_loader.load_alpaca_bars(
        symbol=SYMBOL, start_date=START_DATE, end_date=END_DATE, interval=INTERVAL
    )
    price_data = data_cleaner.clean_ohlcv_data(raw_data)
except Exception as e:
    logger.error(f"Failed to load data from Alpaca: {e}")
    sys.exit(1)

# 2. Prepare NN Data
logger.info("[2/5] Preprocessing data for Neural Network...")
FORWARD_PERIODS = STRATEGY_CONFIG.get('HORIZONS', [24])[0]
X_train, X_test, y_train, y_test, scaler, feature_cols = data_preprocessing.prepare_nn_data(
    price_data, STRATEGY_CONFIG, forward_periods=FORWARD_PERIODS
)
logger.info(f"Training set size: {len(X_train)}, Test set size: {len(X_test)}")

# 3. Train Model
logger.info("[3/5] Training Neural Network...")
model = nn_model.create_model(X_train.shape[1:], mode='classification')
model, history = nn_model.train_model(model, X_train, y_train, STRATEGY_CONFIG)

# 4. Generate Signals on Test Set
logger.info("[4/5] Generating signals on test set...")
# Reconstruct the aligned test index.
# prepare_nn_data drops NaN rows, splits chronologically, then creates sequences
# which consume LOOKBACK_WINDOW rows from the front of each split.
# The safest alignment: features + labels define the valid rows, then the test
# split starts at (1 - TRAIN_TEST_SPLIT) of those, offset by LOOKBACK_WINDOW.
LOOKBACK_WINDOW = STRATEGY_CONFIG.get('LOOKBACK_WINDOW', 24)
features_tmp = data_preprocessing.create_features(price_data)
labels_tmp = data_preprocessing.create_labels(price_data, FORWARD_PERIODS, STRATEGY_CONFIG['RETURN_THRESHOLD'])
valid_index = pd.concat([features_tmp, labels_tmp.rename('target')], axis=1).dropna().index
split_at = int(len(valid_index) * STRATEGY_CONFIG.get('TRAIN_TEST_SPLIT', 0.8))
# After sequence creation, first LOOKBACK_WINDOW rows of test split are consumed
test_index = valid_index[split_at + LOOKBACK_WINDOW:]
test_price_data = price_data.loc[test_index]

entries, exits, _, _ = nn_signals.generate_nn_signals(
    test_price_data, model, scaler, STRATEGY_CONFIG
)

# 5. Run Simulation
logger.info("[5/5] Running backtest simulation on test set...")
portfolio = None
if not entries.empty and entries.any().any():
    portfolio = simulator.run_backtest(
        price_df=test_price_data,
        entries_series=entries,
        exits_series=exits,
        initial_capital=BACKTEST_CONFIG.get('INITIAL_CAPITAL', 100000.0),
        fees=BACKTEST_CONFIG.get('FEES_PERCENT', 0.001),
        slippage=BACKTEST_CONFIG.get('SLIPPAGE_PERCENT', 0.0005),
        frequency=DEFAULT_FREQ,
        size=BACKTEST_CONFIG.get('DEFAULT_SIZE', 0.9),
        size_type=BACKTEST_CONFIG.get('DEFAULT_SIZE_TYPE', 'percent'),
        sl_stop=BACKTEST_CONFIG.get('STOP_LOSS_PERCENT') if BACKTEST_CONFIG.get('USE_STOP_LOSS') else None,
        tp_stop=BACKTEST_CONFIG.get('TAKE_PROFIT_PERCENT') if BACKTEST_CONFIG.get('USE_TAKE_PROFIT') else None
    )

    if portfolio is not None:
        logger.info("Simulation complete. Saving results...")
        # Since it's not an optimization, best_params is just our single signal column
        best_params = entries.columns[0] 
        
        results_dir = metrics.save_run_results(
            portfolio=portfolio,
            aggregate_stats=None,
            best_params=best_params,
            config_path=config_file,
            strategy_name='nn_strategy',
            symbol=SYMBOL,
            price_data_for_plots=test_price_data
        )
        logger.info(f"Results saved to: {results_dir}")
        
        # Log final stats
        stats = metrics.get_summary_stats(portfolio[best_params])
        logger.info("\n--- Performance Summary (Test Set) ---")
        for index, value in stats.items():
            logger.info(f"  {index}: {value}")
    else:
        logger.warning("Simulation failed to produce a portfolio object.")
else:
    logger.warning("No entry signals generated on the test set.")

logger.info("--- Neural Network Backtest Finished ---")
