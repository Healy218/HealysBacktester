# Handoff — September 29, 2026 — MRHA migration in progress

## Selected task

User requested moving as much stock/ticker data to MRHA as safely possible.
The verified raw-data migration is started, not complete. V6/V7 continue;
gate **7-3 remains selected/open**. [Migration review](docs/reviews/2026-09-29-mrha-payload-migration.md)
and [measured observations](docs/reviews/2026-09-29-mrha-payload-migration.json).

## Migration runtime and frozen scope

- Service: `healys-v7-mrha-migration-v2-20260929.service`.
- State: `nn_meta/validation/v7-mrha-payload-migration-20260929-r1/`:
  `plan.json`, `files.sqlite3`, `progress.json`, `migration.jsonl`, `consumer-v2.json`.
- Scope: 504,516 completed V7 stock/option payload paths, 229.38 GB logical;
  204.49 GB unique content before filesystem overhead. Not physical-savings promises.
- Destination: `/run/media/healy/MRHA/HealysBacktester/sealed-v7-payloads-20260929/`;
  verified drive UUID `62C9-C390`, external 20-GiB reserve.
- Keeps local directories/receipts and atomically replaces only verified payloads
  with file links. External catalog/journal/RESTORE.txt preserve restore details.
- Three SQLite-sidecar cases stay local; four existing external links preserved.
  V6 working data, models, features, indexes and writable replay databases stay local.
  Steam untouched. Do not reset capture quota accounting after offload.
- Nice 19, idle I/O, CPU 100%, 768-MiB/1-GiB memory high/max, no swap.
  Process entire finite manifest unless capacity/evidence checks stop it.

## Recovery and validation

Original mover safely stopped at seven files: retiring a hardlink alias changed
another alias's ctime. v2 permits only matching-inode/size/mtime changes explained
by an already migrated verified alias; source bytes still fully rehashed.
Original producer/manifest unchanged; v2 revision explicitly bound. Do not edit
bound consumers in place. 13 tests pass, including hardlink recovery and corruption
rejection. First three real external copies passed checksum/gzip readback.
Read actual progress/journal and exact service before inferring later completion.

## V6/V7 continuation

V6 remains on its pinned September 28 catch-up, from 17:31 Central; latest counts
are in `incubator/continual-v6/r3/latest-run.json`. Training has not started in the
last observation. Calendar cutoff remains; do not blindly restart an active run.
V7 frozen-frontier capture completed **109,825/109,825** windows at 19:30 Central,
4,577 packs, zero remaining batch failures; combined evening r0 index sealed.
Supervisor `healys-v7-evening-continuation-20260929.service` advanced to replay;
`v7-evening-continuation-20260929-r0/selected-replay.json` owns exact inputs/output.
Larger replay remains incomplete. Supervisor then resumes original discovery if
budget remains. Selected reference epoch and approved 10,835-pair policy unchanged.
[Evening continuation evidence](docs/reviews/2026-09-29-v7-evening-continuation.md).

## Next actions

1. Observe migration progress/terminal receipt; verify external reads and actual
   internal free-space change. Resume with v2 only after inspecting any failure.
2. Observe V6 and V7 coexistence, exit receipts and further actual requests; full
   capture/replay/training gates are not closed by this move.
3. Observe next-session paper risk, especially AXP; retain existing fresh-quote
   policy. Preserve October 2 provider decision and FA schedules.

[CURRENT_STATE](docs/CURRENT_STATE.md) owns selected runtime pointers. Keep MRHA
connected. Preserve unrelated dirty work, all frozen sources and prior receipts.
