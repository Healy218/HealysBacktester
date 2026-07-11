# v3 GBT baseline (LightGBM) vs the NN ensemble

Pool **v3**, label **label_excess**, 62 trees (early-stopped).

| model | val AUC | test AUC |
|---|---|---|
| LightGBM | 0.614 | 0.609 |
| NN 40-seed ensemble | ~0.62 | (see meta_report) |

## Top 20 features by gain

| feature | gain % |
|---|---|
| prem_spot | 17.1 |
| strat_rsi | 14.0 |
| dte_frac | 10.8 |
| strat_tv_rating | 8.4 |
| market_iv | 4.9 |
| atm_iv_far | 4.9 |
| strat_macd | 3.7 |
| beta_60d | 3.4 |
| rsi14 | 3.3 |
| term_slope | 2.9 |
| strat_squeeze | 2.6 |
| strat_ma | 2.3 |
| dir_short | 2.0 |
| atm_iv_near | 1.8 |
| iv_chg_5 | 1.5 |
| session_gap | 1.5 |
| bb_z | 1.5 |
| rv_iv_spread | 1.5 |
| rvol_21 | 1.3 |
| strat_supertrend | 1.3 |

## Strategy one-hot importance (does each earn its seat?)

| strategy | gain % |
|---|---|
| rsi | 13.98 |
| tv_rating | 8.43 |
| macd | 3.69 |
| squeeze | 2.56 |
| ma | 2.34 |
| supertrend | 1.33 |
| volume | 0.28 |