# Core audit remediation — September 5, 2026

| Finding | Implemented correction | Regression evidence |
|---|---|---|
| CORE-01 | Elliott pivots are published on the confirmation bar, never at the earlier pivot bar. | Every prefix of a deterministic 200-bar series preserves all elapsed long/short entry/exit signals. |
| CORE-02 | Sentiment resampling is right-closed and right-labeled. | A 10:04 headline cannot appear before 10:05 in a five-minute aggregate. |
| CORE-03 | Sharpe fillers exclude masked/NaN candidates. | Bankrupt and single-trade candidates stay off a sparse leaderboard. |
| CORE-04 | Every local candidate competes for each global metric before final deduplication. | A local combined Sharpe/return winner still wins global return against another chunk. |
| CORE-05 | Combined indices product actual parameter tuples. | A triangular MA grid combines with RSI without phantom columns or shape failure. |
| CORE-06 | Saved-parameter scanner uses the same vectorbt RSI/MACD implementations and crossing rules. | RSI values and MACD values match the sweep on the same prices. |
| CORE-07 | Intraday requests end at the current UTC timestamp, force a refresh, remove forming bars and reject stale data. | Request capture verifies fresh fetch and stale-history refusal. |
| CORE-08 | Volume scanner parameter mapping uses actual formatted names; all required parameters are validated. | Save roundtrip includes volume window, multiplier and exit window; incomplete rows are refused. |
| CORE-09 | Results persist their strategy and interval; saving reads those immutable values. | Changing current UI controls cannot relabel a saved result. Old results without metadata must be rerun. |
| CORE-10 | Training rows are purged by original-bar target availability; unresolved classification/triple-barrier tails are NaN. | All three label modes end training targets before the first test row and discard unavailable tails. |
| CORE-11 | OOS indicators receive preceding history; trade signals are clipped to the OOS index. | A 120-bar indicator can operate from the first bar of a 50-bar OOS window, with no pre-window trades. |
| CORE-12 | Cleanup uses only forward observations and drops unavailable leading OHLCV rows. | Leading missing prices are not filled from the next day; fully missing input returns no data. |
| CORE-13 | Dataset and live features use the same decision-time moneyness target; executed strikes remain metadata. | Dataset/live specialists test zero and nonzero targets; shared causal contract prevents silent old-bundle reuse. |

Additional integration changes: freeze specs include the shared causal version, execution settings and a configuration hash covering algorithm/weekly settings. Loading, resuming, inheriting or merging incompatible freezes fails with a rebuild message. Writes use atomic replacement. Baseline sequential drawdown now includes initial capital. Tests cover outdated freeze load/resume/merge and first-trade losses.

Tests: `tests/test_core_audit_regressions.py`, with existing ranking/scanner/signal/baseline suites. Full integrated results are in [the remediation report](2026-09-05-remediation.md).

Documentation: current README/data-source/v3 descriptions match implemented modules; ROADMAP distinguishes historical verdicts from current repair work; old TODO/HANDOFF were archived; hidden project-manager memories are explicitly historical. Runtime/environment reference corrections retain the operational traps. Old research reports remain historical evidence, not corrected performance claims.

No original model weights, raw market caches or production state were changed. Correcting signals/labels invalidates their derived results, so artifact rebuilding and a fresh evaluation are required before deployment of this source.
