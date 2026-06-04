---
name: NN Pipeline Status
description: State of the NN model and NN pipeline as of June 2026 review
type: project
---

## Summary (June 2026)
The NN pipeline has been PARTIALLY fixed since the April 2026 review. The major integration
gaps in nn_signals.py and nn_backtest.py were addressed. However, a new critical issue was
introduced: nn_model.py was reverted from LSTM to a plain Dense MLP, which is architecturally
incompatible with the sequence-based data pipeline.

## Current nn_model.py — DENSE MLP (NOT LSTM)
- Input: Dense(64) → Dropout → Dense(32) → Dropout → Dense(16) → Dense(1, sigmoid)
- NO LSTM layers. NO BatchNormalization.
- `create_model(input_shape)` takes ONE arg — no `mode` parameter.
- `save_model()` function does NOT exist (called by nn_multi_backtest.py).

## Integration Status
| Issue | Status |
|---|---|
| nn_backtest.py forward_periods crash | FIXED |
| nn_backtest.py input_shape scalar bug | FIXED |
| nn_backtest.py test index alignment | FIXED |
| nn_signals.py missing sequence creation | FIXED |
| STRATEGY_NN missing config keys | FIXED |
| nn_model.py LSTM architecture | REGRESSED — now plain Dense |
| nn_model.py `mode` parameter | BROKEN — crashes with TypeError |
| nn_multi_backtest.py save_model call | BROKEN — function doesn't exist |
| nn_multi_backtest.py class_weight usage | INCOMPLETE — computed but never used |

## Recommended Fix Order
1. Add `mode='classification'` param to `create_model` (accepts and ignores for now) — 2 min.
2. Add `save_model(model, path=None)` to nn_model.py — 5 min.
3. Restore LSTM architecture (or switch to 1D CNN which also handles sequences) — 30 min.
4. Wire computed class_weight into nn_model.train_model() via class_weight_dict param — 10 min.

**Why:** NN pipeline was rebuilt in pieces; Dense MLP appears to be a regression from the prior
LSTM version. The sequence-generation pipeline (prepare_nn_data, create_sequences) is correct
and produces 3D arrays — the model needs to match.
