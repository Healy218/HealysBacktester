# V7 current state and download locations

Updated September 27, 2026. **V7-1 and V7-2 complete. V7-3 entry acquisition
running. Model training not started.** Read [TODO](../TODO.md) for unfinished
work and [ROADMAP](../ROADMAP.md#completed-work) for completed work.

## Running download

- Service: `healys-v7-capture-v3-20260927.service` (home box).
- Live meter: `nn_meta/validation/v7-entry-campaign-v3-20260927/progress.json`.
- Immutable launch: `nn_meta/validation/v7-entry-campaign-v3-20260927/declaration/`.
- New packs: `nn_meta/data_v7/entry-campaign-20260927/<security>/<batch-hash>/`.
- Attempt journal: `nn_meta/validation/v7-entry-campaign-v3-20260927/attempts/`.
- Shared acquisition accounting: `nn_meta/data_v7/quota.json`.
- Launcher: `bash scripts/start_v7_capture_campaign_v3.sh 16`; do not start a duplicate
  while the service is active. Existing batches are verified/reused on resume.
- [Concurrency upgrade](reviews/2026-09-27-v7-parallel-capture.md); original
  declaration and journals remain in `v7-entry-campaign-20260927/`.
- [Original launch review](reviews/2026-09-27-v7-entry-campaign-started.md) and
  [initial live proof](reviews/2026-09-27-v7-entry-campaign-launch.json).

This job downloads the exact full-universe **entry quote/trade** union minus
already captured coverage. It does not yet automate all held/roll/stock/reference
acquisition or assembly/training. Those are the precise remaining V7-3/next-stage
connections in TODO, not reasons to rebuild completed preparation.

Four autosized process workers with 16 bounded I/O threads each (64 requests
maximum); one compute thread per worker; 10 GiB MemoryHigh / 14 GiB MemoryMax; no swap allocation;
400% CPU quota, low priority. The initial new-data allocation is 100 GB, with the
unchanged 250 GB acquisition / 640 GB project limits and 20 GiB free reserve.
MRHA use is authorized. The 100 GB number is a dispatch guard, not a total size
forecast. It pauses on a limit/provider failure and drains current work.

## Authoritative completed inputs — reuse exactly

All shorthand roots below are under `nn_meta/validation/`.

| Input or completed work | Location |
| --- | --- |
| V7-2 completion | `v7-2-completion-20260925/complete.json` + `gate.json` |
| Frozen 591-security / 1,773-store catalog | `v7-2-full-catalog-20260922-rebuild-5-15-30/` |
| Full causal daily/market context | `v7-daily-context-20260925-full/` |
| Full completed demand | `v7-3-scheduler-20260925/demand/<security>/` |
| Full demand/entry union audit | `v7-3-entry-union-20260926/` |
| Existing packed coverage used by live campaign | `v7-execution-sample-index-20260927-r12/` |
| Dated reference demand | `v7-dated-reference-demand-20260927/` + sibling `.checkpoints/<security>/references.sqlite3` |
| Dated regular option hours | `v7-dated-hours-20260927/`; audit `v7-dated-hours-audit-20260927/` |
| Five exact reference blackouts | `v7-contract-blackouts-20260927/`; entry impact `v7-contract-blackout-impact-20260927/` |
| First-leg conservative envelopes | `v7-execution-envelopes-20260927/` + sibling `.checkpoints/` |
| Last actual five-path replay state | `v7-execution-discovery-20260927-r12/` |
| Replay restart audit | `v7-execution-pilot-audit-20260927/` |
| Packed entry volume estimate | `v7-joined-packed-v2-forecast-20260926/` |
| Verified cleanup/migration | `v6-archive-migration-20260926/` and [review](reviews/2026-09-26-authorized-storage-reclamation.md) |

Raw dated reference sample: `nn_meta/data_v7/entry-joined-sample-references-20260926/`.
Raw execution packs: `nn_meta/data_v7/execution-frontier-20260927-r1` through `-r12`.
Historical exchange sources: `nn_meta/data_v7/option-hours-evidence-20260927/`
and `option-hours-followup-20260927/`. Captured calendar:
`nn_meta/data_v7/exchange-calendar-20260916/`.

## Exact remaining boundary

The dated-reference **plan** is finished; most full-scope reference **downloads**
remain. The hours reconstruction is finished for the reviewed scope. The five
blackouts are implemented; do not re-investigate or broaden them. The entry
request plan/packing/cleanup are complete; the live service is executing that
plan. Replay machinery exists; actual remaining paths/captures and full dataset
assembly still have to run. No full trained V7 artifact exists.

Model history remains 2022-03-15 through 2026-09-14. Regular-hours rule coverage
extends through 2026-09-23; do not confuse that with a model-history extension.
All 591 securities, 5/15/30 signals, 221 features and existing execution/fold
policies remain. Do not treat `research_ready:false` on an intermediate artifact
as evidence that its completed subtask failed. The legacy readiness checker has
stale pre-amendment/222-column requirements; consume current receipts instead
of rewriting freezes to turn that old report green.

## Current 7-4 integration — September 27

The versioned shared/physical runner is connected. Latest actual ledger:
`nn_meta/validation/v7-integrated-execution-20260927-r2/`; quote snapshot:
`v7-integrated-quote-index-20260927-r2`; retained source paths:
`v7-execution-discovery-20260927-r13` (validation roots). Use these newer receipts
for integration; r12 remains valid original evidence. The shared ledger completed
DIS/ABBV, retains NVDA at its next exact missing mark, and has not reached real
exercise/stock liquidation. Full V7-4 is still open. See the
[integration review](reviews/2026-09-27-v7-integrated-execution.md) and the current
three-argument `scripts/run_v7_integrated_execution.sh` launcher.
