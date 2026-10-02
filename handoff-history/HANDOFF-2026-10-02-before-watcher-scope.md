# Handoff — October 2, 2026 — V7 discovery concurrency

## Selected task and change

User asked whether discovery compute is optimized and whether more workers can
be used. Replaced the two-worker scheduler with a versioned, memory-aware
scheduler; scientific wave workers, inputs and their seals remain unchanged.
Gate 7-3 remains open. No model/trading changes or fresh capture campaign.

## Deployment and stopping point

Installed October 2 at 08:00:11 Central on existing
`healys-v7-required-discovery-20260930.service`.
New launcher: `scripts/resume_v7_discovery_resources_v2.py`.
New recovery: `scripts/run_v7_execution_recovery_v2.py`.
Admission: `scripts/v7_discovery_resources_v2.py`, using shared autosizer.
Ceiling four overnight; weekdays 07:00–21:00 Central ceiling two with a larger
memory reserve for paper trading/daily V6. Admission recomputed before dispatch;
active slices finish before concurrency declines. Low memory admits no new work.
Service MemoryHigh 12 GiB, MemoryMax 14 GiB, no swap and no CPU quota.
At 08:00:55: two workers active, no errors, no OOMs/throttling. This does not
establish a measured four-worker throughput improvement.

Prior controller stopped with status checkpointed, no errors. All 195 existing
wave declarations verified unchanged across handover. Old controller declaration
preserved; new scheduler has separate declaration-resource-v2.json and identity.
The original progress path remains selected so frontier closure/watcher consumers
continue to see the same campaign. Finished waves and committed cohorts are reused.
Evidence: `nn_meta/validation/v7-discovery-resources-20261002-r0/`.
[Configuration, measurements and limits](docs/reviews/2026-10-02-v7-discovery-resources.md).
14 focused tests passed; actual handover/runtime verification recorded separately.

## Next checks

Inspect admitted_workers, active_securities and per-wave cohort progress, plus
cgroup CPU, memory events and I/O pressure. Compare useful work over time before
claiming that extra workers accelerate discovery. The change raises concurrency,
not the per-wave algorithm's efficiency. Preserve all frozen sources/checkpoints.
Both V7 controllers remain selected. MRHA migration completed October 1; a
stopped migration service is expected. Gate closure still needs full evidence.

## Operating obligations

V6 October 1 daily run completed 20:50:20 Central: 449 symbols, 40 members,
evaluated candidate, 122 payloads verified at the 21:00 check. Diagnostic rejected;
updated freeze retained, no deployment. Daily service/timer remain selected r5.
Paper scanner v10 quote-recovery repair still needs prospective market-hours
verification. Read position-monitor-status.json and scanner receipts independently
of broker polling; after-hours idle success is not market-hours acceptance.
Preserve entry freshness/deadline guards, models, positions and journal history.
Hourly checks continue in this terminal. Provider recommendation due October 2
remains a separate TODO obligation; no cancellation authorized.
[Previous paper handoff](handoff-history/HANDOFF-2026-10-02-before-discovery-resources-v2.md).
[Current pointers](docs/CURRENT_STATE.md) · [Tasks](TODO.md).
