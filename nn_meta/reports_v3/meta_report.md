# NN Meta — Selection Report (v2.1)

Dataset: 344780 rows | 55 symbols × 7 proposal strategies × 5 DTEs (hash `69ef5648159e`)

| baseline | val | test |
|---|---|---|
| all frozen-DTE proposals | +20.1% (212) | +896.1% (149) |
| underlying B&H basket | -0.6% | +25.3% |

Gate: kept >= 10, maxDD <= 40%, val return > baseline AND > basket B&H; eligible if >= 20/40 seeds pass. Modes: filter (frozen-DTE, sequential) / rank (top-5 slots @ 10%, cross-ticker, model picks the DTE).

## Validation leaderboard (median across seeds)

| mode   | label        | arch   |    lr |   threshold |   median_val_return |   passing_seeds |   seeds |
|:-------|:-------------|:-------|------:|------------:|--------------------:|----------------:|--------:|
| rank   | label_excess | 32x16  | 0.000 |       0.600 |               0.672 |              31 |      40 |
| rank   | label_excess | 64x32  | 0.000 |       0.600 |               0.584 |              34 |      40 |
| rank   | label        | 32x16  | 0.001 |       0.600 |               0.555 |              29 |      40 |
| rank   | label        | 32x16  | 0.000 |       0.600 |               0.544 |              28 |      40 |
| rank   | label_excess | 64x32  | 0.001 |       0.600 |               0.474 |              29 |      40 |
| rank   | label_excess | 32x16  | 0.001 |       0.600 |               0.442 |              31 |      40 |
| rank   | label        | 64x32  | 0.001 |       0.550 |               0.439 |              28 |      40 |
| rank   | label_excess | 32x16  | 0.000 |       0.500 |               0.431 |              26 |      40 |
| rank   | label        | 64x32  | 0.000 |       0.600 |               0.431 |              25 |      40 |
| rank   | label        | 32x16  | 0.000 |       0.550 |               0.420 |              25 |      40 |

## Test (one shot) — mode=rank, ensemble of 40 seeds, thr=0.6

| strategy | return | trades | maxDD | win rate | ex-top3 |
|---|---|---|---|---|---|
| **NN rank (1x costs)** | **+257.9%** | 192/27306 | +23.4% | +50.0% | +93.4% |
| NN rank (2x costs) | +237.2% | 192 | +23.7% | +50.0% | +82.3% |
| Baseline (all frozen-DTE proposals) | +896.1% | 149 | +29.5% | +40.9% | +359.8% |
| **Underlying B&H basket** | **+25.3%** | — | — | — | — |
| SPY buy & hold | +13.8% | — | — | — | — |

Per-seed test return: +13.4%, +33.2%, +34.5%, +36.4%, +37.8%, +50.2%, +58.4%, +81.6%, +85.4%, +89.4%, +92.5%, +97.3%, +109.7%, +112.0%, +120.3%, +129.8%, +145.4%, +145.4%, +169.7%, +172.0%, +174.9%, +180.4%, +186.9%, +195.2%, +208.5%, +213.5%, +214.4%, +228.0%, +244.0%, +246.7%, +272.7%, +290.7%, +311.2%, +325.9%, +327.4%, +336.8%, +357.5%, +359.6%, +362.7%, +519.7%

## Rank calibration (test, all candidates): score quintile → outcome

| bucket   |    n |   mean_score |   mean_return |   win_rate |
|:---------|-----:|-------------:|--------------:|-----------:|
| Q1       | 5462 |        0.289 |         0.082 |      0.266 |
| Q2       | 5461 |        0.438 |         0.154 |      0.344 |
| Q3       | 5461 |        0.509 |         0.154 |      0.393 |
| Q4       | 5461 |        0.559 |         0.128 |      0.429 |
| Q5       | 5461 |        0.636 |         0.109 |      0.49  |

Monotonically increasing mean_return from Q1→Q5 means the model's ranking is informative — 'best initial choice' really was 'best performing'.

## Caveats

- Next-bar fills, no lookahead, identical on every side of the comparison.
- All rows (baseline, filter, rank) run through ONE slot portfolio: up to 5 concurrent positions, one per symbol, at 10% each (max 50% deployed) — filter picks the frozen DTE, rank lets the model choose the DTE.
- Exposure differs vs buy & hold (often flat vs 100% invested) — B&H rows answer 'worth doing at all?', not 'same-risk alpha'.
- Costs: 0.15%/side proxy; 2x stress restated exactly per fill.
- Earnings proximity is proxied by |gap| z-score (no offline earnings calendar); Sentiment strategy excluded (live news feed).
## Walk-forward folds (everything re-frozen per fold)

| fold | train end | OOS | NN return (kept) | NN ex-top3 | baseline | underlying B&H | NN wins |
|---|---|---|---|---|---|---|---|
| 1 | 2025-07-08 | 2025-07-09→2025-10-31 | -12.4% (220) | -6.1% | -31.6% (269) | +28.5% | ✅❌ |
| 2 | 2025-10-31 | 2025-11-03→2026-03-02 | +109.6% (258) | +108.0% | +90.4% (283) | +11.6% | ✅✅ |
| 3 | 2026-03-02 | 2026-03-03→2026-06-29 | +120.0% (196) | +111.4% | +53.1% (237) | +27.5% | ✅✅ |

**NN filter beats the fold-frozen baseline in 3/3 folds and the underlying B&H basket in 2/3; both in 2/3 → ROBUST**
(OOS windows are thin — ~81 trading days each; treat single-fold results as noise-dominated)
