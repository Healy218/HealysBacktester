# Handoff — October 2, 2026 — V7 paused for optimization

## Current user direction

User explicitly requested pausing V7 and rethinking performance. Stop is complete.
Do not resume discovery or frontier until a new user instruction authorizes it.
Selected task is 7-3.performance: bounded profiling/optimization design; gate
7-3 remains open and completed preparation remains complete.
[Inspection and proposed work](docs/reviews/2026-10-02-v7-performance-pause.md).

## Actual stopping point

At 09:59:06 Central, healys-v7-required-discovery-20260930.service stopped.
At 09:59:13, healys-v7-required-frontier-20260930.service stopped.
Supervisor receipts stopped; child campaigns checkpointed with no failures.
Both cgroups gone, campaign/supervisor/current-replay locks released. Frozen
sources, wave declarations and committed cohort checkpoints remain preserved.
A last uncommitted interrupted cohort may need replay on eventual resume.
Evidence: nn_meta/validation/v7-performance-pause-20261002-r0/pause.json.
At 10:02: 1,534,496 discovery cohorts, 143,947,955 horizon-target assessments;
60 finished waves plus seven verified empty cases and 133 partial waves. Current
replay 47/93 finished, 172,783 cohorts / 14,520,464 assessments. No counters reset
on disk to manufacture progress. Assessments include pending-input outcomes.

## Performance findings and next work

Verified total original plan: 1,641,934,235 horizon-target assessments. All 60
finished wave totals match their per-job denominators. Rough overnight matched
throughput 26.79 million assessments in ten hours; unchanged extrapolation about
23 days remaining for original discovery only. This is not a completion promise.

Code/EXPLAIN identified repeated five-minute initialization, ordered full-source
traversal to skip completed cohorts, replay fetch-before-skip, grouped full-table
progress scans, per-cohort durable commits and bounded quote caches. Existing
prefix sharing already operates. Relative time costs remain unprofiled.

Benchmark small/large/I/O-heavy fixed cohorts in a NEW bounded validation copy.
Profile phases, then optimize the dominant costs in a new bound revision. Likely
candidates: persistent workers with durable checkpoints, indexed resume, earlier
replay skipping and transactional counters. Prove output/membership/pending-input
and restart parity before measuring scaling or requesting broad resume.
Do not rewrite old source bindings, weaken integrity or replay the full campaign.

## Other operations

V6 paper and incubator were not stopped. Paper scanner reliability remains open;
inspect actual scanner/monitor and independent broker receipts. Incubator through
October 1 remains frozen and retained, with no automatic deployment authorized.
Hourly watcher focuses on paper and cumulative V7 work; V7 pause is intentional.
Completed storage/idle successful incubator should remain absent from routine
reports. Provider keep/cancel recommendation is still a separate TODO obligation.
[Current pointers](docs/CURRENT_STATE.md) · [Tasks](TODO.md).
