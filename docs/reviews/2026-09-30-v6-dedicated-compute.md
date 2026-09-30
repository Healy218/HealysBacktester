# September 30 — scheduled V6 dedicated compute

## User decision and boundary

At 3:01 p.m. Central September 30, pause competing local batch workloads and
prioritize finishing the V6 incubator. The user also selected automatic resumption
of paused jobs afterward with as much supported compute/concurrency as possible.
This supersedes uninterrupted V7 execution and the 15:45 V6 start for this handover.
It is a scheduling/resource change, not a changed research or admission contract.

The one-time launcher verifies today's captured market close, refuses starts
before 15:01 or on another date, verifies all V6 bound source hashes and the pinned
September 28 snapshot, and retains the completed-entry prerequisite. The normal
market-hours guard is unchanged; only this explicitly requested run starts earlier.

## Scheduled handover

- Unit/timer: `healys-v6-focus-20260930.service` / `.timer`, one-time
  `2026-09-30 15:01:00 America/Chicago`, one-second accuracy.
- Entry point: `scripts/v6_focus_20260930.py --auto-restore`.
- Receipts: `nn_meta/validation/v6-focus-20260930/`. `pause-plan.json` records
  original timer enabled/active states and running services; `units/` preserves
  launch definitions before transient units disappear. `progress.json`,
  `paused-services.json`, `incubator-result.json`, `restored-services.json` and
  `service-exit.json` distinguish scheduling, execution, candidate and restoration.
- Pause local V7 controllers/capture/discovery, MRHA migration, FA jobs/transfers,
  backup, V6 daily data/context/scanning and the ordinary continual timer.
  Disable selected enabled timers temporarily so they cannot compete after reboot.
  Preserve order management, paper monitor, deadman, dashboard and hourly reports.
  Remote live experts, desktop and unrelated applications are outside this local
  batch-compute switch.
- Stop successor controllers before their initial jobs. Let initial capture seal
  its current pack/index and migration finish its atomic move via SIGTERM to the
  main process. Allow up to 15 minutes for drain; timeout leaves explicit evidence
  and refuses to launch V6 over still-running workloads. Thus 15:01 starts the
  handover; actual V6 startup follows checkpoint drain.

## V6 allocation and completion

Continue `incubator/continual-v6/r3/runs/2026-09-28`, preserving 325/449 completed
symbols, partial seals and the original input snapshot. The unchanged producer
checks its scientific source/configuration contracts again at runtime.
Shared autosizing budgets 4500 MiB per worker and 4096 MiB host reserve, plus
2048 MiB parent allowance inside a 26-GiB hard limit (25-GiB high, no swap).
At preparation it selected four data workers; after pausing competitors it may
select five. Training receives all available CPU threads (16 observed), with
no service CPU quota. Existing training plans, if any, retain their saved threads.
No GPU implementation is introduced. The 24-hour invocation budget is shortened
by the unchanged next-session opening-minus-30-minutes cutoff (08:00 Central).

Automatic restoration requires successful producer exit, full candidate-frozen
status and verified candidate files after training/evaluation. A rejected research
candidate can be a completed evaluated run; it does not replace the accepted
model. Failure, incomplete coverage, no matured labels or deadline leaves the
other batch jobs paused for investigation. No model is deployed automatically.

## Resumption

Restore exact prior timer enabled/active states and request saved V7 supervisor
and migration starts. Do not restart initial quote/discovery units: the successor
controllers resume their retained checkpoints and use fresh quote-index paths.
`resume_v7_compute_20260930.py` records a separate resource revision while leaving
original producer hashes, wave databases and bindings unchanged. It admits the
maximum concurrency implemented by the unchanged producers: up to two original
discovery workers (8-GiB service), four quote workers (6-GiB frontier service),
and one sequential replay worker. Autosizing can select fewer. CPU quotas are
removed from the two resumed supervisors. Increasing serial replay concurrency
requires a separately validated controller change and is not claimed here.
Runtime drop-ins live in the user's runtime systemd directory. Ordinary timers
may launch their normal due work after restoration. Read actual services/receipts
before claiming resumed health or higher measured throughput.

## Verification

Fifteen focused tests passed: one-time clock/market-close boundary, selected pause
scope, memory sizing, stop ordering, failure retention, candidate verification
before automatic restore, timer-state restoration, skipping superseded initial
units, supported V7 worker limits and existing required-input controller checks.
Read-only real-data preflight passed all current V6 source/snapshot anchors and
completed-entry evidence. Unit syntax verified. These are preparation checks;
actual handover, full candidate freeze and automatic restoration remain future
runtime outcomes until their receipts exist.

Installed/read back at **14:31 Central September 30**: timer enabled and active/waiting,
next event exactly 15:01 Central; focus service inactive, CPU quota unlimited,
25/26-GiB memory high/max. `schedule.json` records source hashes, resource sizing
and preflight. V7 jobs remain running until the scheduled handover.
