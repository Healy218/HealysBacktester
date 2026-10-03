# Handoff — October 2, 2026 — V7 archive I/O repair

## Priority

V7 remains paused for a restorable MRHA/v7 cold archive. User authorized strong
lossless compression and verified V7-only local reclamation, then requested
maximum supported compute and reported low CPU use. Other work stays paused.
[TODO](TODO.md), [I/O review](docs/reviews/2026-10-02-v7-cold-archive-io.md).

## Diagnosis and selected runtime

MRHA was 100% busy with 20 in-flight requests, about 12.3 MiB/s writes and
1.05 MiB/s reads. Archive used 4.8 CPU cores; zstd writer threads blocked on
disk writeback. No memory-cap/OOM events. Parallel direct HDD writes and
verification competed. Preserve original archive plan and already verified shards.

Service: `healys-v7-cold-archive.service`.
Consumer: `scripts/archive_v7_cold_staged.py`; launcher
`scripts/start_v7_cold_archive_staged.sh`; binding `consumer-staged-v2.json`.
State: `nn_meta/validation/v7-cold-archive-20261002-r0/`.
Destination: `/run/media/healy/MRHA/v7/`, mounted UUID `62C9-C390`.

Local shards compress to at most 8 GiB SSD staging, with 10 GiB internal free
space guarded. One serialized MRHA copy/verification pipeline prevents competing
writes. Oversized and external-source shards defer to serial direct streaming.
Compression stays zstd-22; all-shard verification precedes any source reclamation.
Workers use shared autosizing; memory high/max 20/22 GiB, no swap.

## Verification and observation

Thirteen focused tests passed, including staged corruption/source-mutation
rejection, capacity deferral and prior restoration/reclamation/link coverage.
Shell and host service checks passed. Service started 23:30:07 Central with
13 workers. Startup rehashes existing archives before new compression; its
pass counter is not the total persistent receipt count. No scientific progress
or retained archives were reset. At 23:37:54–23:38:24, four ten-second samples
used 12.0–12.4 CPU cores; seven new staged shards verified. MRHA busy time
fell to 19–62%, no memory-cap/OOM events. Live `progress.json` owns later state.
[Measured improvement](docs/reviews/2026-10-02-v7-cold-archive-io-after.json).

## Next actions

1. Inspect the selected service and progress. Active staged compression was
   verified; check for new failures and preserve the selected runtime.
2. Keep MRHA connected. On failure preserve all sources and receipts; resume
   the same bound consumer after diagnosis. Completed archives are reused.
3. Require `VERIFIED.json` and then `COMPLETE.json` for full completion. Only
   then measure free space, close 7-3.archive, refresh compressed notes and commit.
4. Read [restore guide](docs/reference/V7_COLD_ARCHIVE_README.md) before eventual
   user-directed V7 restoration. New archive runtime is saved in compressed notes.
   Last research state remains [the pre-archive handoff](handoff-history/HANDOFF-2026-10-02-before-v7-cold-archive.md).
   Resource admission and Massive historical-option HTTP 403 remain unresolved.

## Preservation

Keep shared/non-V7 inputs, raw inputs, small local receipts, links, plans, source
and MRHA original payloads. No gate closure, retraining, completed recapture,
source relabeling or provider subscription purchase is implied. Preserve all
unrelated dirty/untracked work and keep root `.env` out of archives.
