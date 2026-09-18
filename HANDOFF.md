# Handoff — V7 item 6-1: authorized no-event coverage consumed

## Instruction and settled decisions

Continue coding the seven-item sequence in [TODO](TODO.md), update documentation
and notify the user when all remaining tasks are done. **6-1 remains open; 6-2
through 6-7 remain queued.** Do not equate this milestone with V7 readiness.
Preserve V6 operation and unrelated dirty work; no blanket staging or reset.

Both admission questions are settled; do not ask again:

1. Matching ordinary provider terms are accepted as historical reconstruction,
   applied only from the effective session; publication remains unverified.
   Active policy: `docs/specs/V7_ORDINARY_ACTION_ADMISSION_20260917.json`.
2. The user explicitly accepted the documented provider-union no-event
   reconstruction assumption after all applicable conflicts are resolved.
   Active policy: `docs/specs/V7_NO_EVENT_ADMISSION_20260917.json`.
   Each consumer retains the assumption and completeness_verified=false.

Neither decision admits unknown identities, unresolved complex actions, stock
entitlements/payment clocks or option deliverables.

## Completed milestone

The production proposal builder now requires source-bound action coverage,
checks exact required dates/tickers/events and preserves both assumptions in
feature declarations. Undated pending records conservatively block affected
histories; dated pending records block applicable dates through known aliases.
Every original provider record must have exactly one treatment.

Finite exact-date reviews distinguish 45 cash groups /90 original records for
unrelated B, FB, FIG, GOLD and SPCX ticker reuses. These are relevance treatments,
not new universe exclusions or inferred successors.

Two named acquisitions repaired missing inputs: GAP raw 2025–2026 observations
and a 45-ticker Alpaca process-date tail for already effective cash events.
The latter queries scheduled process/payment dates through December 29 without
changing the September 14 effective-date scope. It adds 48 in-scope original
records; revised existing IDs are rejected.

Current action total: **4,481 events** =4,462 reconstructed (4,373 cash /89
splits) +19 publication-reviewed events, including 18 SPY distributions. All
prior 4,433 complete event objects remain unchanged. Original-record partition:
**10,428 =8,964 compiled +90 unrelated +1,374 pending**.

The full history retains 667,239 rows /591 securities /1,129 sessions /598 spans.
425 GAP sessions are restored; the other 666,814 rows remain unchanged.
Observed rows: 614,564; listed zero-observation rows: 43; no selected source:
52,632. Eligible identity mismatches remain 162. Coverage admits **579,160**
history sessions: 574,811 assumed no-event and 4,349 compiled-event sessions.
35,447 sessions remain blocked by actions; 52,632 by identity. All held-position
admission remains false.

Independent verification passes all 4,481 numerical and unchanged-prefix checks
(maximum absolute return error 1.24e-15), and the actual SPY proposal-input and
saved feature path retains both assumptions. Full suite: **2,070 tests +18
subtests passed**, 19 warnings, 128.77 seconds. A full-grid comparison caught
one old routing candidate count being lost in supplementation; the repaired
`-r2` outputs preserve it and have a regression test. Earlier outputs remain
superseded, not relabeled.

[Detailed evidence and limitations](docs/reviews/2026-09-17-v7-action-coverage.md).

## Current immutable artifacts

Under `nn_meta/validation/`:

- History: `v7-security-history-20260917-gap-r2`.
- Inventory: `v7-action-inventory-20260917-tail`.
- Actions: `v7-ordinary-actions-20260917-tail-gap-r2`.
- Unrelated records: `v7-other-instrument-actions-20260917-tail-gap-r2`.
- Coverage: `v7-action-coverage-20260917-tail-gap-r2`.
- Verification: `v7-coverage-consumers-20260917`,
  `v7-coverage-feature-check-20260917-SPY`, `v7-coverage-tests-20260917`.
- Supplemental daily inputs: `v7-gap-daily-20260917/{2025,2026}`.

Under `nn_meta/data_v7/`: `gap-history-repair-20260917`,
`action-process-tail-20260917`, original `daily-identities-20260916` and
`start-20220315`. Earlier source routing, share-class, reviewed cash and lifecycle
artifacts remain unchanged. See the archived handoff for their full index.

Use `ordinary_actions.price_action` for envelopes; direct PriceAction loading
loses reconstruction fields. Pass `--action-coverage` to the production proposal
builder; supplementary raw roots must already be bound by selected daily inputs.
Producer source changes require new immutable artifacts, not receipt rewriting.

## Exact remaining 6-1 work

1. Resolve identity/lifecycle exceptions: 162 eligible mismatches across ATVI12,
   BLK22, CCL16, DISCA14, DKNG18, RKLB4, SGEN10, SIRI15, SWTX17, TWTR1, VMW5,
   X7, XOM21. Including zero-bar cases gives 172 distinct eligible exceptions.
   Actual changed share classes cannot use the previous same-share-class resolver.
2. Resolve **504 simple groups**: 358 unreviewed units/terms, 23 single-provider,
   57 combined-event, 44 mismatches and 22 matching identity/adjacent-continuity
   cases after unrelated ticker groups are separated. Missing currency/ADR units
   are not admitted just because numerical rates happen to match.
3. Resolve **213 complex records**, including 47 undated name-change records.
   Pure ticker changes need dated identity plus primary-notice review; process
   dates alone are not effective dates. These undated records block many known
   sessions, including restored GAP history. Actual mergers/spinoffs must retain
   executable successor/entitlement treatment rather than a chart-only factor.
4. Consume treatments in actual feature and held-position paths, including cash
   entitlements, payment/settlement, splits, lifecycle and option deliverables.
   Only full required-scope reconciliation closes 6-1. Never invent outcomes.

## Fixed scope and resources

March 15, 2022–September 14, 2026; Alpaca stocks/Massive options; no OTC;
BBBY/FRC/REV/SI exclusions without replacements. Preserve 20 families, 11,268
variant/timeframes, 222 columns, causal chronological folds, raw stock execution,
arithmetic option midpoint, separate costs, V7 12.5% premium stop, strategy exits,
ITM expiry exit 15 minutes before regular option close, funded physical fallback
and shared-capital limits. Active contract:
`docs/specs/V7_ACTIVE_INPUTS_20220315_OPTION_RISK.json`.
At most four outer workers /one inner thread; 100 GiB reserve; 250 GB cap.
Current shared quota: 63,056,260,023 bytes, zero reservations. Recheck before
acquiring another named necessary input; no broad collection campaign.

No full V7 dataset or trained model exists. Saved readiness remains
`v7-readiness-20260917-entry-demand.json` with three foundational passes and eight
substantive stages unpassed. Preserve uncommitted assembly modules and unrelated
V6 edits. This milestone makes no deployment or training launch.

Previous handoff: `handoff-history/HANDOFF-2026-09-17-before-no-event-coverage.md`.
