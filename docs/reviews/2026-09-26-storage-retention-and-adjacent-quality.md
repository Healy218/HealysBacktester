# Storage review, reserve amendment and joined-capture quality — September 26

The review found substantial redundant data and an identifiable source of the
file-count problem. It made **no deletions, deduplication, archive moves or live
configuration changes**. Original freezes and captures remain intact.

## Computer space and the user's revised reserve

At the initial recheck, `df`, `statvfs` and Btrfs reported about **158.04 GB free**
on the internal 1 TB NVMe filesystem. The earlier 50.67 GB figure was available
space *after* the previous 100 GiB operating reserve, not total free space.
The user authorized using nearly all local capacity. New capture planning now
uses a **20 GiB (21.47 GB) reserve**, with in-flight writes counted before each
worker group. Policy: `docs/specs/V7_CAPTURE_CAPACITY_20260926.json`.
The separate 250 GB acquisition and 640 GB project limits remain unchanged.
Original frozen producers retain their original guards; the small quality
validation used the existing stricter 100 GiB writer alongside the new plan.

During this read-only review, free space increased to **231.58 GB**, leaving
**210.10 GB after the new reserve**. This agent did not free that space; the
cause of the external change is unconfirmed. All 6,012 files in the verified
duplicate groups remained present with unchanged inode, device and size, and
the V6 raw archive still had its 453 symbol directories. Capacity snapshot:
`nn_meta/validation/storage-review-verdict-20260926`.

The installed filesystem uses Btrfs `compress=zstd:1` with duplicated metadata.
An initial sandbox-only device warning disappeared when the read-only Btrfs
check ran outside the sandbox; the actual filesystem reported zero missing
devices. No filesystem repair or mount operation was performed.

## Actual project inventory

One read-only traversal counted **13,303,859 regular file entries** and
**2,890,819 directories**, with zero read errors. Four symlinks were not followed;
the separate `.agents` mount was excluded. This is a non-atomic project inventory,
not the entire computer's storage. Counts precede the small new review reports.

| Area | File contents | Files | Retention finding |
|---|---:|---:|---|
| Current V7 feature/proposal catalog | 117.67 GB | 1,987,291 | Current freeze; preserve |
| Current V7 demand scheduler outputs | 106.55 GB | 14,495 | Current demand and bound exports; preserve |
| V7 acquisition roots | 87.36 GB by names; about 68.98 GB unique | 264,473 | Includes hardlinked aliases and active raw evidence |
| V6 campaign directories | 83.94 GB | 821,621 | Several generations, with verified duplicate datasets/arrays |
| V6 expanded input archive | 51.53 GB | 9,541,723 | Main file-count source; historical training evidence |
| Corrected/earlier data-candidate caches | 15.97 GB | 248,395 | Mixed active inputs and duplicate/older copies |
| Main V6 live data | 7.19 GB by names | 12,302 | Current live data-index points here; preserve |

The V6 expanded archive contains about **72% of all file entries** and
2,066,117 directories. Its `full-run` alone contains 9,538,316 files and
2,065,573 directories, totaling 47.21 GB of contents. This is mostly genuine
captured option history plus manifests/attempt receipts, not disposable empty
directories. The archive's allocated file-block count is 80.71 GB versus
51.53 GB of contents, illustrating the tiny-file overhead; it is not a promise
of space returned by deletion. Directory/metadata and Btrfs extent accounting
require separate interpretation.

Whole-project unique file contents total **489.14 GB**. File-path sizes sum to
514.14 GB because **25.00 GB is already shared through 30,155 hardlink aliases**.
Those aliases are not additional independently reclaimable copies. Unique-file
attribution among directories depends on which hardlink was visited first.
Detailed evidence: `nn_meta/validation/project-storage-inventory-20260926`.

## Verified content duplication

The focused duplicate audit scanned campaign and cache roots, selected
size-matched files of at least 1 MiB, and SHA256-hashed **6,022 files / 90.98 GB**.
It found **1,322 identical-content groups**, covering 6,012 files in distinct
inodes. Keeping one equivalent file per group leaves **4,690 extra copies /
53,884,528,671 bytes** of identical contents:

