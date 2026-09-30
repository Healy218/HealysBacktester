# Handoff — September 29, 2026 — V7 resumed without overall cutoff

## User direction and result

User requested restarting V7, then explicitly removed the time limit so work can
finish while they sleep. The selected pending replay is running again; automatic
continuation has no overall cutoff. Gate **7-3 remains selected/open**.
[Restart evidence](docs/reviews/2026-09-29-v7-overnight-resume.md),
[dated verification/progress](docs/reviews/2026-09-29-v7-overnight-resume.json).

## V7 selected runtime

- Current worker service: `healys-v7-pending-overnight-20260929.service`, started
  23:28:20 Central. Its initial four-hour pass remains active to avoid interruption.
- No-cutoff successor: `healys-v7-until-complete-20260929.service`; waits for the
  exact current unit, then resumes automatically until all 93 selected securities
  finish. No overall wall-clock cutoff; capacity waits retain checkpoints.
- Supervisor state: `nn_meta/validation/v7-until-complete-20260929-r0/`.
- Campaign: `nn_meta/validation/v7-pending-replay-campaign-20260929-20260929T233047Z/`;
  same frozen 21,624,449 horizon-target queue. Read `progress.json` and per-wave
  meters. Aggregate completion counters rebuild each traversal; retained work stays.
- Selected inputs: `v7-evening-continuation-20260929-r0/selected-replay.json`.
  Evening quote index, combined reference epoch and 10,835-pair policy unchanged.
- Preflight: `v7-overnight-resume-20260929-r0/`; eight input anchors/all retained
  wave declarations verified; all 31 wave databases passed quick checks under locks.
- Resumed from 5,021,957 evaluations / 59,278 cohorts / ten completed securities.
  Fresh progress exceeded that baseline. No worker failures reported at observation.
- One autosized worker, CPU 100%, 3/4-GiB high/max, no swap, Nice 15.
  Keep 6-GiB available-memory / 20-GB disk guards. Do not edit bound producers.

## Preserved completed acquisition

All 109,825 frozen-frontier windows completed at 19:30 Central (4,577 packs,
zero remaining failures); evening r0 index sealed. Do not restart that capture.
Prior evening supervisor checkpointed successfully at 22:01 after its replay and
original-discovery budgets. Original discovery is checkpointed, not newly active.
Selected replay completion can reveal more actual input gaps; it does not close
7-3, establish full-universe execution coverage or start V7 training.

## V6 and MRHA migration

V6 continues the pinned September 28 catch-up from 17:31 Central. Current counts:
`incubator/continual-v6/r3/latest-run.json`; training not yet started at observation.
MRHA migration: `healys-v7-mrha-migration-v2-20260929.service`, state
`nn_meta/validation/v7-mrha-payload-migration-20260929-r1/`. It remains active.
Target 229.38 GB logical sealed raw data; original paths/receipts preserved by
verified file links. Leave V6 working stores, features, models, indexes and writable
replay databases local. Steam untouched. Keep MRHA UUID 62C9-C390 connected.
[Migration/recovery procedure](docs/reviews/2026-09-29-mrha-payload-migration.md).

## Next observations

1. Inspect the no-cutoff supervisor and campaign for completion, capacity waits or
   real errors. Do not stop merely because a checkpoint slice elapsed.
2. Reconcile further actual requests after the frozen replay finishes; retain
   all gate boundaries and evidence. No promised overnight finish time.
3. Observe migration completion/space, V6 progress and next-session paper risk,
   especially AXP. Preserve October 2 provider decision and FA schedules.

[CURRENT_STATE](docs/CURRENT_STATE.md) owns exact pointers. Preserve unrelated
working changes, original checkpoints and all frozen producer versions.
