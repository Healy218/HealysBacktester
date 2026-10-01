# V6 daily occurrence repair — October 1, 2026

The user requested repair of CRSP/MTUM, completion of the September 29–30 update,
and restoration of V7/storage after final training/evaluation/freeze.

## Defect and evidence

r4 exited at 00:59:10 Central with 447/449 completed symbols. Both failures were
`Daily parent artifact inputs differ`. The extended simulation emits an additional
`tv_rating` occurrence at an existing September 28 timestamp: CRSP 19:45, MTUM 13:30.
Raw/adjusted stock prefix hashes and existing proposal fields are unchanged.
Whole-entry feature inheritance incorrectly requires the entire occurrence list
to stay equal, despite preserving proposal ordinals in candidate identity.
CRSP audit: `logs/lab-hourly-watch/crsp-input-mismatch.json`; MTUM audit:
`nn_meta/validation/v6-daily-repair-20261001-r5/mtum-input-mismatch.json`.

## Versioned repair and preservation

`scripts/v6_daily_append_v5.py` validates inherited prefixes/scope and each old
proposal, then resolves existing occurrences to their original feature seal.
Missing occurrences get a separate sealed batch with their real ordinal retained.
The inherited ordinal-zero fast path is not allowed to erase an additional ordinal.
Removed/changed proposals, candidate duplication, prefix changes and label-feature
binding mismatches remain errors. Every historical/current candidate is reconciled.

New namespace r5 binds all prior r4 producer hashes plus the new consumer/launcher.
The scientific model family, fixed-family refit, chronological arrays, baseline
comparison and final immutable freeze pipeline are unchanged. No old receipt is
rewritten or relabeled. Verified r4 census includes 3,516 feature batches, 17,070
labels and 447 completed symbols. Completed inventories are symlinked unchanged
only after original producer contract, snapshot, artifact references and history
hashes are verified. The two missing symbols are newly built with this consumer.

## Verification and selected runtime

23 focused occurrence/prefix/inheritance/resource tests passed; nine viewer and
hourly dispatch checks passed. The real CRSP/MTUM pilot succeeded in 86.77 seconds:
1,725 candidates, 117 matured, 402 pending, 1,206 unfilled, 105 new feature rows.
No errors. Pilot and full producer contract match:
`84452acaf5aefda625ca3d84a3558cee5606e1ebcf421f0dfbb0bfa4464ba6c0`.
Full r5 start: **01:35:39 Central** under `healys-v6-continual.service`.
Actual full training/evaluation/freeze is pending; the pilot does not establish it.

Persistent daily override is `50-daily-v5.conf`; temporary dedicated override is
`95-dedicated-r5.conf`. Dedicated wrapper preserves five autosized worker slots,
16 training threads and 26 GiB, with the existing morning deadline. After verified
full candidate completion, it removes both temporary r5/r4 overrides and restores
the previously saved V7/migration/timer plan. Diagnostic rejection retains the
completed freeze. No automatic paper/live deployment. Failure retains checkpoints
and paused competitors. Evidence lives under the repair validation root above.

CLI and hourly watcher now select r5. Existing open CLI processes need restarting.
Read [CURRENT_STATE](../CURRENT_STATE.md) for receipts and selected configuration;
read [TODO](../../TODO.md) for the active task. Preserve unrelated dirty work.
