# Handoff — September 30, 2026 — V6 two-session update running in r4

## Selected user task

Catch V6 completely up through September 30, adding September 29–30 after the
completed September 28 freeze, and measure this two-session daily update.
Keep each completed update and record regressions; do not discard its data/freeze.
V7 and migration continue under their restored resource allocations.

## Why a new lineage was necessary

Persistent-timer restoration had already started an r3 September 30 attempt at
22:40:49. Refreshed provider data revised previously consumed bars; history
checks correctly refused them. Stopped only V6 daily service/timer while fixing
this transition. Preserved 25 completed symbols, 105 observed history errors and
all earlier artifacts. This failed attempt is not a valid daily timing result.

r4 preserves the exact September 28 frozen stock prefix and appends later bars.
Provider revision audit: 343 symbols, primarily volume; 23,087 new raw bars.
Verified 231,323 r3 parent seals; r2 ancestry remains referenced, never relabeled.
The original r3 scientific source hashes and completed candidate are unchanged.

## Current selected runtime

`healys-v6-continual.service`, installed `40-daily-v4.conf` drop-in, runs
`scripts/v6_continual_resume_v4.py --autosize-workers` and the r4 launcher.
Root `incubator/continual-v6/r4`; config `deploy/incubator-continual-v6-r4.json`.
Actual full run started **23:04:36 Central**, through **2026-09-30**, 449 symbols.
Three autosized data workers, two training threads, 20-GiB max, CPU quota 400%.
This is the regular coexistence allocation, not the earlier dedicated 26-GiB run.
Daily/retry timer restored; next retry opportunity observed 00:00 Central.
The existing 08:00 Central cutoff remains. Avoid duplicate manual launchers.

An isolated ADBE preflight finished in 120.27s with 720 candidates, 85 new feature
rows and zero errors. Pilot/full contract identities match. Twelve focused
prefix/inheritance/proposal/schedule checks and nine prefix/inheritance/watcher
checks passed. Full completion remains pending; do not infer it from launch.

## Evidence, progress and timing

`incubator/continual-v6/r4/latest-run.json` and `resources.json` own live state.
Stage start events are recorded in the run status for actual measured timings.
`nn_meta/validation/v6-daily-update-20260930-r4/` contains preparation, failed-r3
attempt/exit, pilot and launch receipts. Snapshot revision audit is under
`r4/snapshots/2026-09-30/revision-audit.json`.

Restart the CLI viewer to load its new defaults:
`./venv/bin/python scripts/watch_v6_incubator.py --follow`.
Already-open old viewer processes still observe r3. Ctrl-C affects only viewer.
[Review](docs/reviews/2026-09-30-v6-two-day-update.md) · [State](docs/CURRENT_STATE.md).

## Completion boundary and prior result

New r4 data reconciles all frozen symbols and matured/pending outcomes, then
trains 40 members, evaluates and freezes. Diagnostic comparison now uses the
preceding completed update, initially the September 28 candidate, regardless of
its diagnostic verdict. Evaluation does not discard a completed update.
Preserve model family, chronological validation and point-in-time evidence.

Prior September 28 candidate completed at 22:40:47, 122 verified files; training
35m29s, evaluation/freeze 5m36s. Its return-MSE diagnostic failed, but its data and
freeze remain. No paper/live deployment changed. OPS-INCUBATOR.PROOF remains open.
Keep MRHA mounted and preserve unrelated dirty/untracked work.
