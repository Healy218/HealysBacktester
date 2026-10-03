# V7 pause and cold archive — October 2, 2026

User selected pausing V7 for resource constraints, strong lossless compression
to MRHA, verified V7-only local reclamation, and an archive named `v7` with
compressed handoffs/notes and a readable ordered restoration/resumption guide.
This supersedes immediate research continuation; gates 7-1/7-2 stay complete,
7-3 and subsequent gates stay open. No trained V7 model exists.

## Source and destination

At 22:29 Central MRHA UUID `62C9-C390` was mounted at
`/run/media/healy/MRHA`; approximately 472 GiB was free externally and 21 GiB
internally. Host inspection found no V7 Python workers. The two old enabled
V7 catalog/download startup services were disabled and verified disabled.
No research controller was restarted.

The previous raw migration receipt is complete: 504,516 paths,
229,378,057,319 logical bytes, approximately 204.49 GB unique contents. The
external object tree uses about 221 GiB of exFAT allocation. Those original
objects remain readable. Archive includes both external V7 target trees,
all `nn_meta/data_v7`, all prior `nn_meta/validation/v7*` paths, all V7 research
plans and a frozen working-source snapshot. All 504,520 external links observed
point into the two selected external trees; other observed V7 links target
included local validation roots. Links are archived as links, not dereferenced.

Destination: `/run/media/healy/MRHA/v7/`:
`README.md`, `data/*.tar.zst`, `manifests/`, compressed `notes/notes.tar.zst`.
The notes include all current project documents and handoff history, preserving
mixed V6/V7 context. Root `.env`, virtual environment and shared non-V7 datasets
are not included. The source snapshot retains 1,167 source/configuration files,
working bytes and SHA256 manifest, original Git HEAD and requirements.

## Integrity and reclamation

`scripts/archive_v7_cold.py` freezes a finite plan and its own source checksum.
Independent numbered tar/PAX shards use Zstandard `--ultra -22`, with threads
selected by `scripts/lib/autosize.sh` (4 GiB/thread planning reserve, 8 GiB host
reserve). The service has 12/16-GiB memory high/max, no swap, low I/O priority.
Streaming writes go directly to MRHA, preserving 20 GiB external free space.
No SSD-sized staging archive is required.

Each shard must pass stable before/after metadata fingerprints, fsync, SHA256,
GNU tar full source comparison and an independent archive-member census.
Small-file, hardlink and symlink semantics are preserved inside containers.
Restart rechecks completed archive hashes and rebuilds incomplete shards.

Only after **all** shards verify can reclamation start. It rehashes each external
shard and each selected original file before unlinking. Durable per-file intent
and retirement journals support interrupted deletion. Only regular local files
larger than 1 MiB under the frozen V7 validation scope are eligible. Keep small
receipts, symlinks, directory scaffolding, all raw input trees, plans, source,
external originals and non-V7/shared datasets. Retained metadata is intentional;
logical bytes are not a promise of Btrfs free-space gain.

Nine focused tests passed (including parallel independent-shard and failure-admission tests): actual extraction with hardlink/symlink fidelity,
verified retirement/retry, archive corruption rejection, changed-source rejection,
global verification requirement, external shared-link preservation and restore
helper checksum verification (some cases share a test). Shell syntax and host
systemd service verification passed. No broad scientific reruns were performed.

## Runtime and completion boundary

Selected service: `healys-v7-cold-archive.service` (manual start, not auto-enabled).
Local state: `nn_meta/validation/v7-cold-archive-20261002-r0/`.
`plan.json` owns shard mapping; `progress.json` owns phase/current shard/errors.
`VERIFIED.json` proves all shards passed; `COMPLETE.json` also records completed
selected reclamation. No archival completion or reclaimed-space claim from launch.

The plain [archive README](../reference/V7_COLD_ARCHIVE_README.md) specifies notes,
source/environment, external targets, local inputs/plans, validation/checkpoints,
then verified research resumption. Last research handoff is preserved at
[the pre-archive snapshot](../../handoff-history/HANDOFF-2026-10-02-before-v7-cold-archive.md).
Historical capture HTTP 403 and V6 clock-based memory reservation remain unresolved.
Extra disk space alone does not resolve RAM or provider admission.

## Verified launch observation — 22:52 Central

The corrected frozen plan contains **2,847 shards / 564 source roots**. Service
started 22:49:04 with three autosized compression threads. At 22:52:24 it was
active, five shards were fully verified and shard 00005 was advancing. An actual
file extracted from external shard 00000 matched its saved source SHA256.
No local retirement had begun and no overall completion receipt existed.
[Machine-readable observation](2026-10-02-v7-cold-archive-launch.json).

The first setup attempt caught a path-type error before plan creation or any
source removal. It was repaired, a plan/source-binding regression test added,
and the selected plan generated only after all seven focused tests passed.
Notes initial snapshot: 570 files, 1,381,762 compressed bytes with full source
comparison; it is refreshed after final documentation updates. Read the notes
checksum/current receipt for the refreshed size, not this historical count.

## User-directed maximum supported compression compute

The user requested as much available compute as possible. Initial three-thread
zstd used about 3.73 GiB RSS. A resource-only fast launcher budgets 1.5 GiB per
worker plus 6 GiB host reserve, capped through the shared autosizer/CPU count.
Memory high/max increased to 20/22 GiB, no swap; normal CPU/I/O weight. A first
12-thread single-stream revision preserved completed shards, but small shards
still showed single-core compression. Selected parallel-v1 therefore compresses
independent **local** shards concurrently with one zstd-22 thread each, while
external HDD-source shards stay sequential to avoid seek contention.

The original frozen archive source, plan, level, integrity checks and global
all-shards-before-reclamation rule remain intact. New consumer has its own
source/plan-bound receipt and is saved with the compressed notes runtime files.
Stopped unfinished shards are rebuilt; verified shards are rehashed and reused.
Parallel processing tests cover independent complete archives and stopping new
admission on integrity failure. This is a resource revision, not new V7 evidence.

At **23:12:47 Central**, parallel service was active with 12 admitted shard
workers, 105/2,847 verified shards and 14,684,504,064 bytes of service memory.
Ten compressors were sampled at roughly one CPU core each (others may be in
verification/I/O). No local reclamation had started. These are measured launch
observations, not an ETA or completion claim.
[Compute observation](2026-10-02-v7-cold-archive-compute.json).
