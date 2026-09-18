# Handoff — V7 6-1: recovered session and 48 cash-date resolutions

## Current direction and authorization

The user reported an overnight reset and asked to recover our place and continue.
The committed checkpoint was `086eb39` (36 FCX/SLB groups plus settlement mapping).
Eight additional IBM/TGT/PNC date cases had saved artifacts but uncommitted code;
the January 2025 closed-record-date exception and v2 lineage code were unfinished.
Recovered and verified that work, then added 40 primary date reviews from existing
captures. **6-1 remains open; 6-2 through 6-7 remain queued.**

Work on main; preserve the unrelated dirty V6 files, untracked V6 modules/reviews,
and V7 assembly files. Stage only owned paths. No V6 policy change or deployment,
new market-data acquisition, full dataset build or training occurred here.

Four admissions remain settled: ordinary-action reconstruction, provider-union
no-event completeness, original 4,337-event pre-tax stock-cash model, and its
finite extension to the original 528 remaining dividend groups as reviews pass.
Their JSON policies are under docs/specs, dated 20260917. Do not ask for another
per-issuer approval. No waiver of unresolved amount/date/identity terms is implied.
Cash accrues on funded beneficial shares at ex-open; receivables add equity but
cannot fund spending. Release at first captured regular open strictly after the
reviewed payable date; zero modeled withholding/fees; broker posting unverified.

## Completed checkpoint and verification

**4,421 cash entitlements; 4,527 price actions; 4,428 cash price actions;
586,876 admitted history sessions.** Price objects and history coverage are
unchanged. All original 4,337 cash objects, subsequent 36 FCX/SLB objects and eight
recovered IBM/TGT/PNC objects remain unchanged; 40 reviewed objects were added.

Current dated reviews: `V7_CASH_DATE_REVIEWS_20260917.json` (eight) and
`V7_CASH_DATE_REVIEWS_20260918_R2.json` (40) under docs/specs. The intermediate
20260918 file/artifact contains 39 reviews before the last MPWR PDF inspection;
retain it as history, use R2 for current work. Source bytes are already in
`nn_meta/data_v7/cash-date-notices-20260917`. PDFs were visually reviewed; MPWR's
PDF starts with whitespace before `%PDF`, so a strict prefix check missed it.

INTU/ORCL/MA retain January 9, 2025 record dates with January 10 ex-dates, explicitly
supported by their issuer notices plus Nasdaq ETA2025-1. The compiler and runtime
accept only the finite exception and pinned original notice with a closed Jan 9
calendar. No global chronology relaxation. PNC explicit next-business-day clauses
remain distinct from other issuers' nominal weekend/holiday dates.

All 4,421 events pass actual source/amount/identity/clock/settlement verification;
the real no-inventory portfolio consumes them without creating cash. The prior
captured funded AAPL case is retained. New funded exception tests use fixtures,
not historical INTU/ORCL/MA fills. Full held history is not admitted.

Full suite: **2,246 tests +18 subtests**, 19 warnings, 129.84 seconds, exit 0.
Receipt `nn_meta/validation/v7-recovery-tests-20260918`; 21 new focused tests pass.
Actual compile, verification and census CLI runs also pass.
[Evidence review](docs/reviews/2026-09-18-v7-cash-date-recovery.md).

## Current immutable artifacts and commands

All artifact names below are under nn_meta/validation:

- History `v7-security-history-20260917-gap-r2` (667,239 rows /591 IDs /1,129 sessions).
- Inventory `v7-action-inventory-20260917-tail` (10,428 original records).
- Actions `v7-cash-units-20260917` (preserves prior price actions).
- Coverage `v7-action-coverage-20260917-cash`. Pass --renames when rebuilding;
  pass --action-coverage to actual proposal builds.
- Renames `v7-common-share-renames-20260917`; unrelated
  `v7-other-instruments-20260917-renames`.
- **Cash `v7-stock-cash-dates-20260918-r2`.**
- **Cash verification `v7-stock-cash-dates-verification-20260918-r2`.**
- **Dividend census `v7-dividend-closure-20260918-r2`.** Its uncompiled.json and
  missing_held.json are the exact current work lists.
- Settlement `v7-reported-settlement-20260917/settlement_calendar.json`:
  ReportedSettlementSchedule, 1,212 direct Alpaca mappings through October 2026,
  all 46 independent FINRA checks agree. Never infer settlement from trading days.
