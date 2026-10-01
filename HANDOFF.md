# Handoff — September 30, 2026 — V6 resumed with 424 verified symbols

## Selected direction

Finish the pinned V6 catch-up, training and evaluation; restore paused batch
jobs automatically after a verified candidate freeze. User reported the CLI
stopped with 35 missing symbols; investigated and resumed. [TODO](TODO.md) owns tasks.

## Resolved stopping point

The main pass stopped at 19:15:23 with 414/449 complete and 35 failures.
The separate retry helper recovered all ten HTTP 502 symbols by 20:13:48,
but did not admit 25 differently worded transport failures. Its strict HTTP
502-only filter prevented automatic main resumption; it exited needs_review.
Actual verified count was 424/449, not the old main receipt's 414/449.

Verified all 424 completion payloads and unchanged frozen sources/snapshot.
Confirmed main failed and side retry inactive before starting the main service.
At **20:47:50 Central**, the same focus service resumed, selecting five workers.
At 20:48:12, fresh WFC/WMT/WPM/WULF/WYNN progress was observed; main receipt
showed 424/449 (94.4%) with no new errors. Training remained pending.
All 424 pre-resume completion seals remained byte-identical.

## Current runtime

`healys-v6-focus-20260930.service`, installed `20-workers.conf` drop-in;
entry `scripts/v6_focus_workers_20260930.py --worker-mib 3584 --auto-restore`.
Pinned root `incubator/continual-v6/r3`, through September 28. Sources, inputs,
scientific method and next-open-minus-30-minute cutoff (08:00 Central) unchanged.
Five autosized workers; 3584-MiB worker budget, 4096-MiB host reserve,
2048-MiB parent allowance, 25/26-GiB service high/max, no swap. Training threads 16.

Finish missing data → checks/arrays → 40 sequential ensemble members → evaluation
→ verified freeze → automatic paused-job restoration. No automatic deployment.
Failure/deadline retains checkpoints and keeps competing jobs paused for review.

## Evidence and monitor

Resume evidence: `nn_meta/validation/v6-focus-20260930/transport-resume-r1/`.
`before.json` preserves 424 seal hashes; prior run/focus/exit/worker-restart
receipts are archived there. `after.json` records resumed state and preservation.
Main stage: `incubator/continual-v6/r3/latest-run.json`.
Focus state: `nn_meta/validation/v6-focus-20260930/progress.json`.
`./venv/bin/python scripts/watch_v6_incubator.py --follow` follows the new pass.
Ctrl-C closes only the viewer. Compare receipts with fresh service/journal state.
[State](docs/CURRENT_STATE.md) · [Review](docs/reviews/2026-09-30-v6-dedicated-compute.md).

No scientific code changed in this recovery. Existing source/snapshot preflight,
424 payload verifications, pre/post seal comparison and fresh symbol updates
passed. Remaining completion and full training/freeze are not yet demonstrated.

## Prior retry helper and constraints

`healys-v6-symbol-retries-20260930.service` finished; do not start its old helper
again against this new invocation. Its plan is bound to the previous start time.
Evidence retained under `symbol-retries-r1/` in the focus state directory.

V7/migration remain checkpointed by the 15:01 handover. Migration retained
254,561 files/200.127 GB logical; current quote batch retained 40,992 windows.
Restore V7 successor controllers after verified V6 completion; do not restart
original discovery/capture units. Keep MRHA mounted. Broker order management,
monitoring and remote experts remain. Preserve unrelated dirty/untracked work.
V7-3 and full-incubator proof remain open; October 2 provider decision is separate.
