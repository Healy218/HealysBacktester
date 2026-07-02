# scripts/nn_multi_backtest.py

import pandas as pd
import numpy as np
import sys
import os
from dotenv import load_dotenv

# Fix for macOS OpenMP/TensorFlow crash
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
os.environ['NUMBA_CACHE_DIR'] = '/tmp/numba_cache'

# Load .env variables
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
log_file_path = os.path.join(project_root, "logs", "nn_ensemble_backtest.log")
logger = setup_logging(log_level=logging.INFO, log_file=log_file_path)

# --- Import project modules ---
from signals import nn_signals
from portfolio import simulator
from analysis import metrics, plotting
from utils import config_parser, freq_utils
from data import data_cleaner, alpaca_loader
from models import data_preprocessing, nn_model
from datetime import datetime

# --- Load Configuration ---
config_file = os.path.join(project_root, 'config', 'settings.py')
config = config_parser.load_config(config_file)
DATA_CONFIG = config.get('DATA_CONFIG', {})
STRATEGY_CONFIG = config.get('STRATEGY_NN', {})
BACKTEST_CONFIG = config.get('BACKTEST_CONFIG', {})

# --- Parameters ---
SYMBOLS = DATA_CONFIG.get('SYMBOLS', ['SPY'])
START_DATE = DATA_CONFIG.get('START_DATE', '2023-04-15')
END_DATE = DATA_CONFIG.get('END_DATE', '2026-04-15')
INTERVAL = DATA_CONFIG.get('INTERVAL', '5m')
DEFAULT_FREQ = freq_utils.resolve_freq(BACKTEST_CONFIG.get('DEFAULT_FREQ'), INTERVAL)

HORIZON = 24  
RET_THRESH = 0.025 
PROB_THRESH = 0.85
ENSEMBLE_SIZE = 5

logger.info(f"--- Starting 3-Year ENSEMBLE LSTM Backtest ---")
logger.info(f"Symbols: {SYMBOLS} | Horizon: {HORIZON} bars | Target: {RET_THRESH:.1%}")

# 1. Load Data
all_price_data = {}
for symbol in SYMBOLS:
    try:
        raw_data = alpaca_loader.load_alpaca_bars(
            symbol=symbol, start_date=START_DATE, end_date=END_DATE, interval=INTERVAL
        )
        all_price_data[symbol] = data_cleaner.clean_ohlcv_data(raw_data)
    except Exception as e:
        logger.error(f"Failed to load {symbol}: {e}")

market_df = all_price_data.get("SPY")

# 2. Data Preparation
train_X_list, train_y_list = [], []
ticker_test_info = {}

for symbol, price_data in all_price_data.items():
    tmp_config = STRATEGY_CONFIG.copy()
    tmp_config['RETURN_THRESHOLD'] = RET_THRESH
    
    X_train, X_test, y_train, y_test, scaler, _ = data_preprocessing.prepare_nn_data(
        price_data, tmp_config, forward_periods=HORIZON, 
        mode='triple_barrier', use_sequences=True, market_df=market_df
    )
    
    train_X_list.append(X_train)
    train_y_list.append(y_train)
    # Align test price data accounting for NaN drops + sequence windowing.
    # After prepare_nn_data: features/labels drop NaNs, split chronologically,
    # then create_sequences consumes LOOKBACK_WINDOW rows from the front.
    lookback = tmp_config.get('LOOKBACK_WINDOW', 24)
    features_tmp = data_preprocessing.create_features(price_data, market_df=market_df)
    labels_tmp = data_preprocessing.create_triple_barrier_labels(
        price_data, horizon=HORIZON, pt=RET_THRESH, sl_mult=tmp_config.get('STOP_LOSS_MULT', 0.5)
    )
    valid_idx = pd.concat([features_tmp, labels_tmp.rename('target')], axis=1).dropna().index
    split_at = int(len(valid_idx) * tmp_config.get('TRAIN_TEST_SPLIT', 0.8))
    test_idx = valid_idx[split_at + lookback:]
    ticker_test_info[symbol] = {'X_test': X_test, 'price_data': price_data.loc[test_idx]}

X_train_combined = np.concatenate(train_X_list, axis=0)
y_train_combined = np.concatenate(train_y_list, axis=0)

# 3. Train Ensemble of Models
ensemble_models = []

from sklearn.utils import class_weight
weights = class_weight.compute_class_weight('balanced', classes=np.unique(y_train_combined), y=y_train_combined)
weight_dict = dict(enumerate(weights))

for i in range(ENSEMBLE_SIZE):
    logger.info(f"\nTraining ENSEMBLE Brain {i+1}/{ENSEMBLE_SIZE}...")
    model = nn_model.create_model(X_train_combined.shape[1:], mode='classification')

    model, history = nn_model.train_model(
        model, X_train_combined, y_train_combined, STRATEGY_CONFIG,
        class_weight=weight_dict
    )

    # Save each brain
    model_path = nn_model.save_model(model)
    ensemble_models.append(model)
    logger.info(f"Brain {i+1} saved to: {model_path}")

# 4. Ensemble Backtest (Averaging Predictions)
all_portfolios = []
for symbol, info in ticker_test_info.items():
    logger.info(f"Generating ensemble predictions for {symbol}...")
    
    # Collect predictions from all 5 models
    all_preds = []
    for model in ensemble_models:
        all_preds.append(model.predict(info['X_test'], verbose=0).flatten())
    
    # Take the AVERAGE probability
    avg_probs = np.mean(all_preds, axis=0)
    
    entries = (avg_probs > PROB_THRESH)
    entries_df = pd.DataFrame(entries, index=info['price_data'].index, columns=['signal'])
    
    if entries.any():
        logger.info(f"Backtesting {symbol}... Found {entries.sum()} ensemble conviction entries.")
        portfolio = simulator.run_backtest(
            price_df=info['price_data'],
            entries_series=entries_df,
            exits_series=pd.DataFrame(False, index=entries_df.index, columns=entries_df.columns), 
            initial_capital=100000.0 / len(SYMBOLS),
            frequency=DEFAULT_FREQ,
            tp_stop=RET_THRESH,
            sl_stop=RET_THRESH * STRATEGY_CONFIG.get('STOP_LOSS_MULT', 0.5)
        )
        all_portfolios.append(portfolio)
        metrics.save_run_results(
            portfolio=portfolio, 
            aggregate_stats=None, 
            best_params='signal', 
            config_path=config_file,
            strategy_name='ensemble_nn', 
            symbol=str(symbol), 
            price_data_for_plots=info['price_data']
        )

logger.info("\n--- FINAL ENSEMBLE PORTFOLIO PERFORMANCE ---")
total_ret = np.mean([p.total_return().iloc[0] for p in all_portfolios]) if all_portfolios else 0
logger.info(f"AVERAGE PORTFOLIO RETURN: {total_ret:.2%}")