| Category | Extra identical contents |
|---|---:|
| Prepared training arrays | 28.87 GB |
| Repeated cache files | 10.46 GB |
| Other campaign datasets, marks and related files | 14.56 GB |

For example, the same 3.30 GB `train_raw.npy` appears in the cash-repair,
neural-repair and previous training campaign. All three hashes match, while
all three have separate inodes and exclusive Btrfs extents. Extent checks across
the entire reviewed set report **53.84 GB of exclusive extents** for the extra
copies. This supports substantial deduplication potential, but actual free-space
gain must be measured after a separately authorized operation.

Evidence: `nn_meta/validation/storage-large-duplicates-20260926` and
`nn_meta/validation/storage-duplicate-extents-20260926`. The latter contains an
exact review list with reference paths, equivalent paths, hashes and sizes.
These are review choices, not instructions already executed.

## What the current systems still reference

`v7-retained-inputs-audit-20260926` scanned **5,326 current documents / 16.02 GB**:
all 591 demand declarations, all daily declarations/input lists, all 1,773
feature and proposal declaration pairs, and current gate/kernel evidence.
It found current references to numerous older V7 action, dividend, identity,
calendar and raw-source roots. Do not remove those based on their dates or
an `r2`/`r3` suffix. This is a path-reference retention aid, not a proof that
every unmentioned directory is garbage or that every transitive dependency
has been traversed.

The old V6 campaign and expanded-input roots did not appear in those current
V7 declarations. Installed V6 forward service configuration points at the
packaged cash-repair release in `/home/healy/Coding/HealysV6`, and its current
data index points at main's `nn_meta/live/v6_server/data/2026-09-25`. That service
does not use the old V6 raw archive as its forward-data root. The archive is
still historical training/parity provenance and must remain recoverable.

The two explicitly superseded early V7 catalog directories total only about
**2.61 GB** (0.42 GB early pilot and 2.19 GB superseded September 24 stores).
They are lower-value archival candidates than the V6 redundancy. Current
catalog/demand, frozen model bundles, live data/state and provenance receipts
remain protected.

The committed weekly cache-backup script does **not** include V6 expanded
inputs, campaign directories or the V7 acquisition tree. It cannot be treated
as proof those trees are backed up. The unmounted MRHA drive is documented as
the historical restore-kit drive; its current backup contents were not inspected.

## Quality of adjoining requested intervals

The user approved joining adjacent intervals if quality is preserved. The
existing full census already proved 42,030,534 fixed windows can be represented
by 10,941,828 exact contiguous ranges without adding or dropping a nanosecond.
Now a real provider/consumer comparison also passes across six cases spanning
2022–2026, including the densest previously sampled quote case:

- 62 fixed-window captures versus 12 joined captures; 12 exact old shards reused.
- All **24,527 full-range records** match byte for byte in canonical form.
- All **126 original request reads** through `QuoteArchive.window` match,
  preserving timestamps, order, duplicate multiplicity, fields and precision.
- Requests never cross contract, data kind or day; genuine gaps stay gaps.
- Complete pagination is required. A page-budget failure is not truncated data.

Plan/proof: `v7-adjacent-quality-plan-20260926` and
`v7-adjacent-quality-proof-20260926` under validation. Original fixed archives
are preserved. These are quality/stress cases, not a representative joined-range
storage forecast. They do not establish full-universe execution readiness.

## Recommended next work

1. Prepare a content-preserving deduplication operation for the exact duplicate
   arrays/files, retaining every required pathname and hash. Start with the
   28.87 GB prepared-array duplication; do not remove entire campaign folders.
2. For the huge V6 file count, build and verify a recoverable archive and test
   restoration before considering removal of its loose historical tree.
3. Measure the representative joined-range forecast and use an indexed packed
   capture layout before bulk V7 acquisition. A directory per joined range
   would still create millions more files; joining alone does not solve that.
4. Reconcile acquisition, total-project, temporary-space and execution-path
   requirements with actual free space. Training remains behind its gates.

Tests: **2,427 passed plus 18 subtests**, 20 warnings, 117.26 seconds. The actual
inventory, reference, duplicate-hash and extent audits also completed; new
read-only audit utilities were exercised on the real data. No cleanup occurred.
