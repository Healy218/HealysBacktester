# Handoff — September 30, 2026 — concurrent V6 retries running

## Selected direction

Finish the pinned V6 catch-up, training and evaluation; automatically restore
paused batch jobs after a verified candidate freeze. The user requested retries
while the main pass keeps running. [TODO](TODO.md) owns phase tasks.

## Current runtime

Main: `healys-v6-focus-20260930.service`, worker-revision drop-in
`20-workers.conf`; wrapper `scripts/v6_focus_workers_20260930.py`.
Five autosized data workers since 16:33:47 Central; 3584 MiB per worker,
4096 MiB host reserve, 2048 MiB parent allowance, 25/26-GiB service high/max.
Training selects 16 threads, with 40 members processed sequentially.
Pinned root `incubator/continual-v6/r3`, through September 28, unchanged
scientific sources and contract. All 357 prior symbol seals survived the restart.

At 18:51 Central the main receipt showed 403/449 complete and ten terminal
Massive HTTP 502 errors; training had not started. Those counts are dated.
Individual HTTP requests already receive five short retries before failing.

## Concurrent recovery

Installed/started `healys-v6-symbol-retries-20260930.service` at 18:53:58 Central.
Entry point `scripts/v6_retry_failed_20260930.py`; one extra worker at most,
3584-MiB hard service limit, no swap. Shared autosizer plus explicit available
memory and aggregate planned-worker budget checks gate admission.
UCO completed/verified at 18:59:34; ULTA retry then started.

Only symbols listed as terminal HTTP 502 failures are eligible. Main futures
for those symbols have exited; retry builds call the unchanged frozen builder
with the same inputs, contract and symbol-specific checkpoint paths. Main
invocation identity must remain unchanged. No competing full-run launcher.
Up to three later attempts per failed symbol with a two-minute retry delay.
Receipts/logs: `nn_meta/validation/v6-focus-20260930/symbol-retries-r1/`.

The main supervisor retains failures in memory. Once its pass exits and every
failed symbol is verified recovered, the retry helper archives its old receipts
and requests a fresh start of the same focus service. That start verifies/reuses
all seals, then continues training, evaluation and final candidate freeze.
If failures remain, other errors appear or the 08:00 Central cutoff is reached,
it reports review/deadline and does not bypass the data gate. No model deployment.

## Monitor and stopping point

`./venv/bin/python scripts/watch_v6_incubator.py --follow` shows the main run.
Its error list/main completed count will retain earlier failures until the new
supervisor starts; inspect retry receipts separately for recovery progress.
Ctrl-C closes only the viewer. Exact selected pointers: [State](docs/CURRENT_STATE.md).
Main status: `incubator/continual-v6/r3/latest-run.json`; focus state under
`nn_meta/validation/v6-focus-20260930/`. Compare receipts with live service health.

Four retry-selection/binding/resume/resource tests passed; real source/snapshot
preflight and unit verification passed. Service launch and fresh UCO progress
were observed. UCO recovery is verified; remaining retries and automatic supervisor resume
remain incomplete/unproven.
[Review](docs/reviews/2026-09-30-v6-dedicated-compute.md).

## Paused work and constraints

The 15:01 handover checkpointed V7 and migration; V6 began 15:03:52. Migration
retained 254,561 files/200.127 GB logical; quote capture retained 40,992 windows.
V7 successor controllers resume after verified V6 completion; original discovery
and quote units do not restart. Rejected evaluated candidates retain incumbent.
Keep MRHA mounted; broker order management/monitoring and remote experts remain.
Preserve unrelated dirty/untracked work. V7-3 and full-incubator proof stay open.
