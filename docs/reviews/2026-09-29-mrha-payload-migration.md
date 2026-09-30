# Sealed V7 payload migration to MRHA — September 29, 2026

The user requested moving as much stock/ticker data as safely possible after
reviewing internal-disk pressure. The selected scope is all eligible completed,
checksum-bound raw payloads under `nn_meta/data_v7/`. This includes historical
stock bars/provider pages and option aggregates/tick/reference captures.

## Frozen scope and boundary

- 504,516 local payload paths; **229,378,057,319 logical bytes**.
- 474,125 distinct content hashes; **204,487,023,318 unique file bytes**, before
  external filesystem allocation overhead. These are not promised physical SSD savings.
- Four existing external payload links are preserved. Three sealed capture
  files with SQLite journal/sidecar evidence are explicitly excluded and stay local.
- All original directories, completion receipts and metadata stay local. Only
  file payloads become symlinks; hashes and frozen producer sources remain unchanged.
- V6 working data, live paper inputs, models, feature arrays, demand/quote indexes,
  planner outputs and writable execution databases remain on the SSD. Steam untouched.

The selected manifest is
`nn_meta/validation/v7-mrha-payload-migration-20260929-r1/plan.json`; per-file source
paths, expected hashes, original inode/size/timestamps/mode and status are in
`files.sqlite3`. The earlier unfinished inventory is retained separately; it
performed no migration. No newly discovered request is permission to move a writer.

## Publication, recovery and restore

Destination: `/run/media/healy/MRHA/HealysBacktester/sealed-v7-payloads-20260929/`.
The mounted read/write drive must have UUID **62C9-C390**. Objects are stored by
SHA256 under `objects/<first-two-hash-characters>/<hash>` so duplicate immutable
content shares one external copy. Local logical paths remain unchanged.

Every transfer verifies the bound receipt, checks source metadata, copies to a
new external temporary file, fsyncs and rehashes it, publishes the external object,
rehashes the source and rechecks its receipt before atomically replacing the
local file with a symlink. There is no interval with a missing logical path.
An already-open read-only SQLite descriptor retains its old inode until closed.
Both local and external journals record each cutover. A stopped/interrupted pass
can resume links already published before a journal/status update. External space
must remain above 20 GiB. Quota ledgers are not reset or credited with migration
savings; migrated evidence remains retained data, not deleted capture scope.

The original mover stopped safely at seven files when unlinking one historical
hardlink alias changed the ctime of its remaining alias. Bytes, inode, size and
mtime matched; the copied peer was recorded. The separate **v2 recovery consumer**
accepts only this explicitly evidenced case: same original inode/size/mtime,
previously moved matching alias, verified external bytes, then a full source
rehash. Unexplained metadata/content changes still stop the run. Original plan
and v1 source remain frozen; `consumer-v2.json` binds the recovery revision.

External `RESTORE.txt`, `plan.json`, `files.sqlite3` and `migration.jsonl` retain
restoration information. Keep MRHA mounted at the bound path. Restoring a payload
means copying to a temporary local sibling, verifying its saved checksum,
restoring recorded mode/mtime and atomically replacing the symlink. The external
object store is a storage tier used by training/replay, not a second backup copy.

## Runtime and verification

Selected service: `healys-v7-mrha-migration-v2-20260929.service`.
Selected consumer: `scripts/migrate_v7_payloads_mrha_v2.py run --state
nn_meta/validation/v7-mrha-payload-migration-20260929-r1`.
Sequential streaming I/O; low priority (Nice 19, idle I/O), CPU 100%, 768-MiB
memory high / 1-GiB maximum, no swap. Stops on failed evidence or capacity;
otherwise works through the complete finite manifest. Do not start another mover.
Initial external catalog backup can precede the first fresh progress update.

13 focused tests passed: source/destination corruption rejection, failed-cutover
recovery, deduplication, open/new SQLite readers, known-hardlink recovery,
unexplained metadata rejection, and existing overflow/quota invariants. The
first three real external files passed full checksum and gzip readback with
unchanged completion-receipt hashes. Subsequent measured observations are in
[the observation record](2026-09-29-mrha-payload-migration.json).

`progress.json` owns current counts, free space, failure reason and completion.
Only `status=complete` with all 504,516 manifest rows moved establishes completion;
service launch or a stale terminal meter does not. Original v1 transient unit
failure is historical. Both V6 and V7 must be checked independently for coexistence.
Gate 7-3 and training readiness are unchanged by storage migration.
