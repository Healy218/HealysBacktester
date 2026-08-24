# Vol-regime track (track 1) — design (started 2026-08-24)

**Goal (ROADMAP wave-2 item 3):** `available_at`-stamped volatility features
for every expert, from the 9-year 1m underlying crawl. A sequence model gets
a seat ONLY if it beats the boring baselines (HAR-RV, GARCH(1,1), naive)
out-of-sample per regime; otherwise the features ship and the model doesn't.

## Data

`v3/data/underlying/<SYM>/<year>.parquet` — 289 symbols, 1m OHLCV, 2017→,
UTC-stamped, includes extended hours. RTH filtering is DST-aware
(America/New_York 09:30–16:00). Synced once to
`gs://healys-backtester/underlying_1m_9y/` for the Batch build.

## Stage 1 — realized-vol features (`nn_meta/vol_features.py`)

Per symbol, per session (all point-in-time; `available_at` = session close):

| feature | definition |
|---|---|
| `rv_1m` | Σ of squared 1m RTH log returns (the intraday RV target) |
| `rv_5m` | same on 5m subsampling (microstructure-noise robust) |
| `bpv` | bipower variation (π/2)·Σ|r_t||r_{t−1}| — continuous component |
| `jump` | max(rv_1m − bpv, 0) — the jump component |
| `overnight_r2` | squared close→open log gap |
| `ret_cc` | close-to-close daily log return (GARCH input) |
| `n_bars` | RTH bar count — coverage; low-coverage sessions are FLAGGED, not guessed |

## Stage 2 — baseline OOS harness

`nn_meta/vol_forecast.py` (existing, tested): HAR-RV (OLS on d/w/m lags),
GARCH(1,1) (scipy MLE), naive constant — one-step-ahead over expanding
folds, QLIKE + pinball losses. Extended to accept the INTRADAY rv target
(squared daily returns are a noisy proxy; that was the stage-0 placeholder).

Regime slices: per-fold QLIKE reported overall AND split by trailing-21d RV
tercile (calm/mid/stressed) — "beats them per regime" is the seat gate, and
a model that only wins in calm markets doesn't ship.

## Stage 3 — the gate for a learned model (NOT built yet)

One small sequence model (spec'd when stages 1–2 are green at scale). Gate:
beat HAR-RV's QLIKE in EVERY regime tercile on held-out folds, or the
features ship without it (they are useful to the experts either way).

## Compute

TASK_MODE=vol on Batch: sharded per-symbol (289), spot-safe (skip
already-published symbols on retry), each task = read ~10 year-parquets →
features → baseline eval row. Output:
`out/vol-<stamp>/{features/<SYM>.parquet, baseline_eval.parquet}`.
