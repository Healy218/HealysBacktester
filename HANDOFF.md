# Handoff — October 1, 2026 — V6 current; V7 and storage resumed

## Completed user task

Fixed CRSP/MTUM, finished V6 through September 30, and resumed V7/storage.
Final r5 candidate frozen **02:32:01 Central**, 449/449 symbols, 40/40 members,
zero errors; 122 candidate files independently hash-verified.
Full recovery run 56m22s, training 39m32s, evaluation/freeze 6m25s. This reuses
447 earlier completed symbols; it is not a clean unattended daily benchmark.
All 447 original symbol seals and both repaired symbols' old feature/completed
label references remain unchanged. Prior failed attempts and parent artifacts retained.

## Selected artifacts and evaluation

Root `incubator/continual-v6/r5`; config `deploy/incubator-continual-v6-r5.json`.
Candidate `r5/runs/2026-09-30/candidate`, complete hash
`4d8693a739c3eb9169f73bb334ee6c11b7fba35c35872b17ef94b9a4093d9a08`.
333,260 candidates: 120,249 matured, 100,167 pending, 112,844 unfilled.
Training/validation arrays: 2,911,662 / 202,418 rows, 164 features.
Diagnostic rejected: return MSE 5.335516 vs parent 5.335310 and zero baseline
5.325535. Brier improved: 0.213463 vs parent 0.213882. These are reused temporal
validation diagnostics, not untouched performance evidence. The new freeze/update
is retained as requested. No paper/live deployment or accepted-research promotion.

## Daily operation and restart evidence

`healys-v6-continual.service`, persistent `50-daily-v5.conf`, selects
`scripts/v6_continual_resume_v5.py`. Both temporary r4/r5 dedicated overrides
were removed on success; ordinary daily resource policy and schedules restored.
Subsequent same-date timer runs may report `candidate_already_frozen`; they do
not repeat training. Use `incubator-result.json` below for the full completed run.
Evidence: `nn_meta/validation/v6-daily-repair-20261001-r5/` includes preparation,
pilot, completed-data audit, completion verification and restored-progress verification.
CLI: `./venv/bin/python scripts/watch_v6_incubator.py --follow` (defaults r5).

## V7 and migration are running again

Original discovery and MRHA migration restored automatically at 02:32.
Frontier initially stopped on two retained HTTP 502 failures from the earlier
interrupted capture. User's restart instruction was completed with a versioned,
one-time transport recovery, retaining attempts and all completed packs.
Selected frontier runtime override `98-transport-recovery.conf` invokes
`scripts/resume_v7_frontier_transport_20261001.py`; original producer/resource
bindings remain. Evidence `nn_meta/validation/v7-frontier-restart-20261001-r0/`.
Restart **02:48:11 Central**. At 02:49, capture advanced to 64,584/126,719 windows,
no failed batches; discovery had fresh active securities; migration advanced to
275,575 files / 204,212,780,359 logical bytes. All three had active cgroup CPU.
Per-pass discovery count 7 is not cumulative retained completion. Gate 7-3 stays
open; completed entry capture remains complete. Continue existing controllers,
not new captures of completed scope. Backup/archive/daily V6 timers restored.

## Remaining proof and constraints

The repaired two-session update is complete. A clean one-session timing and
sustained resource coexistence remain under OPS-INCUBATOR.PROOF/OPS.
Hourly read-only watcher continues each :00 Central in this terminal, bound to
r5 and repair evidence. Pending reports wait behind active work; logs under
`logs/lab-hourly-watch`. No frozen-source edits, artifact relabeling, paper/live
promotion or external messaging. Keep MRHA mounted and preserve unrelated work.
[Repair/completion review](docs/reviews/2026-10-01-v6-occurrence-repair.md) · [State](docs/CURRENT_STATE.md).
