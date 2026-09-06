# September 5 audit remediation

All **51 main code findings and four additional implementation concerns** have corrective changes in the review checkout. The [original audit](2026-09-05-adversarial-audit.md) remains a record of commit `f98ed265db3ce3faf4ba7abf8e6604671e3a1c90`; its reproduction scripts demonstrate the old mechanisms. Use the new regression tests to verify corrected behavior.

The changes repair causal signals/splits, mark and cash accounting, cache/history preservation, PIT selection, checkpoint and model provenance, scanner parity/state, FA evidence, and operational failure handling. Documentation now distinguishes historical deployments/verdicts from this checkout's current repair work. Integration review additionally fixed SPX0 dollar/package fee replay, package fill counts, source-spec binding, and the transport/prewarm paths affected by stricter provenance.

## Validation

**Final integrated suite: 615 passed, zero failures/skips, 18 subtests passed, 10 warnings in 20.42 seconds.**

```bash
PYTHONDONTWRITEBYTECODE=1 NUMBA_CACHE_DIR=/tmp/healys-review-numba MPLCONFIGDIR=/tmp/healys-review-mpl /home/healy/Coding/HealysBacktester/venv/bin/python -m pytest tests/ -q -p no:cacheprovider
```

`bash -n` passed independently for all six affected operational launchers checked; `git diff --check` and local links in the current repair/entry-point documentation passed. Remaining warnings are dependency deprecations/future warnings and Keras optimizer-state loading during inference fixtures. They did not fail validation.

Tests exercise isolated synthetic data and simulated failure paths. No provider requests, full historical rebuild, production model training, cloud workload, notification or deployment was performed. Targeted specialist results overlap the full suite and should not be added to it as unique tests. Changes to older tests reflect explicit timing/schema migrations, with new independent adversarial cases checking the corrected outcomes.

## Important behavior changes

- **Old derived inputs fail default validation.** `2026-09-05-causal-v2` is recorded in freezes, dataset/checkpoint provenance and bundles. Dataset fingerprints bind the exact source baseline. Old checkpoints cannot be silently resumed or mixed with corrected rows and marks. Stored model files have not been rewritten to pretend they were retrained.
- **Evaluation is honest about baseline optimization.** Globally frozen proposals are evaluated only on validation/test windows after their optimization horizon. Reports identify this as conditional evaluation; fully nested proposal optimization still requires fold-local freezes/rebuilds. SPX0 preserves the actual source proposal-training horizon too.
- **Marks represent real event availability and every fill.** Entry-open and completed-bar marks are ordered separately. Costs include rolls; new positions are cash-limited; terminal marks reconcile with execution. SPX0 uses its own dollar/package friction for base/stressed scenarios instead of silently substituting equity percentage fees.
- **Live previews preserve production state.** Dry runs use temporary snapshots. Failed notifications remain in the outbox, overlapping passes serialize, and stale/forming bars do not trigger current alerts. Legacy and v4/v5 scoring use the same configured decision-time moneyness target as new training data.
- **Checkpoint completion is validated, not inferred from a filename.** Cloud/local transport moves marks, rows and provenance together, with provenance last; builders verify current inputs and coverage. Remote freeze resumes also validate the current contract/hash. Walk-forward and prewarm share a content-addressed namespace and default to PIT membership for both v5/v6. Failures propagate to process status. The cloud guard retries unknown/failed requests and monitors terminal state; it remains a best-effort monitor rather than a guaranteed billing cap.
- **FA scores describe available evidence.** Capture cutoffs, global evidence identity, cohort joins and explicit measurement windows are enforced. Old unversioned rankings are historical and do not count as new prospective evidence.

## Finding disposition

Every main finding is implemented. Detailed change descriptions and regression evidence are in the specialist repair reports.

