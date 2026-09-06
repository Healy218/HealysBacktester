# Data audit remediation — 2026-09-05

All eight data-audit findings are fixed in the review checkout. The original audit and reproductions are preserved. No production cache, cloud job, provider endpoint, deployment or commit was touched.

| Finding | Change | Regression evidence |
|---|---|---|
| D1 | Compaction deduplicates `(ticker,date)` newest-first instead of replacing entire ticker histories. | Disjoint historical dates survive while overlapping observations keep their latest correction. |
| D2 | Execution records cached request coverage per contract and extends coverage when a subsequent DTE needs earlier/later bars; each caller receives its requested slice. Daily fallback was removed for intraday fills. | Executing DTE 1 before DTE 10 gives exactly the same records as a fresh DTE-10 executor. No daily call is made on missing intraday data. |
| D3 | PIT membership defaults on for both v5 and v6. | Parameterized CLI test verifies both pools call membership-enabled assembly. |
| D4 | Reuse requires complete requested DTE coverage, matching frozen entry, and current build provenance. | Unchanged winning DTE cannot reuse a five-DTE family for an eight-DTE weekly grid. |
| D5 | Symbol/partial/cross-pool skips require marks with the persisted schema, every executed trade ID, and matching entry/terminal timestamps. Assembly rejects missing mark shards when assembling a marks-backed dataset. | Missing shard, missing terminal mark, legacy row metadata and empty-family resume tests. |
| D6 | PIT raw-input loader selects only `YYYY-MM.parquet`, excluding its own consolidated membership output. | Reconstitution before and after writing the derived view gives identical frames. |
| D7 | Wing-grid estimation reads only prints completed before the decision. | Adding future prints cannot change the historical selected wing. |
| D8 | Stop triggers become available one minute after the source bar's start. SPX0 worst-print/package fills and marks now carry completion timestamps; post-entry stops include the next completed minute. | A close-triggered stop uses the subsequent minute's gap price; fill-time expectations updated explicitly. |

Additional coordinated corrections:

- Training moneyness now encodes the decision target `log1p(EXEC_CONFIG['MONEYNESS'])`; executed strike stays metadata. The live agent implements the same target. Tests cover zero and nonzero targets with an executed strike different from the target.
- Final meta/SPX0 parquet attrs carry the shared `feature_contract.CONTRACT_VERSION`. SPX0 persisted marks include cumulative entry/exit cost counters matching the evaluation agent's new mark schema.
- Symbol and family checkpoints carry `.provenance.json` with contract version, frozen entry, DTE grid, window, simulation/execution settings and fees. Old/mismatched provenance rebuilds rather than silently reusing pre-fix outputs; assembly rejects unversioned rows. Cross-pool reuse checks the earlier rows' recorded entry against the earlier spec. Empty family checkpoints now persist their marks marker too.
- The live/ops agent updates transports to move marks, then rows, then provenance, and delegates skipping to the builder's validation. Root owns baseline freeze/resume version invalidation.

New tests live in `tests/test_data_audit_regressions.py`; related existing tests now express complete mark coverage, observation-level deduplication, and minute-completion fills. Existing generated artifacts are intentionally incompatible and need rebuilding; this work does not regenerate them or assert that previously published research results remain valid. Compaction cannot restore dates already deleted from a production cache.

Validation: **169 tests passed** across the new adversarial suite and execution, provider, download/compaction, PIT, weekly reuse, preflight, meta baseline/data, v3 and SPX0 suites. Two existing protobuf deprecation warnings; no failures. `git diff --check` passed for owned files. Tests used the existing Python 3.12 venv, disabled bytecode writes and pytest cache, and directed Numba/Matplotlib caches to `/tmp`.

Integration review additionally aligned SPX0 `n_fills` with one package lifecycle and retained actual contract count in `n_legs`; the persisted cost counters now pass the shared ledger validation for credit verticals. Assembly also compares every checkpoint against the **current** validated frozen spec and per-symbol grid, preventing same-version rows from an older parameter freeze from being assembled. Two integration regressions verify those boundaries, including SPX0 parquet attribute restoration and the new persisted mark loader. The focused integration/SPX0 subset passed **31 tests**. Cloud/local transports were inspected: final marks→rows→provenance publication, complete checkpoint pulls, and family wildcard transfers include the new metadata; Python validates the checkpoint before skipping.

The subsequent SPX0 cost integration issue is also fixed: the shared ledger now receives explicitly computed base/stressed **index dollar** net-mark paths. They use the existing SPX0 per-contract/package commission and spread models, book entry friction immediately and exit friction at the terminal fill, and preserve settlement exemptions for shorts/verticals. Gross marks remain unchanged for reconciliation; the ledger reports `cost_model=index_dollar` and does not add equity percentage fees to an already costed path. This is not a zero-fee workaround. Twelve isolated ledger regressions (long/vertical/naked short × base/stressed × market exit/settlement) match the builder's `net_return` exactly and show entry costs immediately. The associated accounting/mark/SPX0 suite passed 89 tests before adding the six extra settlement cases; all twelve final cost cases passed.

Assembled datasets now carry `baseline_spec_sha256` from the shared canonical fingerprint helper. SPX0 records its optimized proposal spec's real training window and fingerprints its synthetic baseline; its evaluator excludes validation folds overlapping proposal optimization rather than claiming its optimized proposal generators are unoptimized mechanical rules.

Final coordinating verification: **615 tests passed** across the complete suite. SPX0 evaluation also records the exact mark-stream hash and index-dollar cost convention in its manifest, covered by `tests/test_spx0_evaluation_provenance.py`.
