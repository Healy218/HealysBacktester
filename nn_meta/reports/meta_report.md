# NN Meta Filter

## Walk-forward folds (everything re-frozen per fold)

| fold | train end | OOS | NN return (kept) | NN ex-top3 | baseline | underlying B&H | NN wins |
|---|---|---|---|---|---|---|---|
| 1 | 2025-07-08 | 2025-07-09→2025-10-31 | +2.0% (250) | -35.5% | -59.8% (252) | +28.5% | ✅❌ |
| 2 | 2025-10-31 | 2025-11-03→2026-03-02 | +70.9% (157) | -2.3% | -4.6% (219) | +11.6% | ✅✅ |
| 3 | 2026-03-02 | 2026-03-03→2026-06-29 | +35.0% (186) | +19.6% | -27.9% (277) | +27.5% | ✅✅ |

**NN filter beats the fold-frozen baseline in 3/3 folds and the underlying B&H basket in 2/3; both in 2/3 → ROBUST**
(OOS windows are thin — ~81 trading days each; treat single-fold results as noise-dominated)