- Original 4,337-event baseline `v7-stock-cash-entitlements-20260917-r3`;
  original funded-case verification `v7-reported-settlement-20260917`.
- Prior split/rename/feature-boundary evidence remains valid history.
  Supplemental GAP daily `v7-gap-daily-20260917/{2025,2026}` remains required.

Use the **v2** scripts: `compile_v7_cash_date_reviews_v2.py`,
`validate_v7_cash_extension_v2.py`, `audit_v7_dividend_closure_v2.py`.
`producer_versions.py` binds exactly two old producer hashes to byte-identical
snapshots in `nn_meta/v7/producer_snapshots/`; current code is bound separately.
Unknown changed sources fail. Historical receipts were not rewritten. Older
CLIs can correctly reject the changed current stock_cash producer.
Trading calendar: `nn_meta/data_v7/exchange-calendar-20260916/calendar.json`.
The review and saved inputs.json files identify all other CLI inputs.

## Exact next work

**444 dividend review items remain: 437 uncompiled cash groups +seven date cases.**

Seven dates: CMA 2023-09-14, CMA 2023-12-14, FIX 2023-05-17,
QQQ 2023-12-27, QQQ 2024-03-18, PG 2024-04-18, RILY 2024-05-23.

1. Resolve exact CMA/FIX payment evidence and QQQ March distribution evidence.
   Reuse existing captures first; any new acquisition should be named small
   documents, not a broad crawl.
2. QQQ December has saved `qqq-202312-occ` (OCC #53847): extracted text describes
   special cash and option strike adjustment. Visually inspect the full PDF and
   integrate its separate semantics rather than claim ordinary cash treatment.
3. PG captured `pg-20240409` says payable on or after May 15; RILY `rily-20240515`
   says on or about June 11. Do not silently convert qualified dates to exact
   posting. Resolve terms within the authorized model; record a genuine policy
   extension explicitly if still needed.
4. Continue the 437 groups: 328 unit/term, 47 combined, 34 mismatch,
   14 single-provider, 11 selected-identity, three adjacent-continuity.

Non-dividend 6-1 blockers persist: 162 eligible identity exceptions across
ATVI12, BLK22, CCL16, DISCA14, DKNG18, RKLB4, SGEN10, SIRI15, SWTX17, TWTR1,
VMW5, X7, XOM21 (172 including zero-bar cases); 21 other simple groups;
203 complex records including 37 undated names; complete stock/option held
lifecycles and option-deliverable treatment. ENVX/OPEN reported stock dividends
may be warrants; do not convert globally to splits. Action-blocked sessions
27,731; identity-blocked 52,632. Only full required-scope consumer reconciliation
can close 6-1, not a selected-symbol test or this date batch.

## Storage and scope

No new download bytes this session. New September 18 date/census/test artifacts
are about 49.65 MiB including immutable intermediate outputs. Observed acquisition
quota **68,907,498,073 bytes**, zero reservations; free disk 458.69 GiB. The earlier
63.07 GB handoff figure was stale; do not attribute that increase to this session.
User reported roughly 230 GB project usage and constrained storage. Before bulk
acquisition/full stores, forecast storage and establish the total-project budget;
250 GB acquisition is not the total-project cap. Preserve old artifacts and
100 GiB free reserve. At most four outer workers, one inner thread.

Fixed scope: March 15, 2022–September 14, 2026; Alpaca stocks/Massive options;
no OTC; BBBY/FRC/REV/SI exclusions without replacement or reranking; all 20
families, 11,268 variants/timeframes, 222 columns. Raw stock execution, arithmetic
option midpoint with separate costs, V7 12.5% premium stop, strategy exits,
ITM expiry exit 15 minutes before regular option close, funded physical fallback,
shared capital limits, causal folds. Active inputs remain
`V7_ACTIVE_INPUTS_20220315_OPTION_RISK.json`.

No full V7 dataset/model exists. Readiness remains the September 17 entry-demand
gate (three foundational passes/eight substantive stages unpassed). GOALS review
is due September 21 after a full V6 operational week; no trading-edge claim.

Previous handoff: handoff-history/HANDOFF-2026-09-18-before-cash-date-recovery.md.
