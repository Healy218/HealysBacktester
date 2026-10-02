# Handoff — October 2, 2026 — V6 deadline and V7 optimization

## User direction

V6 broker deadline widened to ten minutes. User authorized the four-step V7
optimization plan: benchmark, optimize measured costs, prove exact/restart parity,
then measure worker scaling. V7 campaign remains paused; no broad resume yet.

## V6 completed deployment

Ten-minute policy installed 10:36:02 Central across scanner allocation, broker
admission and unfilled-source retention. Original signal close remains the clock.
New scanner v11, resilient consumer v2, broker runtime v6 and bridge v5; old files
and manifest preserved. Quote age remains 30 seconds; ladder waits/prices unchanged.
101 focused tests passed. Broker polling succeeded after deployment; observe the
next scheduled scanner for prospective evidence. No manual order submission.
[Change and evidence](docs/reviews/2026-10-02-v6-ten-minute-window.md).

## V7 in-progress work

Both controllers intentionally stopped at 09:59, checkpoints retained. Retained
original discovery 1,534,496 cohorts / 143,947,955 assessed horizon-targets;
67 terminal securities including seven empty cases, 133 partial. Replay epoch
00001 is separate: 47/93 complete, 14,520,464 / 20,015,688 assessments.
[Pause evidence](docs/reviews/2026-10-02-v7-performance-pause.md).

Bounded validation root: nn_meta/validation/v7-performance-20261002-r0.
Three copied checkpoints and next-40-cohort baselines profiled: small, long
completed prefix and large database. Grouped progress scans cost ~6 of 17.6s in
the large-database baseline. Other samples spend substantial time in immutable
quote reads, verification and record copies. Timings are profiled short samples,
not overall speedup or completion estimates.

New uncommitted performance revision under development: transactional summary
counters and cursor, eight-cohort durable batches, indexed quote-window slicing,
early replay skip. Initial small sample succeeds; exact comparison, larger samples,
restart/gap tests, longer benchmarks and resource scaling are still required.
Never edit original campaign bindings or checkpoints to adopt changed sources.

## Operational boundaries

V6 model/features and selected scientific scope unchanged. Watcher continues here,
reporting paper/V7; successful idle incubator and completed storage stay omitted.
No automatic paper/live model promotion. Provider recommendation remains a separate
TODO obligation. Preserve unrelated dirty/untracked work.
