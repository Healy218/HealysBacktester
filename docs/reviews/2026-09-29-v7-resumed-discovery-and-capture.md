# V7 7-3 recovery and actual-input capture — September 29, 2026

The user explicitly selected resuming V7 after the V6 worker configuration change,
without waiting for V6 catch-up/training. Gate 7-3 remains open. Completed entry
capture, original reference capture, and gates 7-1/7-2 remain complete.

## Completed preparation and preserved evidence

The planner resumed its original source-bound checkpoint and completed all 591
securities in 486.88 seconds, reconciling 793,394,264 original proposals into
328,386,847 distinct execution horizons. Its separate compactor only removes
verified equivalent scratch copies after sealed publication.

The two empty-index failures, BBG000BCQ6J8 and BBG000BF8TF5, have verified zero
proposals, jobs and selections. The new controller records no-proposal receipts
without inventing quotes, paths or numerical labels. Nonempty demand still fails
closed when capture evidence is absent.

The original wave worker and all bound replay sources are unchanged. A separate
recovery controller binds the old campaign declaration and continues its existing
wave directories. Its aggregate guard uses live free space, a 10-GB floor and
512 MiB of pending-write reserve per worker; the frozen worker's per-wave guards
remain. Original parent progress was archived then marked stopped with a successor.
Both interrupted wave progress files were reconciled under locks. SQLite recovered
their rollback journals before request extraction; before/after provenance and
committed request content are retained in the sealed snapshot.

Snapshot `v7-recovery-frontier-20260929-r0` froze 112,118 committed pending rows
from 93 waves (six more than the earlier progress-file sum), preserving security
links and original request records. Subtracting existing quote coverage and taking
the exact union yields 109,825 missing quote windows and 1,985 dated-reference
requests. Mutable source database hashes are labeled observations; downstream
capture binds the immutable extracted snapshot, allowing discovery to continue.

## Executing services and dated results

[Observation at 12:52 Central](2026-09-29-v7-resume-observation.json):

- Discovery: two autosized workers, 5/6-GiB memory high/max, CPU 200%, no swap;
  no recorded worker failures. Original wave databases continue to accumulate.
  The controller's discovered count covers its current traversal; inspect all
  wave receipts for the retained global census while that traversal is incomplete.
- Quote capture: four autosized workers, 5/6-GiB high/max, CPU 200%, no swap;
  61,488/109,825 windows and 2,562 immutable packs complete. 284 batch attempts
  returned HTTP 502; these are failures, not coverage or new exclusions.
- The retry service waits for the initial capture service to stop, then reuses all
  completed packs and retries only missing batches for up to three passes. Every
  pass archives the terminal receipt and creates a new immutable combined index.
  No retry overlaps the original capture; all retries retain the same snapshot.
- Discovery/capture stop dispatching at 15:00 Central and drain active work before
  V6's 15:45 timer. Larger V6 limits are not a reason to extend V7 into that window.
  Long provider calls or index finalization still require exit-receipt observation.

Actual initial service readback: discovery approximately 5.0 GiB peak, quote
capture approximately 0.58 GiB peak. These are dated observations, not full-run
resource proofs. Neither restarted process status nor downloaded windows closes
execution coverage or 7-3.

## Held-reference results

All 1,985 exact requests across 84 securities were captured and independently
audited: 1,979 standard and six HTTP 404 detail responses; retained packs total
2,557,778 bytes. None of these requests was already present in the old reference
index. The new audit preserves the actual held-frontier scope rather than calling
this an entry-plan result.

Both exact alternate-list queries were captured for each of the six missing pairs.
The recovery completed 12 queries and found exact matches in two queries. Those
rows need admission review before constructing the next combined reference epoch;
the remaining unknowns need their own evidence-backed disposition. No exclusions
were added. The existing finite 10,831-pair policy remains unchanged.

Missing-detail pairs: GME220722C00155000, GME220722P00155000,
GME220729C00155000 and GME220729P00155000 on 2022-07-22;
GPS240823C00024500 and GPS240830C00024500 on 2024-08-22.

## Selected locations and validation

All following state roots are under `nn_meta/validation/`:

- Queue: `v7-full-execution-plan-20260928/` (591 sealed jobs).
- Replay controller: `v7-execution-recovery-20260929-r0/`; original waves remain
  under `v7-execution-campaign-20260928-r1/waves/`.
- Request snapshot: `v7-recovery-frontier-20260929-r0/`.
- Quote controller: `v7-frontier-capture-20260929-r0/`; raw packs under
  `nn_meta/data_v7/execution-recovery-20260929-r0/`.
- Quote index: only consume the sealed path in the controller's
  `index-receipt.json`; initial target is `v7-frontier-quote-index-20260929-r5`,
  subsequent retry indexes include their invocation timestamp/pass. A target
  filename before publication is not an available index.
- Held references: `v7-held-reference-demand-20260929-r0/`,
  `v7-held-reference-campaign-20260929-r0/`,
  `v7-held-reference-reconciliation-20260929-r0/`, and
  `v7-held-reference-recovery-20260929-r0/`. Raw reference and alternate packs
  use corresponding held-reference campaign/recovery names under `nn_meta/data_v7/`.

Twenty-one focused tests passed. Tests cover reference/quote separation in the
snapshot, overlap subtraction, stable extracted provenance after source updates,
no dropped batch tail, zero-demand admission, false-empty rejection, and live
write reserves, plus existing execution queue/frontier checks. Shell syntax and
Python compilation passed. The full V6 source contract still matches all 74 hashes.

Next: observe the bounded capture and retries; review recovered references; bind
new quote/reference epochs and replay actual remaining paths. Capture additional
requests from later stopped checkpoints, reconcile provider/storage/exclusion
coverage, then assess 7-3 closure against its full declared evidence.
