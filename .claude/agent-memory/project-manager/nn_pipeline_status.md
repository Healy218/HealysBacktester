---
name: NN Pipeline Status
description: State of the Gemini-authored nn_model.py and the full NN pipeline integration as of April 2026
type: project
---

## Summary
The NN pipeline consists of four interconnected files:
- `models/nn_model.py` — Gemini-authored. Model architecture is good but has a duplicate import.
- `models/data_preprocessing.py` — Solid feature engineering. Triple-barrier labeling loop is slow.
- `scripts/nn_backtest.py` — Has 3 critical bugs that will crash on first run.
- `scripts/nn_multi_backtest.py` — Structurally sound. Missing early stopping. Newly added.
- `signals/nn_signals.py` — Missing sequence creation — will crash against LSTM model.

## nn_model.py Assessment (Gemini-authored)
The model architecture itself is reasonable:
- LSTM(64, return_sequences=True) → BN → Dropout → LSTM(32) → BN → Dropout → Dense(16) → Dense(1)
- Supports classification (sigmoid + binary_crossentropy + AUC) and regression (linear + MSE).
- EarlyStopping with restore_best_weights in train_model is correct.
- The model is NOT overfit-prone by design (Dropout + BN + EarlyStopping).

**What Gemini got wrong:**
1. Duplicate import block (cosmetic, not a crash).
2. `create_model` takes `input_shape` as a tuple but is called in `nn_backtest.py` with a scalar integer. The model itself is fine; the calling code is wrong.

## Integration Gaps (the real problems)
The pipeline was assembled in pieces and the contracts between components were never verified end-to-end:

1. `nn_backtest.py` passes `X_train.shape[1]` (int) to `create_model` — needs `X_train.shape[1:]` (tuple).
2. `nn_backtest.py` calls `prepare_nn_data` without `forward_periods` — needs it added.
3. `nn_backtest.py` aligns test_price_data using `-len(X_test)` which is wrong after sequence windowing.
4. `nn_signals.py` does not create sequences before calling predict — will pass 2D data to a 3D LSTM.
5. `STRATEGY_NN` config is missing `RETURN_THRESHOLD` and `EXIT_PROBABILITY_THRESHOLD` keys.

## Recommended Fix Order
1. Fix config/settings.py (add missing keys) — 5 min.
2. Fix nn_backtest.py (input_shape, forward_periods, test alignment) — 15 min.
3. Fix nn_signals.py (add sequence creation at inference time) — 20 min.
4. Add early stopping to nn_multi_backtest.py ensemble loop — 5 min.
5. Vectorize triple_barrier labeling — 1-2 hrs (Numba or vectorized pandas).

**Why:** Pipeline was built incrementally; Gemini wrote nn_model.py in isolation without seeing how it would be called.
**How to apply:** Assign all 5 fixes to quant-backtesting-engineer in priority order above.
