# September 29 power interruption — recovered stopping point

Investigation at 16:36–17:05 Central. Gate **7-3 remains open**. This is a recovery
census, not a campaign restart or full-disk integrity certification.
[Machine-readable checks](2026-09-29-power-surge-recovery.json).

## Timeline

Last saved implementation/handoff commit: `28bca08`, 12:59:53 Central; local HEAD
and the local `origin/main` tracking reference both contained it. Unrelated dirty
and untracked work remains present and untouched. The previous boot journal ends
at **13:13:55** without orderly shutdown. Completed quote packs continue through
**13:14:07** by filesystem timestamp. This narrows surviving evidence to around
13:14 rather than proving the user's approximate 13:30 time; exact loss time is unknown.

First return: 16:11:28. Journald reported an unclean/corrupted user journal and
replaced it; that message alone does not prove dataset corruption. An orderly
shutdown occurred at 16:23:54, followed by the current boot at 16:24:29.

V7 discovery/capture started at 10:44:15; the retry waiter at 12:55:24. All three
transient units are now absent/inactive. Default `Result=success` does not mean
those interrupted jobs completed.

## Surviving evidence

**Quotes:** stale progress at 13:13:53 says 72,000 windows / 3,000 packs. A full
checksum and expected-batch-identity census verifies **3,005 packs / 72,120 windows**,
158,704,986 bytes, zero errors. Frozen scope: 109,825 windows; **37,705 remain**.
There are 294 retained partial directories; the last controller lists 290 HTTP-502
failures. Partials are not coverage and are not all attributable to the outage.
No final index receipt or r5 index was published. The frozen snapshot and both
controllers' bound input hashes pass.

**Discovery:** 93 existing wave receipts remain: 28 discovered, 61 checkpointed,
two previously interrupted, two stale-running. The controller's 18 discovered
securities describe its traversal, not the global census. Active workers were
`BBG000BFRF55` and `BBG000BFT2L4`. Their databases and rollback journals were copied
to `/tmp` and recovered there; both passed `PRAGMA quick_check`. Recovered committed
counts: respectively 3,945 / 5,007 cohorts and 1,324 / 1,451 pending rows. Original
databases/journals were not opened for writes. Unsaved transactions and unfinished
requests may need replay; this is not a general zero-data-loss finding.

**References:** all 84 raw packs pass checksums, preserving 1,985 dated responses
(1,979 standard, six 404s). Alternate-recovery pack and sealed reconciliation pass.
Two matching alternate queries still need admission review. No exclusions changed.

**V6:** morning 93/449 catch-up was already stopped before the power loss. Its
persistent timer resumed at 16:11:31, saved 95/449, then shutdown terminated it at
16:23:53. `service-exit.json` records TERM; `running` progress is stale. It is
inactive; next retry midnight September 30. No training/freeze started.

**Paper orders:** broker and portfolio databases pass read-only quick checks.
Local records contain eight filled orders (five entries, three closes), superseding
first-fill-pending notes. Last saved broker poll: 13:14:00, reporting four positions.
Last scan began 13:00 and completed in 280.834 seconds. These local observations do
not establish post-outage broker positions/orders; reconciliation and review of
missed intraday management remain outstanding. This investigation submitted or
canceled no orders.

## Storage and continuation

MRHA was connected but unmounted. Verified **MRHA / UUID 62C9-C390**, then remounted
at `/run/media/healy/MRHA`. All four existing entry-payload symlinks resolve; three
sampled packs pass checksums. Internal disk: about **87 GiB free, 91% used**; MRHA:
about **693 GiB free, 63% used**. No bulk data moved. New recovered quote packs total
only 159 MB. Large local trees include current catalog (~116 GiB), scheduler
(~100 GiB), replay campaign (~24 GiB), execution plan (~13 GiB). These are provenance
and checkpoint inputs, not disposable scratch.

Keep the existing 10-GB floor and pending-write reserve. The newer entry producer
has MRHA routing; frontier capture uses older local `capture_v7_joined_sample.worker`
and its quota ledger (250 GB limit, zero reservations at inspection). Do not assume
all writers auto-overflow. Before substantial growth, select cold immutable payloads
for checksum-verified copying with preserved local receipts/locators. Do not move
active databases or bulk-delete the scheduler/catalog.

Next permitted V7 continuation: preserve interrupted receipts/journals, reconcile
stale workers under locks, reuse completed packs and retry missing batches from the
same snapshot, seal a combined index, review references, then bind new replay epochs.
The existing launcher refuses starts after 15:00 Central; this inspection did not
override V6's evening allocation or restart acquisition. V6 needs permitted catch-up
continuation; paper needs post-outage reconciliation. Completed entry capture and
gates 7-1/7-2 remain complete.
