---
name: Known Issues
description: Active bugs, integration gaps, and code quality issues found during April 2026 comprehensive review
type: project
---

## Critical Bugs

### 1. nn_backtest.py — Shape mismatch crash at train time
`nn_model.create_model` is called with `X_train.shape[1]` (an integer) but the model expects a tuple `input_shape=(time_steps, features)` because the model is LSTM-based and `prepare_nn_data` returns 3D arrays when `use_sequences=True`. This will raise a Keras error at runtime.
- File: `scripts/nn_backtest.py` line 80
- Fix: Change to `nn_model.create_model(X_train.shape[1:], mode='classification')`

### 2. nn_backtest.py — Wrong `forward_periods` passed to prepare_nn_data
`prepare_nn_data` is called without a `forward_periods` argument, but the function signature requires it explicitly after `config`. The default is missing from the function signature; it will crash with a TypeError.
- File: `scripts/nn_backtest.py` line 73-75
- Fix: Add `forward_periods=STRATEGY_CONFIG.get('HORIZONS', [24])[0]` or similar.

### 3. nn_backtest.py — Test set index misalignment
`test_price_data = price_data.iloc[-len(X_test):]` is incorrect when `use_sequences=True`. The sequence creation shrinks the dataset by `window_size` rows from the train split AND from the test split, so `len(X_test)` does not correspond to the last N rows of the raw price data. The index will be wrong.
- File: `scripts/nn_backtest.py` line 87
- Fix: `prepare_nn_data` should return the original test index so the caller can align correctly.

### 4. nn_signals.py — Predict on 2D data, model expects 3D
`generate_nn_signals` calls `scaler.transform(X_filled)` producing a 2D array, then passes it directly to `predict_probabilities`. But the LSTM model trained on 3D sequences `(samples, time_steps, features)` will crash on 2D input. Sequence creation is completely missing from the inference path.
- File: `signals/nn_signals.py` lines 38-41
- Fix: Add sequence creation (using the same `LOOKBACK_WINDOW` from config) before prediction.

### 5. nn_multi_backtest.py — No early stopping
The ensemble training loop calls `model.fit(...)` directly without EarlyStopping, unlike `nn_model.train_model` which uses it. Long training runs risk overfitting.
- File: `scripts/nn_multi_backtest.py` lines 111-118
- Fix: Use `nn_model.train_model(model, X_train_combined, y_train_combined, STRATEGY_CONFIG)` to get consistent training.

## Moderate Issues

### 6. config/settings.py — STRATEGY_NN missing RETURN_THRESHOLD key
`data_preprocessing.prepare_nn_data` references `config['RETURN_THRESHOLD']` but `STRATEGY_NN` in settings.py only has `THRESHOLDS` (a list). This will raise a KeyError when `mode='classification'` (the default).
- File: `config/settings.py`
- Fix: Add `"RETURN_THRESHOLD": 0.01` to `STRATEGY_NN` or update `prepare_nn_data` to use `.get('RETURN_THRESHOLD', config.get('THRESHOLDS', [0.01])[0])`.

### 7. data_preprocessing.py — Triple barrier labeling uses a Python loop
`create_triple_barrier_labels` contains a plain Python for-loop over every row. For 1 year of 5-minute data (~20,000 bars) with horizon=24, this runs ~20,000 iterations in Python — extremely slow. Should be vectorized or Numba-compiled.
- File: `models/data_preprocessing.py` lines 75-86

### 8. signals/signal_combiners.py — Uses print() not logger
`combine_signals_and` and `combine_signals_or` use `print()` for all output instead of the established logger.
- File: `signals/signal_combiners.py` lines 71, 123, 173, 199

### 9. ma_crossover.py — logger.info used for error branch
In the except block for crossover generation, `logger.info` is used instead of `logger.error`, and the logger.info call incorrectly passes extra positional args (not the f-string pattern).
- File: `signals/ma_crossover.py` lines 86-89

### 10. config/__init.py__ — Filename is wrong
The file is named `__init.py__` instead of `__init__.py`. This means the config package cannot be imported as a package. Not fatal because config_parser uses `importlib.util` to load it directly, but it is a latent bug.
- File: `config/__init.py__`

### 11. scripts/ma_backtest.py and rsi_backtest.py — Return value mismatch
`generate_ma_signals` returns a 4-tuple (entries, exits, short_entries, short_exits) but `ma_backtest.py` line 192 unpacks only 2 values (`entries, exits = ...`). This will raise a ValueError at runtime.
- File: `scripts/ma_backtest.py` line 192

### 12. STRATEGY_NN missing EXIT_PROBABILITY_THRESHOLD key
`nn_signals.generate_nn_signals` accesses `config['EXIT_PROBABILITY_THRESHOLD']` but this key is absent from `STRATEGY_NN` in settings.py (only `PROBABILITY_THRESHOLD` is defined). Will raise KeyError.
- File: `config/settings.py` + `signals/nn_signals.py` line 51

## Minor / Code Quality Issues

### 13. models/nn_model.py — Duplicate import
`Dense, Dropout, Input` are imported twice (lines 3 and 7).

### 14. utils/date_utils.py, math_utils.py, api_utils.py — Stub files
These are placeholder docstring-only files with no implementation.

### 15. sentiment/ — Completely unimplemented
`sentiment_analyzer.py` and `sentiment_data_loader.py` are stubs. No real implementation.

### 16. indicators/moving_averages.py, rsi.py — Not used by main pipeline
These simple wrappers are effectively dead code; the main pipeline calls vbt indicators directly.

### 17. scripts/rsi_backtest.py — ENABLE_SHORTING read from wrong config section
Reads `STRATEGY_CONFIG.get('ENABLE_SHORTING')` but `ENABLE_SHORTING` is in `BACKTEST_CONFIG`, not `STRATEGY_RSI`.

**Why recorded:** Found during April 16 2026 comprehensive review.
**How to apply:** Use this as the fix checklist when coordinating with quant-backtesting-engineer.
