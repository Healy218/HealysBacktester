# Core backtester adversarial audit — 2026-09-05

> Remediated in the review checkout. See [the repair report](2026-09-05-remediation.md) for current dispositions and validation. Findings below refer to the original audited commit.

Snapshot: `f98ed265db3ce3faf4ba7abf8e6604671e3a1c90`. P1 means repair before relying on affected results; P2 means a material defect under the stated trigger. These are code findings, not claims about realized trading losses. Legacy components are explicitly identified.

## Findings

### CORE-01 — P1: Elliott signals use future-confirmed pivots before confirmation

`indicators/elliott_wave.py:51-70` reads through `i + order`, but writes the pivot at `i`. The signal loop consumes it immediately (`:209-218`), and `signals/elliott_wave_signals.py:84-93` passes the unshifted arrays directly. `nn_meta/proposals.py` also calls this generator directly, so this reaches the active Elliott strategy family, not only the legacy dashboard. A deterministic prefix replay (seed 31, order 3) changes an already elapsed short-entry signal at bar 19 when bars after the 20-bar prefix are appended. Full-history backtests can trade information unavailable in live operation. Publish pivots at their confirmation time, test prefix invariance, and rebuild affected frozen strategies, datasets, and evaluations.

### CORE-02 — P2: legacy sentiment aggregation timestamps future news at the bucket start

`sentiment/sentiment_analyzer.py:73` uses default left-labeled resampling. `signals/sentiment_signals.py:58` forward-fills that series onto price timestamps. A headline at 10:04 is returned at 10:00 for five-minute aggregation; a daily aggregate can similarly include after-close news in that day's signal. Reproduced with a provider-supplied score, without network calls. Use an explicit observation/availability cutoff and right-edge timestamps consistent with when a strategy can act.

### CORE-03 — P2: ranking reintroduces parameter sets it explicitly excluded

`utils/param_utils.py:169-194` masks bankrupt and fewer-than-three-trade combinations, but the filler loop at `:242` iterates sorted NaNs as well. With one valid, one -100% return, and one single-trade candidate, all three are returned on the leaderboard. This lets users inspect/save configurations described as excluded; chunked and unchunked ranking also disagree. Filter eligibility before selecting every winner or filler. Reproduced with a minimal portfolio fixture.

### CORE-04 — P2: chunked ranking can crown the wrong per-metric winner

`utils/chunked_runner.py:150-154` compares a candidate only against the metric named in its `ranked_by` label. `utils/param_utils.py:226-235` deduplicates local winners, so a chunk's best return is never compared globally when it is also that chunk's best Sharpe. Example: a local Sharpe winner with return 100% is ignored for Best Return, while another chunk's separately labeled 50% return wins. The 100% candidate may remain elsewhere in the table, but the global metric winner is wrong. Compare each retained candidate against every applicable metric, or preserve independent metric-winner identities before deduplication. Confirmed from the two linked control flows; no full large-grid benchmark run.

### CORE-05 — P2: signal combination invents nonexistent parameter pairs

`signals/signal_combiners.py:22-44` takes a Cartesian product of individual MultiIndex levels instead of actual column tuples. MA grids contain only valid fast/slow pairs. Combining three columns `(2,4), (2,6), (4,6)` with one RSI column generates four labels for three result columns, failing the shape check in `combine_signals_and`. Reproduced on a one-row fixture. Product the actual columns, flattening tuples only after pairing.

### CORE-06 — P2: saved scanner RSI/MACD calculations differ from backtested indicators

`scanner/signal_scanner.py:49-61,146-147` uses Wilder RSI and exponential MACD. `signals/rsi_threshold.py:69` and `signals/macd_signals.py:158-164` use vectorbt defaults without corresponding exponential settings. On the same seeded 200-bar series, scanner RSI is 49.4441 versus backtest RSI 44.5448. Saved thresholds can therefore fire different signals. The scanner's claim that its RSI matches vectorbt defaults is false for the installed dependency. Share the exact indicator implementation/settings and test parity of final signals, including warmup and crossings. This is the legacy saved-parameter scanner, separate from `nn_meta/live`.

### CORE-07 — P2: the legacy intraday scanner requests a window ending at midnight

`scanner/signal_scanner.py:353-358` obtains a date-only end from `utils/date_utils.py:9-13` and passes it to the Alpaca loader. `data/vbt_data_loader.py:115` forwards that end unchanged; `:166-175` reuses the same date-keyed cache for later scans. Consequently the intraday scan does not request the current day's completed bars and can repeatedly present an old final bar as current. Use a current timestamp with explicit timezone, refresh live data, and expose/reject stale bar timestamps. Static request/cache-path verification; no live provider request made.

