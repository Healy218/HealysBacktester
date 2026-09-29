# V7 evening continuation — September 29, 2026

The user selected steps 3–4 after the paper/V6 recovery: resume V7 acquisition,
review held references, bind new indexes and replay actual pending paths.
This authorizes a bounded evening run alongside V6; gate **7-3 remains open**.
[Dated observation and artifact hashes](2026-09-29-v7-evening-continuation.json).

## Capture and continuation

`healys-v7-frontier-evening-20260929.service` started at 18:12:24 Central with
two autosized workers, 1.5/2-GiB memory high/max, CPU 100%, no swap and a two-hour
budget. It reuses verified packs and the unchanged source-bound frontier.
At 18:42, 86,424/109,825 windows were complete, with no new batch failures.

`healys-v7-evening-continuation-20260929.service` started at 18:30:47 Central;
its observed phase is waiting for capture. The separate wrapper has a five-hour
overall budget, up to two 30-minute missing-batch retries, then up to two hours
of new pending replay and 30 minutes of original discovery if budget remains.
Each pass seals a fresh quote index. Replay consumes only a verified published
index receipt. Its service has 3/4-GiB high/max, CPU 100%, Nice 15, no swap.
Replay uses one autosized worker and checks 6-GiB available-memory / 20-GB disk
reserves; capture retains its own quota/floor/inflight write reservations.
Original discovery retains its frozen inputs and ledger; new pending replay
writes to a separate epoch. These jobs cannot establish full coverage by launch.

## References and exact approval

The completed 1,985 held-reference inventory has 1,979 standard detail responses.
The six detail 404s received both dated alternate-list queries. Exact unmodified
list rows admit GME220722C00155000 and GME220722P00155000 on July 22, 2022.
Their receipt hashes and list provenance remain distinct from the raw detail 404s.

The user explicitly approved four remaining exact research-path exclusions:
GME220729C00155000 and GME220729P00155000 on July 22, 2022;
GPS240823C00024500 and GPS240830C00024500 on August 22, 2024.
The GPS queries returned GAP contracts, which were not substituted for GPS.
[Approval](2026-09-29-v7-held-reference-exclusion-approval.json) binds the exact
proposal hash. The selected compiled policy totals 10,835 pairs, preserving
all 10,831 previous pairs and original evidence. No calendar or terms change.

Selected admission is `v7-held-reference-admission-20260929-r1`; earlier r0 is
preserved but not selected. `v7-reference-epoch-20260929-r0` unions 2,225,829 raw
contract/date records without rewriting provider responses. Its separate reader
applies the two exact admissions. Future actual held dates can still add requests.

## Checkpoints, replay and validation

Under exclusive locks, the planner preserved database/journal preimages and let
SQLite recover both interrupted original databases. A zero-byte per-security
progress file was archived without inventing counts. All source ledgers remain;
recovery images and the initial incomplete planner transaction are preserved.

`v7-pending-replay-plan-20260929-r0` freezes 251,983 actual pending cohorts across
93 securities: 1,150,547 cohort/target groups, 21,624,449 horizon/target members.
Replay retains each selected cohort's full original membership and only targets
with actual missing requests; this is not a new full-universe capture envelope.

The stopped AAPL pilot used a sealed observation index and new reference epoch.
It covered three cohorts / 20 horizon-targets (25 weighted proposal targets),
retained 15 buckets / three payloads and emitted two further actual requests.
All 20 outcomes remain capture-incomplete; none is a completed numerical label.
Independent per-horizon execution matched all 20 reconstructed results exactly.
The audit initially omitted restoring target-specific selection IDs from shared
payloads; it now follows the existing reconstruction contract. Worker outputs
needed no change. This small pilot does not validate all 21.6 million members.

37 focused tests passed covering reference admission, pending membership,
cohort reconstruction, recovery, reviewed references/exclusions and payload sharing.
Both admitted GME records were read back through the new epoch reader. Shell
syntax validation passed. The original frozen worker/capture/V6 sources are unchanged.

## Operations and storage

V6 remains running from 17:31:19 Central: 114/449 symbols at 18:42, zero reported
errors; training has not started. Last service readback showed ~3.61-GiB peak.
Internal free space is about 86 GiB, MRHA about 693 GiB. No Steam files or bulk
data moved. Large raw inventories/checkpoints stay in their existing stores;
these changes do not claim disaster-proof backup of all research artifacts.

Inspect `v7-evening-continuation-20260929-r0/progress.json` for phase and
`selected-replay.json` once present for the exact quote index/policy/campaign.
Inspect terminal receipts and service journals before treating a phase as complete.
Reconcile newly discovered requests, provider failures and storage before gate closure.
