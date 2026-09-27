# Handoff — 2026-09-26 — storage inventory and joined-capture quality verified

Read TODO first. Prior handoff:
`handoff-history/HANDOFF-2026-09-26-before-storage-review.md`.
Work on main and preserve unrelated dirty/untracked changes.

## Current task and authority

V7-1/7-2 complete; V7-3 remains current. User asked to double-check disk space,
permits using nearly all local storage and joining adjacent intervals without
quality loss, then requested a review of millions of potentially redundant files.
The storage/retention review and six-case joined-download proof are complete.
No project data was deleted, deduplicated, archived/moved or relabeled.
No bulk capture campaign or training has launched. No live systems were changed.

New capture planning reserve: **20 GiB**, in
`docs/specs/V7_CAPTURE_CAPACITY_20260926.json`, counting in-flight writes.
The 250 GB acquisition and 640 GB project limits remain. Old frozen writers
retain their historical 100 GiB guards; the small quality pilot used that
stricter writer too. A new bulk consumer must enforce the amended policy.
Do not mutate frozen producers/readers to bypass their bindings.

## Latest capacity and inventory

Initial df/statvfs/Btrfs recheck: 158.04 GB free, or 136.57 GB after 20 GiB.
During this read-only review, free space increased externally to **231.58 GB**,
leaving **210.10 GB after 20 GiB**. Cause unconfirmed; this agent freed nothing.
All 6,012 verified duplicate files were still present with unchanged inode,
device and size; old V6 captures retained 453 symbol directories.
Recheck free space immediately before any launch; it can change independently.
Snapshot: `nn_meta/validation/storage-review-verdict-20260926`.

Read-only inventory: `nn_meta/validation/project-storage-inventory-20260926`.
13,303,859 file entries, 2,890,819 directories, zero errors. Four symlinks were
not followed; `.agents` is a separate mount and was excluded.
489.14 GB unique file contents; 514.14 GB by names, including 25.00 GB already
shared through hardlinks. Allocated blocks are not guaranteed deletion savings.

Largest areas:
- Current V7 catalog: 117.67 GB, 1,987,291 files; preserve.
- Current demand: 106.55 GB, 14,495 files; preserve bound exports too.
- V7 acquisition roots: 87.36 GB by names / ~68.98 GB unique; preserve lineage.
- V6 campaigns: 83.94 GB, with multiple generations and duplicate arrays.
- Old V6 expanded inputs: 51.53 GB, 9,541,723 files / 2,066,117 directories.
  Its 47.21 GB full-run is the main file-count problem, not empty junk.
- Main V6 live data: current installed data-index points here; preserve.

## Duplicate and retention findings

`storage-large-duplicates-20260926`: scanned named campaign/cache roots,
hashed 6,022 size-matched files >=1 MiB (90.98 GB). Found 1,322 exact-content
sets: 4,690 extra copies / **53.88 GB**, including **28.87 GB prepared arrays**,
10.46 GB cache duplicates and 14.56 GB other datasets/marks/files.
`storage-duplicate-extents-20260926`: Btrfs reports 53.84 GB exclusive extents
for those extra copies. Exact path/hash/reference lists are saved. This is a
review list; no file replacement, linking or deduplication was performed.

`v7-retained-inputs-audit-20260926`: scanned all current 591 demand/daily and
1,773 feature/proposal declaration pairs plus gate/kernel inputs: 5,326 docs,
16.02 GB. Numerous old-looking V7 dividend/action/identity/raw roots are still
referenced. Path-reference audit is not exhaustive transitive garbage collection.
Old V6 campaign/expanded-input roots are absent from these V7 declarations.

Installed V6 forward service uses the packaged release under the permanent
HealysV6 checkout, and its data-index points to main's dated v6_server/data.
Old raw captures remain valuable training/parity provenance, not its live
forward-data root. Current bundles/state/data and activation evidence stay intact.

The weekly cache backup script does NOT include expanded inputs, campaigns or
V7 acquisition, so do not assume those trees are backed up. MRHA is documented
as the historical restore-kit disk, remains unmounted and was not written to.

## Joined capture quality

Plan: `nn_meta/validation/v7-adjacent-quality-plan-20260926`.
Proof: `nn_meta/validation/v7-adjacent-quality-proof-20260926`.
Raw fixed and joined archives: `nn_meta/data_v7/adjacent-quality-20260926`.
Six cases across 2022–2026 plus density stress: 62 fixed captures vs 12 joined,
12 previous shards reused by immutable hardlinks. All 24,527 full-range raw
records and all 126 original causal request reads match exactly: timestamps,
fields, precision, order and duplicate counts preserved. Gaps stay gaps.
This proves these real quality cases, not a representative joined volume forecast.

Prior full census remains `v7-contiguous-entry-union-20260926`: 10,941,828
contiguous ranges vs 42,030,534 fixed windows; exact same requested nanoseconds.
The prior 1,440-capture full-population sample and encoding experiment remain
unchanged: existing layout estimates 218.04 GB; candidate encoding 164.08 GB.
Their forecasts exclude full execution paths and some storage overhead.

## Next concrete work

Prepare content-preserving deduplication of exact immutable copies, beginning
with repeated prepared arrays, while retaining required paths/hashes. User
requested review; do not interpret it as permission to erase campaign trees.
For the huge V6 archive, create/verify a recoverable archive and restoration
proof before considering removal of loose historical files.

Measure a representative joined-range storage forecast and validate packed,
indexed capture storage before bulk download. A directory per each of 10.94m
joined ranges would still create millions more files. Reconcile capture,
project, temporary storage and full execution-path costs. Dated contract
references/class hours, fills/marks/exits/rolls/delivery, execution, assembly and
readiness remain before training. All original V7-2 freezes/proofs are preserved.

Review: `docs/reviews/2026-09-26-storage-retention-and-adjacent-quality.md`.
Full suite: **2,427 tests + 18 subtests**, 20 warnings, 117.26 seconds.
Real inventory/reference/duplicate/extent audits also completed successfully.
The old hourly completion-alert timers remain disabled. Existing CLI capture
viewers show completion, not training. October 2 subscription, V6 Alpaca bridge
and incubator work remain separate carried-forward tasks.
