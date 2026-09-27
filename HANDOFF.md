# Handoff — September 27, 2026 — twelve-worker download selected

## Focus and stopping point

The user requested twelve workers after the successful six/eight-worker trials.
The versioned capture service is now running **12 workers × 32 I/O threads**,
a ceiling of 384 concurrent requests. Research remains in Phase 7, gate 7-3.
The download continues; no readiness or completion gate was advanced.

## Changes and evidence

- New v7 runner/launcher and policy extend the worker ceiling. Prior source-bound
  producers, exact demand, packing, memory guard and storage routing are preserved.
- The eight-worker service drained with no pending writes/reservations. All
  38,646 completed packs were verified and reused by the new runner.
- Live throughput/resource/temperature observations support the selected setting;
  [review and dated receipt](docs/reviews/2026-09-27-v7-twelve-worker-capture.md).
- RAM remains 14 GiB, swap off, CPU quota 800%, low priority, and 10 GB reserves on
  both local and MRHA disks. TasksMax is 464 for the larger thread pool.
- 26 focused tests and shell/whitespace checks passed. The previous full suite
  passed 2,514 tests plus 18 subtests (one skipped), before this ceiling extension.
- Documentation ownership/consolidation and all other workstreams are unchanged.

## Next session

1. Read TODO, then [CURRENT_STATE](docs/CURRENT_STATE.md) for selected pointers.
2. Inspect the v7 capture progress receipt for status. Do not start a duplicate or
   use an older launcher. Short-window rates change with data density and cannot
   establish a dependable campaign ETA.
3. Continue selected 7-3 work from completed preparation, preserving the partial
   7-4 ledger. No assembly or training campaign was started here.
4. Observe Monday's prospective Alpaca fills; preserve the activated account.
   Incubator source/outcome work and the October 2 provider decision remain the
   separate TODO obligations. FA continues on its existing collection schedules.

## Constraints

The new source-bound v7 producer is frozen too. Use its launcher to resume or
reduce concurrency after a clean drain; older runners cannot admit new v7 packs.
The 14 GiB guard may reduce effective concurrency on denser ranges. Twelve workers
share an 800% CPU quota; they are not twelve dedicated physical cores.
Preserve unrelated dirty/untracked work. All runtime findings are dated snapshots.
