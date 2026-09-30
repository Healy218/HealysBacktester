# Handoff — September 30, 2026 — scheduled dedicated V6 compute

## Selected direction

At **15:01 Central September 30**, pause competing local batch jobs and dedicate
compute to finishing V6 incubator. After successful training/evaluation and a
verified research candidate freeze, automatically restore paused jobs with as
much supported concurrency as possible. This supersedes the 15:45 V6 start and
uninterrupted V7 continuation for this interval. [TODO](TODO.md) owns the tasks.

## Installed scheduled handover

- `healys-v6-focus-20260930.timer` → `.service`, one-time 15:01 Central.
  Installed and verified enabled/active/waiting; focus service still inactive.
- `scripts/v6_focus_20260930.py --auto-restore` verifies clock/market close,
  original V6 source bindings, completed-entry evidence and pinned snapshot.
- Pause local V7 supervisors then capture/discovery/migration; temporarily
  disable competing FA/transfer/backup/V6 data/context/scanner/continual timers.
  Preserve basic broker order management, monitoring, dashboard and hourly reports.
- Capture/migration drain checkpoints before V6 starts; allow up to 15 minutes.
  Prior timer states and transient unit definitions are saved for restoration.
- Exact scope and evidence: [review](docs/reviews/2026-09-30-v6-dedicated-compute.md).

## V6 target and allocation

Pinned catch-up: September 28, r3; **325/449** symbol seals were complete at
preparation. Preserve the unfinished date, snapshot and partial feature/label
seals. No training/freeze completion is claimed by preparation.

Dedicated service: 25/26-GiB high/max, no swap, no CPU quota. Shared autosizer:
4500 MiB per data worker, 4096 MiB host reserve, parent allowance. Four workers
selected before pause; possibly five after competitors drain. Training uses all
available CPU threads (16 observed). The frozen producer still applies its
next-session opening-minus-30-minute deadline (08:00 Central).

Automatic restoration requires successful producer exit plus verified candidate
files after evaluation. A rejected evaluated candidate is still a finished run;
it cannot replace the accepted model. Failure/incomplete/deadline leaves the
other jobs paused for investigation. No automatic deployment.

## Restoration and evidence

State: `nn_meta/validation/v6-focus-20260930/`: `progress.json`, `pause-plan.json`,
`units/`, `paused-services.json`, `incubator-result.json`, `restored-services.json`,
`service-exit.json`. Read the exact systemd journal alongside these receipts.
V6 actual stages remain in `incubator/continual-v6/r3/latest-run.json`.

Restore prior timer states and V7 successor supervisors/migration. Do not restart
initial quote/discovery units: successors reuse retained checkpoints with fresh
sealed quote indexes. `scripts/resume_v7_compute_20260930.py` binds the resource
revision separately: up to two discovery, four capture and one serial replay
worker, 8/6-GiB service limits, CPU quotas removed, autosizing retained.
Original source producers and artifact identities are unchanged.

Fifteen focused tests, real-data source/snapshot/entry preflight and unit syntax
checks passed. Scheduling/installation is separate from observed execution;
verify the selected timer and post-15:01 receipts before claiming the switch ran.
[Exact pointers](docs/CURRENT_STATE.md#september-30-1501-dedicated-v6-handover--scheduled).

V7 gate 7-3 remains open; all completed entry/reference/capture/replay evidence
remains valid. Keep MRHA mounted. Preserve unrelated dirty/untracked work.
October 2 provider decision remains separate. Remote experts are unchanged.
