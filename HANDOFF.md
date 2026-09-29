# Handoff — September 29, 2026 — V6 worker capacity

## Focus and changes

User requested additional V6 workers. Installed service now passes
`--autosize-workers` to `scripts/v6_continual_resume_v3.py`: shared autosizing,
4500 MiB/worker, 8192 MiB host reserve, maximum four data workers. Current sizing
returned three. CPU quota 400%, MemoryHigh/Max 19/20 GiB, no swap; training remains
two threads. Existing timer and market-window guards remain in force.
[Evidence](docs/reviews/2026-09-29-v6-worker-sizing.md).

All 74 frozen source hashes match. Saved contracts, September 28 snapshot,
inherited r1/r2 seals and r3 checkpoints remain unchanged. Fifteen focused tests,
argument/snapshot checks and systemd verification passed. The installed settings
were read back; increased-worker execution and speedup have not been measured.

## Stopping point

Around 08:05 Central, the prior two-worker invocation remained active while
queued tasks returned calendar-deadline failures after the 08:00 cutoff.
93/449 symbols complete; all 17 original failure cases had completed earlier.
No new training/freeze exists. No restart during the paper-session reserve window.
The next regular after-close timer is 15:45 Central; inspect service-exit together
with latest-run because progress can remain stale after an external stop.
Selected config/root remain `deploy/incubator-continual-v6-r3.json` and
`incubator/continual-v6/r3/`. [Exact state](docs/CURRENT_STATE.md).

V7 gate 7-3 remains selected and open; no V7 changes this turn. Planner is
checkpointed at 582/591 securities. Discovery stopped at its 20-GB generated-store
cap; parent progress was stale. Two security workers failed empty quote indexes.
[Overnight evidence](docs/reviews/2026-09-29-overnight-checkpoints.md).

## Next actions

1. Observe V6 terminal receipt and next allowed autosized run; measure concurrency,
   throughput and memory. Complete remaining catch-up, 40 members and evaluation.
   Candidate acceptance never deploys it. Review combined memory if V7 resumes.
2. Resume V7 planner's nine remaining securities. Repair discovery storage,
   empty-index cases and terminal reporting before checkpointed resumption.
3. Capture only actual missing held/exit/roll inputs, reconcile references,
   provider failures and storage; close 7-3 only against full evidence.
4. Keep first paper-fill observation, October 2 provider decision and FA schedules.

## Constraints

Preserve source hashes, partial ledgers, existing captures and unrelated dirty
work. Gates 7-1/7-2, entry capture and known reference adjudications stay complete.
Keep later execution, assembly and training gates separate.
