# Handoff — October 1, 2026 — V6 r5 occurrence repair running

## Selected user task

Fix CRSP and MTUM, finish the September 29–30 V6 update through training,
evaluation and final freeze, then start V7 and storage again. Preserve successful
work and continue hourly health reports in this terminal. No paper/live deployment.

## Diagnosed failure and repair

r4 stopped at 00:59:10 Central with 447/449 symbols complete. CRSP and MTUM had
`Daily parent artifact inputs differ`. Both retain identical stock prefix hashes,
but the longer simulation adds a `tv_rating` ordinal-1 occurrence at an existing
September 28 entry timestamp (CRSP 19:45; MTUM 13:30). Whole-batch reuse rejected
these additions. Old producers, completed inventories, features and labels remain.

New r5 consumer `scripts/v6_daily_append_v5.py` preserves the original batch/seal
for existing occurrences and creates separate sealed batches for additions.
It rejects changes/removals of inherited proposals and prefixes, retains nonzero
ordinals, and reconciles every old/new candidate. The 447 completed r4 symbols
are referenced by unchanged symlinked inventories after input/contract/lineage
verification, not relabeled. Their stock histories are copied with digest checks.

Verified r4 census: 3,516 feature batches, 17,070 label seals, 447 completed symbols.
Two-symbol real-data pilot succeeded in 86.77 seconds: 1,725 candidates,
117 matured, 402 pending, 1,206 unfilled, 105 new feature rows, zero errors.
Pilot/full scientific contract: `84452acaf5aefda625ca3d84a3558cee5606e1ebcf421f0dfbb0bfa4464ba6c0`.
23 focused recovery/resource tests and nine CLI/hourly watcher tests passed.
No complete model/evaluation result is claimed yet.

## Selected runtime and evidence

`healys-v6-continual.service`; full r5 start **01:35:39 Central October 1**.
Root `incubator/continual-v6/r5`; config `deploy/incubator-continual-v6-r5.json`.
Reads the same frozen r4 September 30 snapshot and original fixed model family.
`scripts/run_v6_continual_v5.py` retains array/training/evaluation/freeze sequencing.
Original r4 producer hashes are unchanged; r5 additionally binds the new consumer.
Five autosized data worker slots, 16 training threads, 25/26-GiB high/max, no CPU quota.
Only the two incomplete symbols need new builds after inherited verification.
Existing next-morning 08:00 Central cutoff remains.

Evidence root: `nn_meta/validation/v6-daily-repair-20261001-r5/`.
`prepared.json` owns the 447 preserved seals; `bound.json` binds runtime and
restoration code; pilot receipts/log, MTUM diagnosis, failed-r4 run and exit saved.
Read r5 `latest-run.json`, `resources.json`, per-symbol/member receipts for health.

## Automatic completion and restoration

Persistent `50-daily-v5.conf` selects `v6_continual_resume_v5.py`.
Temporary runtime `95-dedicated-r5.conf` runs `v6_daily_repair_dedicated_v5.py`.
After verified full candidate completion, it checks old seals, removes both
runtime 95-r5 and superseded 90-r4 overrides, and restores the original r4 saved
pause plan: V7 required discovery/frontier, MRHA migration and paused timers.
Do not install temporary overrides persistently. Failures retain checkpoints and
paused competitors for review. Diagnostic rejection does not discard the freeze.

## Watchers and next action

CLI: `./venv/bin/python scripts/watch_v6_incubator.py --follow`; defaults now r5.
Already-open viewers need restarting or explicit r5 arguments.
`healys-lab-hourly-watch.timer` continues each :00 America/Chicago, target thread
`01a0f343-c76a-7842-915b-0c111e8e2e28`; its producer now observes r5 and repair evidence.
Health reports are read-only and wait behind active user work; snapshots/logs
under `logs/lab-hourly-watch`. Continue through actual freeze and verify restored
V7/storage progress. Frontier's old stop timeout is historical, not new failure.
Keep MRHA mounted. Preserve unrelated dirty/untracked work.
[Repair review](docs/reviews/2026-10-01-v6-occurrence-repair.md) · [State](docs/CURRENT_STATE.md).
