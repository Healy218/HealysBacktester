# Concurrent verified-local V7 cleanup — October 3, 2026

The user explicitly requested reclaiming local space while the remaining MRHA
chunks are compressed. This supersedes the earlier all-shards-before-local-cleanup
operating policy; it does not weaken per-shard verification or close the full
archive task. Scientific gates and the frozen archive plan are unchanged.

## Admitted scope

All **2,584 local-source shards** have complete verification receipts. Eligible
scope is **35,031** regular files larger than 1 MiB in the frozen V7 validation
trees, totaling **502.58 GiB logical**. Their compressed archive shards total
151.58 GiB. No local verification receipt was missing. Logical bytes are not a
promise of actual SSD space gain: hardlinks and shared Btrfs extents remain
accounted for by observed filesystem free space.

Keep raw input trees, small receipts, directory scaffolding, symlinks, plans,
working/frozen source, external originals and non-V7/shared inputs. Preserve
top-level plan roots so the still-running compressor can validate its unchanged
scope. There were no eligible top-level root files in this inventory.

## Verification and coordination

Selected service: `healys-v7-local-reclaim.service`.
Base consumer: `scripts/reclaim_v7_verified_local.py`; selected status-recovery
consumer: `scripts/reclaim_v7_verified_local_v2.py`. Both source identities are
retained. Archive compressor remains `healys-v7-cold-archive.service`, staged-v2.

The cleanup binds the original plan plus all local verification-receipt hashes.
Before each affected shard, it compares local/external receipts and rehashes the
actual MRHA archive. Each source file must still match its original inode/type/
size/mtime and SHA256. Unexplained changes or missing files stop cleanup.

An identity-checked Linux pidfd briefly stops only the original Python controller
during each unlink/journal critical section; its compressor subprocesses continue.
After the stop is acknowledged, the cleanup checks that the controller is still
in its external-only phase and has not published full verification. It then
records durable deletion intent and appends/fsyncs the original `retired.jsonl`
journal before resuming the controller. Expensive archive/source hashing happens
outside this short critical section. This prevents racing the original final
cleanup without restarting the archive or rereading all completed shards there.

An owned-pause marker plus `ExecStopPost` recovery resumes the exact controller
after cleanup failure/termination. PID reuse and an already-existing stop are
rejected. When full verification is reached, early cleanup hands remaining work
to the original final pass, which consumes the same journal and skips completed
removals. The original code and its binding are not modified.

Archive rehash reads are capped at 16 MiB/s, with Nice 19, idle I/O class/weight 10,
768-MiB/1-GiB memory high/max and no swap. This limits competition with compression.

## Tests and completion receipts

**19 focused tests passed**, covering actual restoration, corruption/source-change
rejection, local-receipt completeness, frozen-root preservation, original-final-
cleanup journal compatibility, full-phase handoff, real process stop/resume and
owned-stop recovery, as well as the prior archive/staging tests. Host unit
verification passed. No broad scientific reruns were performed.

The first pass removed 112 fully verified files before being stopped to correct
a completion-status timestamp-keyword error identified by testing. No integrity
check failed. The v2 recovery changes only status construction and retains the
v1 declaration and already completed journal entries. All 19 tests passed before
the corrected pass was resumed.

Local state: `nn_meta/validation/v7-cold-archive-20261002-r0/`:
- `early-cleanup-declaration.json`: frozen local shard/receipt scope.
- `early-cleanup-consumer-v2.json`: status-recovery source/plan binding.
- `early-cleanup-progress.json`: cleanup phase, files and observed free space.
- `retired.jsonl`, `retire-intent.json`: original compatible deletion journal.
- `LOCAL_CLEANUP_COMPLETE.json`: completion of this local subset only.

Full archive completion still requires the original `VERIFIED.json` and
`COMPLETE.json`. Early cleanup neither fabricates these nor claims the remaining
MRHA payloads have finished compression. Restore/resume instructions and this
runtime are included in the refreshed MRHA `v7/notes` bundle.

## Deployment observation

Corrected service started **11:11:48 Central**. At 11:13 its journal contained
544 removed files and the SSD had about 22 GiB free, compared with about 20 GiB
before cleanup. The original compression process continued advancing through
external shards. [Subsequent measured launch receipt](2026-10-03-v7-verified-local-cleanup-launch.json)
records separate progress and logical/physical measurements; neither completion
receipt existed at that observation.
