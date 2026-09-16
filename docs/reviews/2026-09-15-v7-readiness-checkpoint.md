# V7 readiness checkpoint — September 15, 2026

**Historical early checkpoint.** Both September 14 option files were later
captured (8,284/8,284 base captures). The user then moved the research start to
March 15, 2022. Use the current [feature and freeze audit](2026-09-15-v7-feature-and-freeze-audit.md)
and [date-migration review](2026-09-15-v7-march15-start.md) for active status.
The counts and incomplete adapters below describe the earlier checkpoint.

## Acquisition result

Base acquisition finished at 07:20:34 UTC with **8,282/8,284** completed tasks,
two failures and **52.516 GB** charged against the shared 250 GB decimal cap.
No workers or reservations remain. All 5,424 stock tasks have receipts:
2,712 raw and 2,712 all-adjusted; 270 responses are observed empty. These
counts were read from completed receipts, not inferred from worker success.
Empty responses still need listing/alias and provider-coverage investigation.
The 270 empty captures represent **135 symbol/year pairs across 62 symbols**,
not 270 missing tickers. Every one of the 452 fetch symbols has some data.
See the [ticker list](../specs/v7-tickers-20260915.txt) and
[empty-year breakdown](2026-09-15-v7-empty-stock-years.md).

Option day aggregates and minute aggregates each have 1,429/1,430 sessions.
Both missing files are September 14, 2026. Direct provider HEAD requests
returned 404 during the September 15 market session. V6's minute-context
refresh is blocked by the same missing minute file. The fixed research end
is unchanged, and acquisition remains incomplete until these are captured.

## Coding and admission

Implemented: full planning parameter catalog; bounded quota/receipts;
calendar-aware 1/5/15/30-minute aggregation; shared MA computation; bounded
quote-request unions and capture/reuse; immutable Arrow/Parquet and NumPy/Zarr
stores; component and 64-MA-variant/timeframe working-set pilots.

Not complete: all other strategy adapters, complete causal feature integration,
historical PIT membership/listing/alias and price-vintage coverage, full
outcome-independent execution quote requests/captures, quote-based labels and
shared cash accounting, frozen purged walk-forward folds and full-pipeline
correctness/resource pilots. The tiny historical quote pilot establishes
access/reuse only. Option trade aggregates do not provide bid/ask execution.

## Recommended order before the long campaign

1. Finish the two provider files and audit stock/session/alias/listing/raw-
   adjusted coverage and every feature dependency. Classify the 270 empties;
   do not invent pre-listing history or claim a current list is survivorship-free.
2. Complete all strategy/timeframe and feature adapters with causal availability,
   prefix invariance and frozen/batch parity. Retain the explicitly deferred
   external Pine-comparison status; do not silently change that decision.
3. Generate outcome-independent quote requests, deduplicate, estimate retained
   storage within the remaining budget, and capture/validate all required
   entries, holding marks, exits and rolls. A full inventory may exceed the
   remaining allocation; measure rather than assume capacity.
4. Audit actual 1–9 DTE, quote timing, spread/costs, rolls, expiry, missing/stale
   quote rejection and portfolio cash/mark reconciliation on real samples.
5. Declare and seal proposal optimization/training/validation/test horizons,
   purging, embargo, baselines, gates and source/runtime/data hashes before
   optimization or model selection. Inspected dates remain revalidation.
6. Pass representative complete end-to-end and four-worker resource pilots,
   including restart/resume, while protecting the V6 paper producer. Only then
   admit the full freeze/build/train sequence.

Operational priority alongside preparation: restore V6 fresh context after
provider publication, verify its next accepted cycle and delivery, and enable
the separate V6 dashboard evidence journal. That forward evidence is useful
for first-week review; it does not establish V7 historical readiness.

Further model complexity, GPU scaling and broad worker increases can wait
until these data/execution/correctness gates pass. No V7 full-universe freeze,
build or training has started.
