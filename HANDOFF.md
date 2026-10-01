# Handoff — September 30, 2026 — V6 r4 running with dedicated compute

## Selected user task

Catch V6 completely up through September 30, adding September 29–30 after the
completed September 28 freeze, and measure this two-session daily update.
Keep each completed update and record regressions; do not discard its data/freeze.
User subsequently requested the same dedicated compute as the prior run.
Competing batch jobs are checkpoint-paused again, with automatic restoration
after the September 30 candidate freeze; preserve the original 08:00 cutoff.

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

## Original launch and requested resource revision

`healys-v6-continual.service`, installed `40-daily-v4.conf` drop-in, runs
`scripts/v6_continual_resume_v4.py --autosize-workers` and the r4 launcher.
Root `incubator/continual-v6/r4`; config `deploy/incubator-continual-v6-r4.json`.
Actual full run started **23:04:36 Central**, through **2026-09-30**, 449 symbols.
Three autosized data workers, two training threads, 20-GiB max, CPU quota 400%.
That was the initial coexistence allocation; the dedicated revision supersedes it.
The temporary dedicated revision pauses this timer while its one-time run works.
The existing 08:00 Central cutoff remains. Avoid duplicate manual launchers.

An isolated ADBE preflight finished in 120.27s with 720 candidates, 85 new feature
rows and zero errors. Pilot/full contract identities match. Twelve focused
prefix/inheritance/proposal/schedule checks and nine prefix/inheritance/watcher
checks passed. Full completion remains pending; do not infer it from launch.

## Dedicated revision

`scripts/v6_daily_dedicated_20260930.py` preserves the pinned r4 invocation and
completed symbol seals, uses shared autosizing capped by the prior selected five
workers, 3584 MiB/worker, 4096 MiB host reserve and 2048 MiB parent allowance.
Temporary runtime drop-in `90-dedicated-r4.conf` selects 25/26-GiB high/max,
no CPU quota, 16 training threads, TasksMax 512. Actual restart **23:18:23
Central** selected five workers. All 32 completed symbol seals remained unchanged;
five distinct symbols had fresh progress at 23:18:50, with no new run errors.
It retains `healys-v6-continual.service`, so the existing r4 viewer still follows it.

Evidence root: `nn_meta/validation/v6-daily-update-20260930-r4/dedicated/`.
Before/preserved seal hashes, stop receipts and saved timer/service states precede
restart. Frontier controller hit its three-minute stop timeout/SIGKILL; retain
its saved receipts and inspect resumed capture health. Discovery stopped cleanly;
migration checkpointed at 268,618 files, 202,885,222,673 logical bytes.
On a verified full candidate, remove only the temporary override and
restore competing jobs/timers; failures retain checkpoints for review.
Do not copy the temporary runtime override into persistent user configuration.

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
