# V7 live storage allocation and 14 GiB capture — September 27, 2026

The user authorized leaving only 10 GB free locally, using MRHA for overflow,
and downloading as fast as possible within the training-size 14 GB RAM allocation.
Both changes are deployed in `healys-v7-capture-v5-20260927.service`.
Code commits: `a545b31` and `0a87eef`. Current meter and launcher are in HANDOFF.

## Capacity and location

The new frozen policy `docs/specs/V7_CAPTURE_STORAGE_20260927.json` supersedes the
100 GB campaign, 250 GB acquisition, 640 GB project limits and 20 GiB reserve.
Routing checks actual free space before each dispatch, retaining **10 billion
bytes** plus all outstanding payload/metadata reservations. Local storage is
preferred; new payloads overflow to mounted UUID **62C9-C390** at
`HealysBacktester/v7-entry-campaign-20260927`. MRHA also keeps 10 GB free. Existing
external data is unchanged. At launch, free space was approximately 279 GB locally
and 744 GB externally, yielding about 269 GB and 734 GB additional headroom.
The shared acquisition ledger now permits about 1.079 TB including already
charged data; this reflects capacity, not a prediction of required download size.

Original pack directories and binding/completion receipts remain locally
addressable. An overflow pack's SQLite file alone is a symlink to its immutable
MRHA payload, so recursive discovery, SHA256 verification and existing packed
index readers work unchanged. Whole-directory symlinks are deliberately avoided.
UUID/mount checks precede external writes and publication. A missing external
payload fails verification; it is never interpreted as an empty capture.
External bytes and local locator metadata are charged once. A physical pack
whose local publication failed is verified and relinked on retry without another
API request or duplicate payload charge. Do not reset the ledger using the old
local-only tree initializer.

## Resources and speed

Four autosized processes now allow up to 32 I/O threads each: **128 requests**.
Numerical libraries remain one thread each. MemoryHigh and MemoryMax both equal
**14 GiB**, swap is disabled, and prefetch reduces at 6/8/10 GiB usage to leave
space for outstanding responses and encoding. The CPU burst ceiling is 800%
with CPUWeight 50 and Nice 10, protecting higher-priority live work. No live V6
or broker configuration changed.

The prior producer drained completely, with zero quota reservations. All 8,704
completed packs / 278,284 ranges were verified and reused. Original through v3
sources and declarations remain unchanged; v4 binds their hashes and holds all
prior controller locks to prevent duplicate campaigns.

A 30-second dense-data observation increased from 10.66 ranges/s before the switch
to 22.39 ranges/s afterward. New sample memory peaked at 10.40 GB; the later
snapshot peaked at 10.80 GB, without memory-limit/OOM events. The new sample had
zero CPU quota throttling and zero provider throttles. These are different real
windows, not a same-data benchmark. Quiet windows can be substantially faster.
Do not extrapolate the earlier 78 ranges/s sample or 38–48-hour estimate as a
reliable full-run ETA. Use the current controller's sustained rate and preserve
uncertainty about later row density. Entry completion still does not close 7-3.

## Verification

Sixteen focused tests passed, covering reserve/in-flight routing, wrong-drive
rejection, local locator discovery, unchanged index reads, single-charge resume,
failed publication recovery, prior producer identity and existing pagination
checks. Launcher syntax passed. No completed catalog/demand campaign was rerun.

The first **four real pending batches** were intentionally routed to MRHA, then
**40,886 actual records** were read back through the original local packed/index
readers with matching hashes. The full queue then continued on local disk.
Proof index: `nn_meta/validation/v7-overflow-readback-20260927`; sibling
`v7-overflow-readback-20260927-proof.json`. Ordinary restart command uses `32`;
there is no need to repeat the initial `32 0 4` overflow check.

The companion [machine-readable evidence](2026-09-27-v7-storage-and-memory.json)
records policy application, before/after measurements, mounted drive, readback,
resource settings and the live snapshot. At that snapshot 299 v4 batches had
completed, with zero failed attempts, retries or HTTP 429s. The service remained
running with no stop reason.

## Cache-aware final guard

The follow-up ETA check found 10.98 GB cgroup memory consisted primarily of
9.12 GB clean inactive file cache, with 1.73 GB anonymous memory. Version 4 had
incorrectly treated that reclaimable cache as live-buffer pressure and reduced
concurrency. Version 5 subtracts only clean inactive file cache, preserves
dirty/writeback and active pages in the pressure estimate, and floors it at
anonymous/kernel/socket/shared-memory usage. The 14 GiB hard limit is unchanged.
The original cache-blind producer remains frozen; the new controller also binds
and reuses its packs. Eight focused tests and launcher syntax passed. This is
a performance correction, not a change to tick data or overflow semantics.

The final live sample measured 185.56 ranges/s, with
729 newly completed batches and no failed attempts/API throttles at
the evidence snapshot. It reused 9,422 packs / 301,248 ranges including all four
MRHA packs. This follows the working-memory correction; the earlier roughly
three-day extrapolation was taken while the cache-blind guard was reducing I/O.
The new run's short sustained pace around 164 ranges/s extrapolates to roughly
18 hours for entry capture, but later density remains unknown; budget 24–48 hours
provisionally, not as an upper bound or a full V7-3 ETA.
