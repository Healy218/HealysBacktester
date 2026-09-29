# Handoff — September 29, 2026 — overnight checkpoints, session cleared

## Focus and stopping point

User requested a notes refresh before clearing the session. This turn changed
only documentation; no jobs were restarted or limits changed. V6's recorded
errors are resolved and catch-up continues. V7-3 remains selected and open.
[Overnight evidence](docs/reviews/2026-09-29-overnight-checkpoints.md).

## V6 status and selected runtime

At 07:33 Central: 90/449 symbols complete, zero recorded errors. All 17 formerly
failing symbols now have full completion receipts. Training has not started;
no new model freeze exists. Existing accepted model and paper runtime stay intact.
Prior repair: stable duplicate-proposal identities, bounded transient tick retries,
18 focused tests and exact feature parity; do not rework the original fixes.

Config `deploy/incubator-continual-v6-r3.json`; root `incubator/continual-v6/r3/`.
Service `healys-v6-continual.service` was executing at the preceding check. Read
latest-run, per-symbol seals and service-exit together. Two autosized workers,
CPU 200%, 11/12-GiB memory limits, no swap. Existing deadline is next open minus
30 minutes; preserve market-hours guards and pinned unfinished date/snapshot.
[Repair](docs/reviews/2026-09-28-v6-continual-error-repair.md).

## V7 stopped checkpoints

- Planner: 582/591 securities, 789,797,718 original proposals reconciled.
  It checkpointed at its eight-hour deadline, 05:13 Central; nine securities remain.
- Discovery stopped at 05:08:48 with `Execution working-store allocation reached`
  (20-GB generated-state cap). Journal confirms exit-code failure; not OOM.
  About 90 GB local free. Parent progress still says running, but the job is stopped.
- Per-wave receipts: 25 discovered, 66 checkpointed, two interrupted/stale running;
  30,462,620 horizon/target dispositions and 112,112 summed pending requests.
  Discovery completion is not label completion or full execution coverage.
- Two other workers failed quote-index construction: `BBG000BCQ6J8` and
  `BBG000BF8TF5`, `No completed capture packs for selected security`.
  Diagnose frozen selections/demand; do not assume entry capture must be repeated.

## Next actions

1. Check V6's latest receipts and calendar cutoff; preserve successes and finish
   the remaining initial catch-up, 40 training members and evaluation/freeze.
   Full overnight latency is not proven; candidate acceptance never deploys it.
2. Resume V7 queue's remaining nine securities from existing checkpoints. Repair
   discovery storage handling, empty-index cases and truthful terminal reporting
   before resuming discovery. Version bound source changes and retain partial data.
3. Capture only actual missing inputs from stopped snapshots; bind new quote/
   reference epochs, replay and reconcile held exclusions/storage/provider failures.
   Close 7-3 only against full evidence; keep later execution/assembly gates separate.
4. Keep paper-fill observation, October 2 provider decision and FA schedules.

## Pointers and constraints

[CURRENT_STATE](docs/CURRENT_STATE.md) owns exact services/inputs. Queue root:
`nn_meta/validation/v7-full-execution-plan-20260928/`; discovery root:
`nn_meta/validation/v7-execution-campaign-20260928-r1/`. Quote index ends `r4`;
approved exclusions remain 10,831 pairs. Gates 7-1/7-2, entry capture, reviewed
rename corrections and known exception adjudication remain complete.
Preserve source hashes, audited stopped pilots, r1/r2 V6 seals and unrelated dirty work.
