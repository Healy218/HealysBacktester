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

## Requested 15:05 terminal report

The user requested a one-time post-handover report in the current terminal.
Installed/enabled `healys-v6-handover-update-20260930.timer` has the verified next
event September 30 15:05 Central. Destination thread
`01a0f343-c76a-7842-915b-0c111e8e2e28` was verified through local thread metadata
without sending an early message. The older hourly updater is unchanged.

The isolated dispatcher records host services/journals in
`logs/v6-handover-update-20260930/runtime.json` and queues a read-only request
covering migration totals, V7 retained progress and actual V6 startup. It uses
one deterministic request identity, waits for an idle thread and retries busy
or failed transport every 30 seconds. It does not interrupt a user turn or
mutate research/trading jobs. Its 64-MiB response allowance accommodates resumed
conversation history above the previous updater's 1-MiB client limit.
Four targeted tests passed (read-only verification, target mismatch rejection,
busy-thread deduplication and resume auto-consumption); unit verification passed.
Timer installation is confirmed; report delivery remains a future runtime event.

## 16:33 worker increase — measured restart

The user requested more workers after observing memory use below one-third of
the service limit. Before restart, the four active worker processes used roughly
0.75–0.8 GiB RSS each; aggregate cgroup peak was 8,261,242,880 bytes (7.69 GiB),
with no memory high/max/OOM events. Much of cgroup memory was file cache.
This supports a cautious worker-budget reduction, not a maximum-memory guarantee.

Versioned operational wrapper `scripts/v6_focus_workers_20260930.py` lowers the
data-worker allowance from 4500 to 3584 MiB, retaining 4096 MiB host reserve,
2048 MiB parent allowance and the 26-GiB hard service limit. Shared autosizing
selected **five workers** from 25,064 MiB available at the actual restart; its
service-budget ceiling is six. Five processes were independently observed.

At **16:33:47 Central** the old pool was stopped and resumed from the same pinned
September 28 snapshot. All **357 completed symbol seals** remained byte-identical;
partial feature/label seals remain reusable. The old service's SIGTERM exit and
semaphore-cleanup warning correspond to this deliberate stop, not a new provider
failure. Prior status/exit receipts are archived in
`nn_meta/validation/v6-focus-20260930/worker-revisions/r1/` (`before.json`,
`stopped-run.json`, `prior-service-exit.json`, `restart.json`).

Installed drop-in: `healys-v6-focus-20260930.service.d/20-workers.conf` selects
the new wrapper with `--worker-mib 3584 --auto-restore`. Frozen producer files,
scientific contracts, model family, pinned inputs and deadlines are unchanged.
Data completion still proceeds automatically through all 40 training members,
evaluation and verified candidate freeze, then restores the paused jobs.

Eleven focused resource/checkpoint/handover tests passed; real source/snapshot
preflight, prior-symbol hash comparison, installed unit verification and live
five-process readback passed. This establishes increased concurrency and retained
checkpoints, not a measured throughput gain or full-incubator completion.

## Read-only terminal viewer — September 30, 16:47 Central

User requested the CLI progress bar follow the incubator. Opened a separate
Konsole with `./venv/bin/python scripts/watch_v6_incubator.py --follow`; the
viewer reads r3 receipts and the dedicated service every five seconds. It shows
separate symbol and training-member progress, then evaluation/final freeze.
It treats a stopped service's saved running receipt as stopped, leaves training
pending after data completion until the producer reports it started, and does
not infer an ETA or a successful candidate from checkpoint presence.

Four focused tests passed. Host readback at 16:47:44 confirmed viewer PID 1701646,
362/449 symbols, five selected workers, training pending and 3.98/26 GiB service
memory including cache. No scientific producer or running job was changed.

## Concurrent provider-error recovery — September 30, 18:54 Central

User requested retries while the main pass continues. At 18:51 the main receipt
reported 403/449 symbols and ten terminal HTTP 502 failures. The frozen tick
client already makes five short transport attempts. Later retries use a separate
operational helper, `scripts/v6_retry_failed_20260930.py`, without changing any
source-bound scientific producer. Its unit started at 18:53:58, main PID 1734139;
UCO emitted new progress at 18:54:07. No symbol recovery is claimed yet.

Eligibility is a terminal failed future in the current main invocation, with
exact HTTP 502 error and matching frozen universe. Failed futures will not be
submitted again by the existing main pass. The helper binds start time, run
path/date, contract, snapshot and its own source, invokes the existing builder
on the failed symbol only, and never writes the main status. Symbol feature,
label, market, history and completion paths are separate from active symbols.
A helper lock prevents duplicate retry controllers; no second full-run launcher
is admitted while the main pass holds the root lock.

One child is admitted by shared autosizing, explicit available-memory checks,
and the planned main-plus-retry worker budget inside the 26-GiB allocation.
The separate retry unit is limited to 3584 MiB with no swap. Each failed symbol
gets at most three later attempts, with a two-minute delay before retrying it.
The original October 1 08:00 Central cutoff remains effective.

Main failures remain in its in-memory list even after side recovery. Once the
main service exits, all failed symbols must have verified completion seals and
all main errors must match HTTP 502 before a fresh focus-service start is
requested. Prior run/focus/exit receipts are archived in the retry directory.
The new supervisor verifies/reuses seals, then follows unchanged training,
evaluation, freeze and restoration behavior. Unresolved failures stay visible.

Four focused retry selection, invocation binding, resume gate and memory tests
passed. Real frozen-source/snapshot preflight and systemd unit verification
passed. Persistent service startup and live symbol activity are demonstrated;
completed retries and automatic main-service resumption are not yet demonstrated.

At 18:59:34 the UCO retry completed successfully; its completion payload was
independently verified. ULTA then started. Remaining recovery and automatic
supervisor resumption are still pending.

## Transport resume — September 30, 20:48 Central

User reported 35 missing symbols in the stopped CLI. The main service had
failed at 19:15:23, with 414 successes and 35 transport/provider failures.
The side helper subsequently recovered all ten HTTP 502 symbols by 20:13:48.
Its intentionally narrow selector did not admit five `Massive tick transport
failed` and twenty `MASSIVE transport failed` errors, so it exited needs_review
without restarting the main service. The old main count omitted side recoveries.

Verified all **424** completion payloads and the frozen source/snapshot binding.
Archived main run/focus/exit and previous worker-restart receipts plus the 424
seal hashes under `nn_meta/validation/v6-focus-20260930/transport-resume-r1/`.
Host check confirmed main failed and helper inactive before requesting the
existing focus service start. It resumed at **20:47:50**, selecting five workers.
At **20:48:12**, fresh WFC/WMT/WPM/WULF/WYNN symbol updates were observed, the
main count was 424/449, no new errors and training pending. All prior 424 symbol
seals remained unchanged. No producer or scientific contract changed.

The unchanged supervisor now retries the remaining 25 symbols, then proceeds to
training/evaluation/freeze if data checks pass. The previous side helper remains
finished and bound to its old invocation. Full completion remains unproven.