### CORE-08 — P2: saving Volume Breakout produces an unusable scanner configuration

`signals/volume_breakout.py:69` names levels `volume_window`, `volume_multiplier`, `exit_ma_window`. The formatter (`utils/param_utils.py:336`) yields `volume`, `volume_multiplier`, `exit_ma`, but `main.py:1250` expects `vol_window`, `vol_mult`, `exit_ma`. Only the exit window is saved, and the nonempty check at `main.py:1315` allows it. `scanner/signal_scanner.py:337` then accesses missing required volume parameters. The formatter mismatch was reproduced directly. Map actual names and validate the complete schema before writing.

### CORE-09 — P2: scanner saves use current controls rather than the selected result's configuration

`main.py:1293-1323` takes strategy and interval from the current dropdown values while taking parameters from a previous result row. Changing the interval after a run and then saving silently schedules the same parameters on a different interval. Changing strategy can also reinterpret overlapping parameter labels. Persist strategy/interval with each result and save that immutable metadata; reject incomplete mappings. Confirmed callback data flow, not a browser automation test.

### CORE-10 — P2: legacy neural training labels cross the train/test boundary

`models/data_preprocessing.py:119-142` computes forward-looking targets on the full input before splitting and does not purge training rows whose horizon enters the test interval. The final training labels therefore consume prices reserved for testing. Binary labels at `:62-64` and triple-barrier labels at `:74-87` also encode the unresolved tail as zero, so `dropna()` retains fabricated negative outcomes. Purge by target availability and mark unresolved labels missing. This finding concerns the legacy neural preprocessing module; v4 evaluator findings are reported separately. Confirmed source boundary logic.

### CORE-11 — P2: walk-forward evaluation discards valid pre-window indicator history

`backtests/run_walkforward.py:106,155-158` generates OOS indicators on the isolated OOS slice. A selected slow window longer than the OOS segment cannot produce an OOS signal, even though sufficient past training history exists. Smaller windows still suffer artificial restart/warmup gaps each fold. Generate causal indicators with preceding history and clip trade eligibility to the OOS interval. This affects the dashboard walk-forward runner, not the separately implemented v4 folds.

### CORE-12 — P2: OHLCV cleaning backfills earlier missing prices with future observations

`data/data_cleaner.py:79-83` applies `ffill().bfill()` to all columns. A missing first trading bar is replaced with the next bar's complete prices and volume; the reproduction fills September 3 with September 4's value 42. This creates tradable fabricated history and violates point-in-time semantics. Drop leading unavailable rows or keep explicit invalid-bar flags; do not backfill prices/volume for trading simulation.

### CORE-13 — P2: live v4/v5 moneyness is fixed at zero despite varying training values

`nn_meta/build_meta_dataset.py:321,343` derives training moneyness from the executed contract's actual listed strike and underlying spot. `nn_meta/feature_contract.py:53` retains moneyness as a model input. However, `nn_meta/live/v4_scan.py:130-138` substitutes spot itself for the strike, making the live feature in `nn_meta/live/v4_candidates.py:35` identically zero. Targeting ATM/50-delta does not imply an actual listed strike equals spot, so sharing the log formula does not establish feature parity. This is a concrete train/serve mismatch; its score impact on deployed models has not been measured. Use the same decision-time contract-selection convention in both paths, or remove/retrain this feature if live intentionally operates without contract selection.

## Evidence and coverage

Run `PYTHONDONTWRITEBYTECODE=1 NUMBA_CACHE_DIR=/tmp/healys-review-numba <python-with-project-dependencies> docs/reviews/repros/root_audit_repro.py` from the repository root. It prints the seven isolated checks described above. These reproductions intentionally expose current behavior; they are not regression tests that assert corrected behavior.

Reviewed core paths: `main.py`, `backtests/`, `portfolio/`, `signals/`, `indicators/`, `models/`, `scanner/`, `utils/`, `analysis/`, `data/`, `sentiment/`, `config/`, and legacy `scripts/*backtest.py`. Review combined source inspection, call-path tracing, and targeted synthetic execution; it was not exhaustive execution of every strategy/grid/UI permutation. No fixes, provider calls, model training, production cache changes, or notifications were performed. The test run can create ignored local logs/caches; only audit artifacts are intended repository changes.
