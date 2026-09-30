# Handoff — September 30, 2026 — V6 terminal progress viewer active

## Selected direction

Finish V6 incubator catch-up, training and evaluation with local batch compute
reserved for it; automatically restore paused jobs after a verified candidate
freeze. User requested a V6 terminal progress bar after the worker increase. [TODO](TODO.md) owns tasks.

## Actual handover and progress

The 15:01 handover ran. V7 successor controllers stopped; initial quote capture,
discovery and MRHA migration checkpointed cleanly. Drain finished 15:03:48; V6
started 15:03:52 with four workers. The 15:05 report reached this terminal.

- Migration stopped at 254,561/504,516 files and 200.127/229.378 GB logical.
- Current V7 quote batch retained 40,992/126,719 windows; successor replay has
  not started. Original discovery retained 46.665 million horizon-targets,
  28 complete wave receipts across 93 started securities; per-pass count was 22.
- V6 was 362/449 complete at 16:47:44 Central; training had not started.
  Read the live receipt for subsequent counts.

## Current V6 runtime

Service: `healys-v6-focus-20260930.service`, installed drop-in
`healys-v6-focus-20260930.service.d/20-workers.conf`, entry point
`scripts/v6_focus_workers_20260930.py --worker-mib 3584 --auto-restore`.
Restarted **16:33:47 Central**, same September 28 r3 input/snapshot. All 357
completed symbol seals verified unchanged. Five worker processes independently
verified after shared autosizing selected five; service-budget ceiling is six.
Resource allowance is 3584 MiB/worker, 4096 MiB host reserve and 2048 MiB parent
allowance inside 25/26-GiB high/max, no swap. No CPU quota; training gets 16
available threads. Original bound scientific sources remain unchanged.

The old SIGTERM exit/semaphore cleanup came from the requested pool restart.
Prior receipts: `nn_meta/validation/v6-focus-20260930/worker-revisions/r1/`.
`before.json`, `stopped-run.json`, `prior-service-exit.json` and `restart.json`
retain identities and resource evidence. Read latest timestamps and the journal.

## Completion and restoration

Finish all 449 symbols and data checks → train 40 ensemble members sequentially
→ evaluate → freeze/verify candidate → automatically restore paused timers and
V7/migration. No build-only flag. Rejected evaluation preserves the incumbent;
it is still a completed candidate run. No automatic deployment.

Failure, incomplete data or deadline leaves competitors paused for review. The
next-session opening-minus-30-minute cutoff (08:00 Central) is unchanged.
Restore original timer states and V7 successor controllers; do not restart initial
quote/discovery units. Resource wrapper `resume_v7_compute_20260930.py` admits
up to two discovery, four capture and one serial replay worker; 8/6-GiB limits.

## Terminal viewer and next inspection

Opened a separate Konsole running `./venv/bin/python scripts/watch_v6_incubator.py
--follow`; refreshes every five seconds through data, training and evaluation/freeze.
Four stage/stopped-state tests passed; host readback confirmed viewer PID 1701646.
Ctrl-C closes only the viewer. Research-only; no runtime producer changes.

Main handover state: `nn_meta/validation/v6-focus-20260930/progress.json` and
`pause-plan.json`. Actual V6 stages: `incubator/continual-v6/r3/latest-run.json`.
Inspect service/journal alongside receipts; a stale running file is insufficient.
Eleven focused worker/handover tests, real source/snapshot checks, preserved-seal
comparison, unit verification and live five-worker readback passed. Throughput
increase and full completion have not yet been measured.
[Review](docs/reviews/2026-09-30-v6-dedicated-compute.md) · [State](docs/CURRENT_STATE.md).

Keep MRHA mounted. Basic broker order management/monitoring remain enabled.
Remote experts and unrelated dirty/untracked work remain untouched. V7-3 stays
open with all completed evidence valid; October 2 provider decision is separate.
