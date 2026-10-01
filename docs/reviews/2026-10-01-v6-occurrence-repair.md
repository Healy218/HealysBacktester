# V6 daily occurrence repair — October 1, 2026

The user requested repair of CRSP/MTUM, completion of the September 29–30 update,
and restoration of V7/storage after final training/evaluation/freeze.

## Defect and evidence

r4 exited at 00:59:10 Central with 447/449 completed symbols. Both failures were
`Daily parent artifact inputs differ`. The extended simulation emits an additional
`tv_rating` occurrence at an existing September 28 timestamp: CRSP 19:45, MTUM 13:30.
Raw/adjusted stock prefix hashes and existing proposal fields are unchanged.
Whole-entry feature inheritance incorrectly requires the entire occurrence list
to stay equal, despite preserving proposal ordinals in candidate identity.
CRSP audit: `logs/lab-hourly-watch/crsp-input-mismatch.json`; MTUM audit:
`nn_meta/validation/v6-daily-repair-20261001-r5/mtum-input-mismatch.json`.

## Versioned repair and preservation

`scripts/v6_daily_append_v5.py` validates inherited prefixes/scope and each old
proposal, then resolves existing occurrences to their original feature seal.
Missing occurrences get a separate sealed batch with their real ordinal retained.
The inherited ordinal-zero fast path is not allowed to erase an additional ordinal.
Removed/changed proposals, candidate duplication, prefix changes and label-feature
binding mismatches remain errors. Every historical/current candidate is reconciled.

New namespace r5 binds all prior r4 producer hashes plus the new consumer/launcher.
The scientific model family, fixed-family refit, chronological arrays, baseline
comparison and final immutable freeze pipeline are unchanged. No old receipt is
rewritten or relabeled. Verified r4 census includes 3,516 feature batches, 17,070
labels and 447 completed symbols. Completed inventories are symlinked unchanged
only after original producer contract, snapshot, artifact references and history
hashes are verified. The two missing symbols are newly built with this consumer.

## Verification and selected runtime

23 focused occurrence/prefix/inheritance/resource tests passed; nine viewer and
hourly dispatch checks passed. The real CRSP/MTUM pilot succeeded in 86.77 seconds:
1,725 candidates, 117 matured, 402 pending, 1,206 unfilled, 105 new feature rows.
No errors. Pilot and full producer contract match:
`84452acaf5aefda625ca3d84a3558cee5606e1ebcf421f0dfbb0bfa4464ba6c0`.
Full r5 start: **01:35:39 Central** under `healys-v6-continual.service`.
The full result is recorded below; the pilot alone did not establish completion.

Persistent daily override is `50-daily-v5.conf`; temporary dedicated override is
`95-dedicated-r5.conf`. Dedicated wrapper preserves five autosized worker slots,
16 training threads and 26 GiB, with the existing morning deadline. After verified
full candidate completion, it removes both temporary r5/r4 overrides and restores
the previously saved V7/migration/timer plan. Diagnostic rejection retains the
completed freeze. No automatic paper/live deployment. Failure retains checkpoints
and paused competitors. Evidence lives under the repair validation root above.

CLI and hourly watcher now select r5. Existing open CLI processes need restarting.
Read [CURRENT_STATE](../CURRENT_STATE.md) for receipts and selected configuration;
read [TODO](../../TODO.md) for the active task. Preserve unrelated dirty work.

## Full completion and diagnostic result

Completed **02:32:01 Central October 1**, all 449 symbols and 40 members, zero
errors. Verified 122 candidate files; complete SHA-256:
`4d8693a739c3eb9169f73bb334ee6c11b7fba35c35872b17ef94b9a4093d9a08`.
Recovery elapsed 56m22s; training 39m32s, evaluation/freeze 6m25s. The earlier
447-symbol build and engineering recovery time are outside that 56m22s; do not
present it as a clean two-day incremental benchmark or an unattended daily SLA.
Data reconciliation: 333,260 candidates, 120,249 matured, 100,167 pending and
112,844 unfilled. Prepared arrays: 2,911,662 training / 202,418 validation rows,
164 features. All 447 old symbol seals remain unchanged. Both repaired symbols
retain every old candidate/feature reference and every completed label reference;
CRSP adds 45 candidates, MTUM 60. See `completed-data-audit.json`.

| Diagnostic on current validation rows | Candidate | Previous completed update |
| --- | ---: | ---: |
| Brier | 0.2134633039 | 0.2138818870 |
| Return MSE | 5.3355164642 | 5.3353099292 |
| Return MAE | 0.3863804769 | 0.3868127864 |

Zero-return baseline MSE is 5.3255352311; training-prevalence Brier baseline is
0.2212244868. Diagnostic verdict is rejected because return MSE is worse than
parent and zero baseline. The updated data and immutable freeze remain retained,
as requested. No paper/live deployment or accepted-research promotion occurred.
These are reused purged temporal validation results, not an untouched test.

## Verified restoration and transport recovery

At 02:32, the dedicated wrapper verified completion, removed both temporary V6
overrides, restored paused timers and started all three research/storage services.
Discovery and migration advanced. Frontier stopped immediately on two old HTTP
502 failures; its historical `draining` receipt was not a healthy running process.
`scripts/resume_v7_frontier_transport_20261001.py` binds the exact stopped receipt
and permits one explicit retry through the unchanged capture producer. It archives
the old progress and supervised pass, verifies/reuses completed packs and queues
only missing seals; no failures are relabeled as success. Other failure types are
not admitted. Five focused admission/rejection checks passed.
Runtime override `98-transport-recovery.conf` restarted the existing frontier
service at 02:48:11. At 02:49 it was capturing 64,584/126,719 windows with no new
failed batches; discovery had fresh active securities, migration had moved
275,575 files / 204,212,780,359 logical bytes. All three cgroups showed active CPU.
The backup/archive/daily-V6 timers were restored. Subsequent same-date V6 timer
runs verify the frozen candidate and exit successfully without retraining.
Recovery receipt roots: `nn_meta/validation/v6-daily-repair-20261001-r5/` and
`nn_meta/validation/v7-frontier-restart-20261001-r0/`.
The selected task is complete; full V7 input coverage and migration completion
remain open under gate 7-3, and clean one-session timing/coexistence remain separate.
