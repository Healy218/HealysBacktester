# Authorized duplicate reclamation and V6 archival

The user explicitly requested removal of byte-identical extra copies and
archival of the 9.54 million-file historical V6 input tree to the MRHA external
drive. This supersedes the earlier review-only authorization. Current V7
freezes, demand, raw-source lineage and live V6 data remain in place.

## Duplicate allocation removal

The exact 1,322 groups recorded by the preceding hash/extent audit were used.
Each reference and extra copy was rehashed immediately before replacement;
file identity, size, modification time and change time were checked around the
operation. A sibling Btrfs reflink was created, verified, given the original
metadata and atomically substituted for the redundant allocation.

All **4,690 extra allocations / 53,884,528,671 logical bytes** were processed.
All historical paths and hashes remain usable. These are separate copy-on-write
inodes, so modifying one does not alter its reference or siblings. This removes
redundant physical copies without breaking path-bound manifests or sharing writes
through hardlinks. The test explicitly exercises independent writes.

Measured free space increased from **231,547,076,608** to **263,215,714,304**
bytes: **31,668,637,696 bytes**. Logical/extent totals from the review were not
a promise of actual physical reclamation; Btrfs compression and concurrent
filesystem activity affect that measurement.

Evidence: `nn_meta/validation/storage-duplicate-reclamation-20260926`, including
the per-file replacement journal and source/review hashes.

## Historical V6 archive protocol

Source: `nn_meta/expanded_inputs/v6-local-20260906`.
Destination: `/run/media/healy/MRHA/HealysBacktester/v6-archive-20260926`.
The mounted drive is identified by UUID **62C9-C390**, label MRHA, exFAT, with
about **779 GB free** before migration. Existing external backups are preserved.

The archive consists of 453 symbol capture tar.zst files plus one context/store
tar.zst. POSIX tar headers retain Unix file metadata, ACLs, xattrs and filenames
inside exFAT-compatible container files. Compression uses at most four autosized
outer jobs and one compression thread per job. Archive creation seals a before/
after metadata fingerprint and SHA256; completed archives can be reused on
restart after their hashes are checked.

Source retirement is gated on all of the following:

- Counts matching the reviewed 9,541,723 files and 2,066,117 directories.
- External archive SHA256 matching the locally sealed archive.
- Successful GNU tar comparison of every archived source byte and metadata.
- Unchanged source fingerprints and top-level partition layout.
- A real extraction from MRHA and comparison with its original file.
- Rechecking every external archive hash before any source retirement, then
  each source partition immediately before removal.

Local receipts and an archive locator remain available after retirement. The
external folder includes restoration instructions and verification evidence.
These historical artifacts are preserved for restoration; archiving does not
admit them as current V7 input or performance evidence.

The migration's current stage is recorded under
`nn_meta/validation/v6-archive-migration-20260926/progress.json`.
Only a `RETIRED.json` receipt establishes completion of source retirement.

## Completed outcome

All **454 archives / 35,106,688,686 bytes** are on MRHA. The source's
**9,541,723 files, 2,066,117 directories and 51,534,857,599 file bytes** reconcile.
The independent archive-member census confirms those exact file/directory
counts inside the containers. Every external archive passed SHA256 and full
GNU tar byte/metadata comparison; a second external SHA256 pass preceded
retirement. A real quote/trade/manifest restoration matched all original hashes
and decoded 309 quote records, one trade record and the manifest.

The complete loose tree was removed, with 454 per-part retirement journal
entries, and the 454 local staging archives were removed after checking their
hashes against the verified external-copy records. No local tar.zst staging
copies remain. The small metadata receipts and restored sample remain locally.
The locator is `nn_meta/expanded_inputs/v6-local-20260906.ARCHIVED.json`.

Final measured internal free space: **303,613,919,232 bytes (303.61 GB)**,
about **72.07 GB more** than immediately before duplicate cleanup. This leaves
about **282.14 GB above the 20 GiB reserve**. MRHA has about **743.73 GB free**.
These are measured filesystem values; they can change with other activity.
The remaining reflink paths still count toward logical-byte budgets, so their
physical savings must not be credited again as a logical project-size reduction.
The existing acquisition/project limits and V7 readiness gates remain unchanged.

Evidence: `nn_meta/validation/v6-archive-migration-20260926`, especially
`VERIFIED.json`, `MEMBERS-VERIFIED.json`, `restore-smoke.json`,
`restore-consumer-read.json`, `RETIRED.json`, `retirement.jsonl`,
`staging-cleanup.json` and `final-capacity.json`. External `RESTORE.md` explains
how to restore the original repository-relative paths onto a Linux filesystem.

Post-move full suite: **2,432 passed plus 18 subtests**, 20 warnings, 136.58 s,
with the historical tree absent. Generated test temporary directories were
removed afterward. A newer post-tests reading was **297,025,257,472 bytes free**
(~297.03 GB), or **275.55 GB above reserve**; it supersedes the earlier 303.61 GB
snapshot for launch planning. Free-space changes outside the measured cleanup
steps are not claimed as cleanup effects. Final source/proof hashes are recorded
in `final-binding.json` and the test result in `post-move-tests.json`.