| Finding | Disposition | Details |
|---|---|---|
| CORE-01 | Implemented with regression coverage | [Change and evidence](2026-09-05-core-fixes.md) |
| CORE-02 | Implemented with regression coverage | [Change and evidence](2026-09-05-core-fixes.md) |
| CORE-03 | Implemented with regression coverage | [Change and evidence](2026-09-05-core-fixes.md) |
| CORE-04 | Implemented with regression coverage | [Change and evidence](2026-09-05-core-fixes.md) |
| CORE-05 | Implemented with regression coverage | [Change and evidence](2026-09-05-core-fixes.md) |
| CORE-06 | Implemented with regression coverage | [Change and evidence](2026-09-05-core-fixes.md) |
| CORE-07 | Implemented with regression coverage | [Change and evidence](2026-09-05-core-fixes.md) |
| CORE-08 | Implemented with regression coverage | [Change and evidence](2026-09-05-core-fixes.md) |
| CORE-09 | Implemented with regression coverage | [Change and evidence](2026-09-05-core-fixes.md) |
| CORE-10 | Implemented with regression coverage | [Change and evidence](2026-09-05-core-fixes.md) |
| CORE-11 | Implemented with regression coverage | [Change and evidence](2026-09-05-core-fixes.md) |
| CORE-12 | Implemented with regression coverage | [Change and evidence](2026-09-05-core-fixes.md) |
| CORE-13 | Implemented with regression coverage | [Change and evidence](2026-09-05-core-fixes.md) |
| D1 | Implemented with regression coverage | [Change and evidence](2026-09-05-data-fixes.md) |
| D2 | Implemented with regression coverage | [Change and evidence](2026-09-05-data-fixes.md) |
| D3 | Implemented with regression coverage | [Change and evidence](2026-09-05-data-fixes.md) |
| D4 | Implemented with regression coverage | [Change and evidence](2026-09-05-data-fixes.md) |
| D5 | Implemented with regression coverage | [Change and evidence](2026-09-05-data-fixes.md) |
| D6 | Implemented with regression coverage | [Change and evidence](2026-09-05-data-fixes.md) |
| D7 | Implemented with regression coverage | [Change and evidence](2026-09-05-data-fixes.md) |
| D8 | Implemented with regression coverage | [Change and evidence](2026-09-05-data-fixes.md) |
| E01 | Implemented with regression coverage | [Change and evidence](2026-09-05-evaluation-fixes.md) |
| E02 | Implemented with regression coverage | [Change and evidence](2026-09-05-evaluation-fixes.md) |
| E03 | Implemented with regression coverage | [Change and evidence](2026-09-05-evaluation-fixes.md) |
| E04 | Implemented with regression coverage | [Change and evidence](2026-09-05-evaluation-fixes.md) |
| E05 | Implemented with regression coverage | [Change and evidence](2026-09-05-evaluation-fixes.md) |
| E06 | Implemented with regression coverage | [Change and evidence](2026-09-05-evaluation-fixes.md) |
| E07 | Implemented with regression coverage | [Change and evidence](2026-09-05-evaluation-fixes.md) |
| E08 | Implemented with regression coverage | [Change and evidence](2026-09-05-evaluation-fixes.md) |
| E09 | Implemented with regression coverage | [Change and evidence](2026-09-05-evaluation-fixes.md) |
| E10 | Implemented with regression coverage | [Change and evidence](2026-09-05-evaluation-fixes.md) |
| E11 | Implemented with regression coverage | [Change and evidence](2026-09-05-evaluation-fixes.md) |
| E12 | Implemented with regression coverage | [Change and evidence](2026-09-05-evaluation-fixes.md) |
| E13 | Implemented with regression coverage | [Change and evidence](2026-09-05-evaluation-fixes.md) |
| E14 | Implemented with regression coverage | [Change and evidence](2026-09-05-evaluation-fixes.md) |
| E15 | Implemented with regression coverage | [Change and evidence](2026-09-05-evaluation-fixes.md) |
| LO-01 | Implemented with regression coverage | [Change and evidence](2026-09-05-live-ops-fixes.md) |
| LO-02 | Implemented with regression coverage | [Change and evidence](2026-09-05-live-ops-fixes.md) |
| LO-03 | Implemented with regression coverage | [Change and evidence](2026-09-05-live-ops-fixes.md) |
| LO-04 | Implemented with regression coverage | [Change and evidence](2026-09-05-live-ops-fixes.md) |
| LO-05 | Implemented with regression coverage | [Change and evidence](2026-09-05-live-ops-fixes.md) |
| LO-06 | Implemented with regression coverage | [Change and evidence](2026-09-05-live-ops-fixes.md) |
| LO-07 | Implemented with regression coverage | [Change and evidence](2026-09-05-live-ops-fixes.md) |
| LO-08 | Implemented with regression coverage | [Change and evidence](2026-09-05-live-ops-fixes.md) |
| LO-09 | Implemented with regression coverage | [Change and evidence](2026-09-05-live-ops-fixes.md) |
| LO-10 | Implemented with regression coverage | [Change and evidence](2026-09-05-live-ops-fixes.md) |
| LO-11 | Implemented with regression coverage | [Change and evidence](2026-09-05-live-ops-fixes.md) |
| LO-12 | Implemented with regression coverage | [Change and evidence](2026-09-05-live-ops-fixes.md) |
| LO-13 | Implemented with regression coverage | [Change and evidence](2026-09-05-live-ops-fixes.md) |
| LO-14 | Implemented with regression coverage | [Change and evidence](2026-09-05-live-ops-fixes.md) |
| LO-15 | Implemented with regression coverage | [Change and evidence](2026-09-05-live-ops-fixes.md) |

The four additional evaluation concerns are also implemented: atomic directory exchange for bundle replacement; complete load-critical verification coverage; inclusion of the final fold remainder; and explicit handling of a zero baseline return. See the [evaluation repair report](2026-09-05-evaluation-fixes.md).

## Rebuild and rollout boundary

Source repairs are complete; corrected historical performance and a production rollout are **not** claimed. The review checkout does not contain the production raw market caches or a newly trained ensemble.

Before deploying this source with active scanners, use the target environment to:

1. Preserve and reconcile raw archives, including restoring any compaction-deleted dates from surviving copies. The compaction fix prevents further loss; it cannot recreate missing observations.
2. Re-freeze affected strategy pools under the current contract into fresh outputs. Rebuild per-symbol/family rows, marks and PIT-filtered assembly; retain their provenance files. Old additive v5 outputs do not qualify for automatic reuse.
3. Train/evaluate/finalize on those exact inputs, with post-freeze validation windows and the corrected cash/cost ledger. Inspect both candidate and baseline results, mark hashes, effective gate settings and source-spec fingerprints. A newly failed gate must remain a refusal.
4. Produce prospective FA rankings under the corrected recipe; do not count the known contaminated historical monthly as a clean forward test.
5. Verify new bundles and exercise isolated previews before any separately authorized deployment. Default loaders deliberately refuse stale bundles, so installing code ahead of rebuilt artifacts would stop affected scanners.

The September 4 gate revision is preserved in the decision/experiment history. Repairing code cannot manufacture an untouched holdout after a selection decision; future effectiveness claims need fresh forward evidence.

Platform limits: process locks use POSIX advisory locking. Atomic replacement of an existing model directory uses Linux `renameat2` exchange; an unsupported platform/filesystem refuses promotion while retaining the old directory. Mocked shell tests verify failure handling but do not establish cloud-provider or deployed-host availability.

No commits, pushes, source deployment, trained-artifact regeneration or production-state changes were performed. All edits remain reviewable in this workspace.
