# V7 compression I/O repair — October 2, 2026

The user observed low CPU use after parallel compression was enabled. A live
five-second sample confirmed an HDD writeback bottleneck: MRHA was 100% busy,
with 20 requests in flight, about 12.3 MiB/s writes and 1.05 MiB/s reads. The
archive used 4.80 CPU cores. Compressor output threads blocked in
`balance_dirty_pages_ratelimited`; full I/O pressure averaged about 40% over
ten seconds. Memory high/max/OOM counters were all zero. USB negotiated UAS at
5 Gbit/s. [Measured diagnosis](2026-10-02-v7-cold-archive-io-before.json).

Concurrent compressed writes and repeated full-verification reads on one HDD
were starving compression. Raising the worker count alone did not fix it.
Parallel-v1 was stopped without removing any source or verified archive.

## Selected I/O consumer

`scripts/archive_v7_cold_staged.py` is separately source/plan-bound by
`consumer-staged-v2.json`; original plan and archivers remain unchanged.
The existing service now uses `scripts/start_v7_cold_archive_staged.sh`.

Local shards compress in parallel to a bounded SSD staging directory under
`nn_meta/validation/v7-cold-archive-20261002-r0/staging/`. Capacity is at most
8 GiB, with at least 10 GiB internal free space guarded during compression.
Reservations bound concurrent staging; oversized shards defer to a later serial
direct-stream phase. Per-shard staging estimates are checked against actual
output size, and an excess causes safe deferral. No source deletion occurs here.

A single publication lock covers external copy, fsync, external SHA256 comparison,
full source comparison, member census and final publication. SSD compressors may
continue while one HDD transfer/verification runs. Successful staging files are
removed afterward. Interrupted staging is rebuildable; verified external shards
are rehashed and reused. External-source shards also run serially.

Compression remains lossless zstd-22. All-shard verification still precedes any
authorized V7-only reclamation. Memory high/max remains 20/22 GiB, no swap;
workers use the shared 1.5-GiB/worker and 6-GiB host-reserve autosizer.

Thirteen focused tests passed, including staged archive fidelity/retirement,
external-copy corruption rejection, source-mutation rejection and capacity
deferral, plus the prior corruption/link/recovery/parallel-admission checks.
Shell syntax and host systemd validation passed. No scientific reruns.

Service started **23:30:07 Central**, selecting **13** workers. Startup first
rehashes prior verified archives serially; low CPU during that finite stage is
expected. The progress counter during a restart counts rechecked/finished work
in that pass; existing receipts are not deleted or scientific progress reset.
`COMPLETE.json` remains the only full archival/reclamation completion receipt.

## Measured active compression — 23:37:54–23:38:24 Central

Four consecutive ten-second samples used **12.216, 11.990, 12.153 and 12.400
CPU cores**, about 75–78% of the host's 16 logical CPUs. MRHA busy time was
34%, 62%, 27% and 19%, rather than continuous saturation. Service memory ranged
from 9.7 to 12.9 GiB; memory high/max/OOM counters remained zero. Seven newly
staged archives had completed full external verification by the end of the
window. Roughly 0.97 GB of actual staging was present (reservation about 3.7 GB).
[Samples and actual external extraction proof](2026-10-02-v7-cold-archive-io-after.json).

This demonstrates reduced HDD contention and increased CPU utilization in the
observed local-catalog phase. It is not a whole-campaign ETA or a guarantee of
constant CPU load: later large/direct/external-source and verification phases
have different I/O limits. All source reclamation still waits for all archives.
