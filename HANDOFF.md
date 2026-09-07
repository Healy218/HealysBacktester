# Handoff — four parallel tick-store workers active

September 6 local / September 7 UTC, 2026. User requested real symbol-process
parallelism for the remaining tick stores, accounting for current system use.

## Active home v6 campaign

Campaign root: `nn_meta/expanded_inputs/v6-local-20260906/`.
Inventory complete 453/453. Verified old serial supervisor PID 10394/start 18439
was stopped with SIGINT before replacement. 181 completed stores were preserved;
all 181 manifest hashes matched after launch. Existing raw captures are reused
through unchanged pinned validation. No causal source, input, policy, or model
contract changes were made.

New supervisor PID **1432456**, launched 2026-09-07 04:16:39 UTC:
`scripts.run_v6_parallel_freeze --symbol-workers 4 --workers 16 --run` with
inventory/policy/output paths recorded in campaign `resume.json`. Original resume
is preserved as `resume-before-parallel.json`. Durable log:
`parallel-freeze-supervisor-resume-20260907T041639Z.log`.

Four real symbol subprocesses were observed concurrently. GME/GOLD completed
and advanced to GWW/GS while GOOG/GOOGL materialized. Latest measured workers
used 1.91 GiB aggregate RSS; 22.8 GiB system MemAvailable. This is an observation,
not a peak estimate. Host has 8 physical cores /16 logical CPUs /about 30.5 GiB RAM.
Launch sampled 24.06 GiB available and 11.81 idle logical CPUs in the usable set.
Budget: four workers × 3 GiB = 12 GiB, plus 4 GiB available-memory reserve.
Two physical cores, including SMT siblings (CPUs 1,4,9,12), are excluded from
heavy worker affinity. Remaining core groups are partitioned among the workers.
Up to 16 network threads per symbol (64 total); numerical inner threads limited
 to 1. RAM estimate is not a hard allocation: scheduler checks every 2 seconds,
stops children below 4 GiB available, and delays additional starts below 7 GiB.

All 453 stores must verify before sealing; previously completed stores verify
last so remaining downloads start immediately. Full freeze then launches with
fresh CPU/RAM sizing: max 4 workers,5 GiB estimate each,4 GiB reserve, two physical
cores excluded. Build/training remain unlaunched. Prepare their launchers at
227/453 actual freeze shards, as requested. Do not change pinned causal sources
or this running scheduler: its exact source is saved as
`full-run/parallel/scheduler-source.txt` and checked before completion/resume.
Per-symbol locks plus duplicate-supervisor detection prevent conflicting writes.

Evidence: `parallel-transition-checkpoint.json`, `parallel-live-verification.json`,
`full-run/parallel/{status,resource-plan}.json`, per-symbol JSON and logs.
30-minute `healys-v6-progress.timer` remains enabled; watcher now reports live
symbol workers and the resource plan. Check host processes, not sandbox-only ps.
Full main regression: **1,444 tests +18 subtests passed**; 18 focused tests passed.

## Production operations (separate host; last verified state retained)

September 6, 2026. User requested operational fixes and both experimental
partial-bar view + closed-bar recap five minutes before the exchange close.
Production compatibility branch ops/server-alert-readiness-20260906 is now at
a315034 (initial patch 6d83a67), separately from research main. Do not pull
research main onto old models. Home v6 causal source/data are unchanged.

Deployment and remaining checks:
docs/reviews/2026-09-06-production-ops-deployment.md.
Full ops regression 545 tests +18 subtests; follow-up 10 focused tests passed.
Freshness/final-close/calendar/stream/retry fixes and separate EOD minute cron
are active. Models/specs/thresholds retained; bundle and alert-state hash checks
passed. Actual stream/timing/delivery acceptance awaits the next session.
Calendar verified September 7 closed, first panel September 8 at 15:55 ET.
Preview prewarms at 15:46, snapshot target 15:54; incomplete coverage is labeled.

Server v5 refresh remains RUNNING, not complete: supervisor 394442, initial
worker 394443, eight download workers, sampled 1 GiB available-memory stop guard.
Exact root logs/ops/v5-refresh-20260906T222750Z/ on server. At last check,
5,000/208,684 remaining downloads done, ~76/s, 5.6 GiB available. Surface follows
successful download/compaction automatically. Check result.json and date coverage.
Server stock stream restarted as PID 394370. Rollback snapshot:
logs/ops/alert-fix-20260906T222537Z/ on server. No test trading alert was sent.


See archived handoff for older campaign chronology and source contract details.
