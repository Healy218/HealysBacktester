# Handoff — October 2, 2026 — V7 cold archive

## Priority and scope

User paused V7 because resources are insufficient, requested strong lossless
compression to MRHA, then explicitly authorized reclaiming verified V7-only
internal space. Archive folder must be **MRHA/v7**, with a plain README and
compressed handoffs/notes under **notes/**. This supersedes finishing 7-3 now.
Other work remains paused; no research/training/model deployment is authorized.
[TODO](TODO.md), [ROADMAP](ROADMAP.md), [review](docs/reviews/2026-10-02-v7-cold-archive.md).

## Selected archive and verification

Destination: `/run/media/healy/MRHA/v7/`; UUID `62C9-C390` mounted at
`/run/media/healy/MRHA`. README, data shards, manifests and compressed notes.
Service: `healys-v7-cold-archive.service`; restart manually after inspection.
State: `nn_meta/validation/v7-cold-archive-20261002-r0/`.
`plan.json` maps shards; `progress.json` gives actual phase/error/counters.
Require `VERIFIED.json` for all-shard validation and `COMPLETE.json` for finished
reclamation. Never infer success from service startup, idleness or old counters.

Archive preserves local V7 inputs, all V7 validation roots/checkpoints/plans,
the two existing external raw-payload trees and a frozen working-source snapshot.
Zstd-22 independent local shards use shared autosizing; external reads stay serial.
Parallel consumer: `scripts/archive_v7_cold_parallel.py`; original plan unchanged.
Service memory high/max 20/22 GiB, no swap; six-GiB host sizing reserve.
20-GiB external reserve; direct writes avoid a second full archive on the SSD.
All shards must pass SHA256, source comparison and member census before removal.
Reclaim only verified regular files >1 MiB in selected local V7 validation roots.
Keep raw inputs, small receipts, links, plans, source, shared trees and MRHA originals.

## Observations and changes

22:29 Central: MRHA mounted, about 472 GiB external / 21 GiB internal free.
No V7 workers found. Disabled both old catalog/download auto-start services.
Prior raw migration is complete: 504,516 paths / 229,378,057,319 logical bytes.
Nine focused archive tests, shell syntax and host service validation passed.
23:12 Central: parallel service active since 23:02:06, 12 autosized shard workers;
105/2,847 verified, about 13.7 GiB service memory. Actual external source extraction
matched SHA256. No retirement yet. [Compute receipt](docs/reviews/2026-10-02-v7-cold-archive-compute.json).

## Next actions

1. Inspect the exact service and progress receipt; verify completed shards and
   actual forward progress. On failure, preserve sources and partial evidence;
   investigate before resuming the same frozen plan. Keep MRHA connected.
2. Once `COMPLETE.json` exists, measure actual free space, update 7-3.archive
   and the review/current-state observation, refresh compressed notes and commit.
3. On user-directed V7 resumption, read
   [archive README](docs/reference/V7_COLD_ARCHIVE_README.md) and
   [last research handoff](handoff-history/HANDOFF-2026-10-02-before-v7-cold-archive.md).
   Restore source/environment, external targets, inputs/plans, then all checkpoints.
4. Retain selected `v7-required-inputs-20261002-perf-r0` lineage. Resolve the
   paused-V6 memory reserve and Massive historical-option HTTP 403 before actual
   research continuation. Gates 7-1/7-2 stay complete; 7-3 and later gates stay open.

## Preservation

Preserve unrelated dirty/untracked work and frozen sources/contracts. Root `.env`
is excluded from archives. No completed capture rerun, source relabeling, silent
exclusion expansion, subscription purchase or automatic non-V7 resumption.
