---
name: Known Issues
description: Active bugs, integration gaps, and code quality issues — updated June 2026
type: project
---

## Critical Bugs (NEW as of June 2026 review)

### 1. nn_multi_backtest.py — calls nn_model.save_model() which does not exist
`nn_multi_backtest.py` line 126 calls `nn_model.save_model(model)` but `models/nn_model.py`
has no `save_model` function. This will crash with AttributeError on the first ensemble brain.
- File: `scripts/nn_multi_backtest.py` line 126, `models/nn_model.py`
- Fix: Either add `save_model(model, path=None)` to nn_model.py, or remove the save call.

### 2. nn_model.py — create_model() ignores mode parameter
`nn_model.create_model(input_shape, mode='classification')` is called with a `mode` kwarg
from both nn_backtest.py and nn_multi_backtest.py, but `create_model()` only accepts
`input_shape` — no `mode` parameter. Will raise TypeError.
- File: `models/nn_model.py` line 7
- Fix: Add `mode='classification'` param to `create_model`. Currently the model is hardcoded
  to binary classification (sigmoid + binary_crossentropy), so `mode` can be accepted and ignored
  for now, or wired to actually switch output/loss.

### 3. nn_model.py — still Dense not LSTM
The current `nn_model.py` is a plain Dense MLP (no LSTM layers), but `nn_backtest.py` and
`nn_multi_backtest.py` both call `prepare_nn_data(..., use_sequences=True)` which produces 3D
arrays (samples, lookback, features). Passing 3D data to a Dense Input layer will crash.
The original LSTM architecture from the prior review was apparently reverted/lost.
- File: `models/nn_model.py`
- Fix: Restore LSTM architecture or flatten sequences before passing to Dense model.

### 4. nn_multi_backtest.py — exits_series is all False (no exit logic)
Line 151: `exits_series=pd.DataFrame(False, index=entries_df.index, columns=entries_df.columns)`
The strategy has no exit signal at all — it relies entirely on `tp_stop` and `sl_stop`. If
those are never hit, positions are held until the end of data. This is not a crash bug but is
a serious strategy design gap for the ensemble path.

## Previously Identified Bugs (Status Updated)

### 5. nn_backtest.py — fixed: forward_periods now passed correctly (line 75)
### 6. nn_backtest.py — fixed: uses X_train.shape[1:] now (line 81)  
### 7. nn_backtest.py — fixed: test index alignment rewritten (lines 92-98)
### 8. nn_signals.py — FIXED: create_sequences is now called before prediction (lines 43-47)
### 9. STRATEGY_NN — FIXED: EXIT_PROBABILITY_THRESHOLD and RETURN_THRESHOLD added to settings.py

## Moderate Issues

### 10. config/settings.py — API_KEYS section has placeholder values
`API_KEYS["ALPHAVANTAGE"]` is "YOUR_AV_KEY_HERE". These keys appear to be loaded from .env
(run_sentiment.py uses os.environ.get), but the config dict contains dummies. Low risk since
real lookups use the env; cosmetic concern.

### 11. signals/signal_combiners.py — uses print() not logger (unchanged from prior review)
- File: `signals/signal_combiners.py` lines 71, 123, 173, 199

### 12. ma_crossover.py — logger.info used in except block (unchanged from prior review)
- File: `signals/ma_crossover.py` lines 86-89

### 13. config/__init.py__ — still misnamed (unchanged)
- File: `config/__init.py__`

### 14. scripts/ma_backtest.py and rsi_backtest.py — legacy scripts still broken
These legacy scripts (not used by dashboard) still have the 2-value unpack bug and ENABLE_SHORTING
config mismatch identified in the prior review. Not urgent since dashboard uses backtests/ runners.

## Minor / Code Quality Issues

### 15. models/nn_model.py — no LSTM, no regularization, no class weighting
The MLP is undertrained for sequential data. It also has no class_weight support despite the
ensemble script computing class weights (which are then never passed to the model fit call).

### 16. utils/date_utils.py — now has real implementations (no longer a stub)
- RESOLVED from prior review.

### 17. sentiment/ — now has real implementations
- RESOLVED: sentiment_data_loader.py, sentiment_analyzer.py, sentiment_filter.py are all real.
- sentiment strategy is exposed in dashboard via run_sentiment.py.
- Limitation: requires ALPHAVANTAGE_KEY or FINNHUB_API_KEY in env.

### 18. indicators/moving_averages.py, rsi.py — still dead code (unchanged)

**Why recorded:** Updated during June 4 2026 comprehensive review.
**How to apply:** Use as fix checklist when coordinating with quant-backtesting-engineer.
