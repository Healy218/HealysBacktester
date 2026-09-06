# Evaluation/accounting audit remediation — 2026-09-05

All fifteen evaluation findings and the four additional implementation concerns were addressed in code. This changes the research contract: **pre-audit datasets, mark sidecars, trained bundles, and walk-forward checkpoints must be rebuilt**. No historical market downloads, model training, cloud work, or production deployment was performed. Original audit reproductions describe the former behavior; the executable regression tests now assert the corrected behavior.

| Finding | Change |
|---|---|
| E01 global freeze overlap | `evaluate_window` rejects any validation period overlapping the inclusive baseline training window. The CLI excludes contaminated folds and refuses an empty set. Results explicitly describe meta-model/policy selection conditional on a previously frozen proposal generator, not end-to-end nested strategy optimization. Source baseline fingerprints are checked against dataset provenance. |
| E02 missing entry mark / close chronology | Executors persist actual bar-close timestamps. Sidecars emit distinct entry-open and bar-close events, including the first close. The ledger processes entry-time marks after allocating their positions. |
| E03 unfunded leverage | Every new allocation is capped by available cash as well as the requested equity fraction. A book with no cash cannot fabricate a funded entry. |
| E04 omitted roll costs | Sidecars persist cumulative `cost_entries` and `cost_exits`; the ledger applies every lifecycle haircut at its event. Turnover sums actual premium traded, including changed reinvestment after gains/losses, rather than multiplying initial notional by a leg count. |
| E05 sidecar outcome mismatch | Terminal marks must reconcile with executed gross returns; cost counters must be valid, chronological, and agree with execution lifecycle counts. Missing execution timestamps are rejected. |
| E06 future exit selection | Daily option candidates are ranked without looking at entry/exit availability. A selected unfilled order receives no substitute. A selected filled contract with no valid exit stops evaluation for explicit valuation repair. |
| E07 sparse-label overlap | Each horizon's training/validation/test outcome is invalidated if its actual exit crosses the partition boundary. The proposal is retained, so missing outcomes cannot silently alter ranking. Old daily datasets and models are rejected by version checks. |
| E08 initial drawdown / curve timing | Daily drawdown peaks start at initial capital, and realized P&L is recorded at actual exit dates rather than decision dates. |
| E09 legacy fold overlap | The legacy runner uses exit-aware purged splits with a one-day embargo. |
| E10 stale resume | A shared lightweight `wf_context` hashes the winner, fold count, membership mode, relevant configuration, underlying/surface/spec, membership manifests, and raw option-cache content. Prewarm and the canonical runner use the same namespace. Predictions additionally bind ordered rows and training data; reused model directories require matching fold metadata. |
| E11 isotonic ties | Equal-score observations are aggregated first, then weighted PAV is fit. Harmless tie ordering no longer changes calibration. |
| E12 volatility availability | Daily volatility features become available after the final minute bar closes. |
| E13 regime leakage | Volatility tercile boundaries are estimated separately from each fold's training history. |
| E14 artifact provenance | Manifests include mark-stream SHA-256, current feature version, and effective evaluation settings. Validation verifies the sidecar hash. Gate names appear in evaluation metadata/report wording. |
| E15 mark-stream grid scaling | `execution_frames` filters selected trade IDs before copying, validating and sorting; full-universe sorting is confined to the initial stream load. |
| Atomic promotion | Existing directories are replaced with a single Linux `renameat2(RENAME_EXCHANGE)` operation. An interruption leaves a complete old or new bundle at the final path. Unsupported exchange fails without moving the old bundle. |
| Verification completeness | Verification requires the actual ensemble config and all model/scaler/magnitude files used by loading, checks schema/version, and rejects paths escaping the bundle. |
| Fold remainder | The final temporal fold includes remainder days. |
| Zero baseline | Legacy comparisons distinguish a valid zero baseline from a missing baseline. |

The feature contract is `2026-09-05-causal-v2`. Its moneyness source is explicitly the configured proposal target `log1p(MONEYNESS)`, independent of the subsequently executed listed strike. Generic and SPX0 builders stamp compatible dataset provenance in coordination with the data reviewer. Old three-column persisted mark streams are rejected; newly persisted streams include cost-event counters. A package's lifecycle count is distinct from its number of option legs.

`tests/test_evaluation_audit_regressions.py` preserves adversarial checks for mark drawdown, endpoint mismatch, negative-cash prevention, rolled costs and actual turnover, sidecar migration, daily future-exit selection, initial-loss drawdown, sparse-label purging, tied calibration, regime causality, final-minute availability, conditional baseline windows, exact source fingerprints, raw-cache checkpoint invalidation, prewarm namespace parity, filtered mark validation, and interrupted promotion. Existing mark/model fixtures were migrated to the new schema rather than weakening the checks.

Validation: the focused evaluation/accounting suite passed **137 tests** before the final prewarm parity regression and shared SPX0 integration changes. The final affected subset (audit regressions plus finalizer/loader) then passed **39 tests**, including prewarm namespace parity. The root also ran the integrated suite successfully at **602 passed** during integration; the final root verification supersedes these intermediate counts. No historical returns or live eligibility claims were recomputed. A corrected report cannot be produced by merely relabeling old artifacts; rebuilding/refreezing/retraining is necessary.

Operational implications: legacy scripts require a newly trained winning bundle before prewarming; initial raw-cache fingerprinting reads cache content once per command and deliberately invalidates resume when raw inputs change. Atomic existing-directory promotion requires Linux/filesystem support for directory exchange. Daily evaluation now refuses unresolved filled positions instead of replacing them with survivors. These are explicit correctness boundaries, not optional compatibility fallbacks.

Final coordinating verification: **615 tests passed**. Walk-forward and prewarm both default PIT membership on for v5/v6; regression cases cover explicit opt-out and both default-on pools.
