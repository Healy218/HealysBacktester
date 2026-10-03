# Handoff — October 3, 2026 — concurrent verified-local V7 cleanup

## Priority

User requested cleaning the verified local V7 data while the last MRHA chunks
continue compressing. This supersedes waiting for the entire bundle before
local reclamation. V7 research and other campaigns remain paused.
[TODO](TODO.md), [scope and tests](docs/reviews/2026-10-03-v7-verified-local-cleanup.md).

## Selected runtime

Archive: `healys-v7-cold-archive.service`, unchanged staged-v2 consumer and frozen
plan. It is in external-only serial compression; do not restart it needlessly.
Cleanup: `healys-v7-local-reclaim.service`, entrypoint
`scripts/reclaim_v7_verified_local_v2.py` over the frozen v1 cleanup consumer.
It reuses the existing deletion journal. Source-recovery binding is separate;
no scientific checkpoint or old archive declaration was relabeled.

State: `nn_meta/validation/v7-cold-archive-20261002-r0/`.
Destination: `/run/media/healy/MRHA/v7/`, mounted UUID `62C9-C390`.
`progress.json` owns compression; `early-cleanup-progress.json` owns cleanup.
`early-cleanup-declaration.json` binds all local receipt hashes.
`early-cleanup-consumer-v2.json` binds the completion-status repair.
`retired.jsonl` and `retire-intent.json` are shared with original final cleanup.

## Scope and coordination

All 2,584 local shards verified; 35,031 regular files >1 MiB eligible, 502.58 GiB
logical. Keep small metadata, symlinks, raw/shared inputs, plans, source and MRHA
originals. Fresh external-archive and local-source SHA256 checks precede deletion.
Archive reads capped at 16 MiB/s, idle I/O, Nice 19, 1-GiB memory max, no swap.
Only the Python controller is briefly coordinated around each journaled unlink;
compressor children keep running. ExecStopPost recovers an owned controller stop.
Early cleanup yields to original final cleanup once full verification is published.

## Verification and observations

19 focused tests passed, including archive corruption/source-change rejection,
all-local-receipt admission, journal compatibility and real process stop/recovery.
Initial 112-file pass was preserved after fixing a completion-status keyword
error in a separate v2 consumer. The corrected service started 11:11:48 Central.
At 11:13, 544 files were removed; SSD free space was about 22 GiB versus about
20 GiB before cleanup. MRHA compression continued. Later scoped observation:
[launch receipt](docs/reviews/2026-10-03-v7-verified-local-cleanup-launch.json).
No local or full completion claim is implied by those observations.

## Next actions

1. Inspect both exact progress receipts/services; keep MRHA connected.
2. `LOCAL_CLEANUP_COMPLETE.json` closes only the verified-local subset. Measure
   actual free space and close 7-3.archive-local after that receipt passes review.
3. `VERIFIED.json` and `COMPLETE.json` still own full archival/final reclamation.
   Refresh compressed notes and owning docs after either completion milestone.
4. On user-directed V7 restoration, follow [README](docs/reference/V7_COLD_ARCHIVE_README.md)
   and [last research handoff](handoff-history/HANDOFF-2026-10-02-before-v7-cold-archive.md).
   Memory admission and historical-provider HTTP 403 blockers remain unresolved.

Preserve unrelated dirty work, frozen sources and credentials. No source reset,
completed recapture, model promotion, subscription purchase or other-work resume.
