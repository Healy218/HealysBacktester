# Handoff — V7 item 6-1: finite splits and funded stock units

## Instruction and settled decisions

Continue coding all seven items in TODO.md, update documentation and notify the
user when all are complete. **6-1 remains open; 6-2 through 6-7 remain queued.**
Do not equate a component milestone with readiness. Work on main, preserve V6
operation and unrelated dirty/untracked work; stage exact owned paths only.

Three user approvals are settled; do not ask again:

1. Matching ordinary provider terms as effective-session reconstruction,
   publication unverified: `V7_ORDINARY_ACTION_ADMISSION_20260917.json`.
2. Provider-union no-event completeness after applicable conflicts resolve,
   completeness unverified: `V7_NO_EVENT_ADMISSION_20260917.json`.
3. Finite 4,337-event pre-tax funded-stock cash model: accrue at ex-open, equity
   receivable separate from spendable cash, release first regular open after pay
   date, zero modeled withholding/fees, broker posting unverified:
   `V7_STOCK_CASH_LEDGER_ADMISSION_20260917.json`.

All policy files are under docs/specs. The 55 excluded cash events, unknown
identities, complex actions and changed option deliverables remain separate.

## Completed milestone

Ten same-share split groups previously blocked by Massive's stock_dividend type
now have exact primary reviews: GOOG/GOOGL20:1 (2022-07-18), GME4:1 (2022-07-22),
TSLA3:1 (2022-08-25), PANW3:1 (2022-09-14), APH2:1 (2024-06-12 and 2026-09-03),
ORLY15:1 (2025-06-10), IBKR4:1 (2025-06-18), CRWD4:1 (2026-07-02). Eight captured
OCC first-page notices were visually reviewed; GME/CRWD issuer releases confirm
the remaining terms. Source bytes, hashes, original references and conservative
publication clocks are retained in `V7_DIVIDEND_SPLIT_REVIEWS_20260917.json`.
ENVX/OPEN stock-dividend records remain unresolved; never globally remap the type.

The combined action set preserves all 4,481 existing objects and adds ten:
**4,491 events**. Original partition: 10,428 =8,984 action +93 unrelated +7 rename
+1,344 pending records. Coverage admits **586,840 sessions** (+10), with 667,229
other rows unchanged; 27,767 action-blocked and 52,632 identity-blocked remain.
Ten actual raw-minute two-day feature boundaries passed (52 observations each,
one 15-minute MA variant), including unchanged pre-event prefixes and correct
price/volume units. These are bounded consumer checks, not full feature stores.

The stock ledger and portfolio now consume `physical.splits` at the effective
open. Funded inventory and pending share deliveries change units; cash payables,
settlement dates and existing dividend receivables retain their amounts. Later
cash entitlements use updated beneficial-share deltas. Open options fail before
mutation and still need exact contract/deliverable treatment.

Real TSLA accounting case: buy ten shares August22,2022 at captured $875.96 ask,
reserve $8,772.7394 including existing costs, settle August24 with August25
availability. Split yields 30 funded shares and $91,227.2606 cash. A raw $302.19
bid at 13:31 UTC August25 gives $100,292.9606 equity. This retains stock: no
liquidation or strategy outcome was fabricated. Two two-minute quote captures
contain 6,630 and 6,918 records; exact-date identity/size sources are bound.

Fresh cash verification after ledger changes still reconciles all 4,337 events,
46 FINRA 2022 trade/settlement pairs, 681 no-inventory portfolio events and the
funded AAPL $23 dividend case. The cash compiler r3 is unchanged; earlier cash
verification is historical because its producer hash predates stock split support.
Only the 2022 settlement year is normalized (249 days); later years stay open.

Focused tests:60 passed. Full suite: **2,163 tests +18 subtests**, 19 warnings,
171.02 seconds, exit0. Test receipt `v7-split-tests-20260917`. All capture,
compiler, consumer and verification processes are closed/completed. No training
or deployment. [Review](docs/reviews/2026-09-17-v7-reviewed-splits.md).

## Current immutable artifacts

Under nn_meta/validation:

- History `v7-security-history-20260917-gap-r2` (667,239 rows /591 IDs /1,129 sessions).
- Inventory `v7-action-inventory-20260917-tail` (10,428 original records).
- **Price actions `v7-reviewed-splits-20260917`.** The earlier
  `v7-ordinary-actions-20260917-tail-gap-r2` remains its unchanged parent.
- Renames `v7-common-share-renames-20260917`; unrelated records
  `v7-other-instruments-20260917-renames`.
- **Coverage `v7-action-coverage-20260917-splits`.** Earlier relevance coverage
  remains historical. Use --renames when rebuilding and --action-coverage in
  the actual proposal builder.
- Split checks `v7-split-consumers-20260917` plus ten corresponding
  `-features-SYMBOL-DATE` stores; `v7-stock-split-verification-20260917`.
- Cash `v7-stock-cash-entitlements-20260917-r3`;
  **`v7-stock-cash-verification-20260917-splits`** includes reviewed settlement
  normalization and fresh ledger verification.
- Existing rename/relevance/coverage consumer checks remain historical evidence.
- Supplementary GAP daily `v7-gap-daily-20260917/{2025,2026}` remains bound to
  selected history. Use declared raw supplements; do not replace prices.

New nn_meta/data_v7 roots: `dividend-split-notices-20260917`,
`split-stock-reference-20260917`, `split-stock-quotes-20260917`.
Retain failed issuer download partials; exact fallback sources are reviewed.
Current quota **63,064,011,570 bytes**, zero reservations, of 250GB; recheck before
new named acquisition. Disk reserve 100GiB. At most four outer workers/one thread.
Changed producers require new immutable artifacts; never overwrite/relabel.

## Exact remaining 6-1 work

1. Resolve identity/lifecycle exceptions: 162 eligible mismatches across ATVI12,
   BLK22, CCL16, DISCA14, DKNG18, RKLB4, SGEN10, SIRI15, SWTX17, TWTR1, VMW5,
   X7, XOM21. Including zero-bar cases gives 172 distinct eligible exceptions.
   Actual changed share classes cannot use the previous same-share-class resolver.
2. Resolve **494 simple groups**: 348 unreviewed units/terms, 23 single-provider,
   57 combined-event, 44 mismatches and 22 matching identity/adjacent-continuity
   cases after unrelated ticker groups are separated. Missing currency/ADR units
   are not admitted just because numerical rates happen to match.
3. Resolve **203 complex records**, including 37 undated name-change records.
   Pure ticker changes need dated identity plus primary-notice review; process
   dates alone are not effective dates. GAP's pure rename and Barrick's separate
   unrelated AMRK→GOLD record are now resolved. Actual mergers/spinoffs must retain
   executable successor/entitlement treatment rather than a chart-only factor.
4. Consume treatments in actual feature and held-position paths, including the implemented finite cash
   entitlements with remaining 2023–2026 settlement calendars, the 55 excluded cash
   dates, remaining splits, lifecycle and option deliverables.
   Only full required-scope reconciliation closes 6-1. Never invent outcomes.


## Fixed scope and continuation

March15,2022–September14,2026; Alpaca stocks/Massive options; no OTC; BBBY/FRC/REV/SI
exclusions without replacement. Retain 20 families,11,268 variants/timeframes,
222 columns, causal folds, raw stock execution, arithmetic option midpoint,
separate costs,V7 12.5% premium stop,strategy exits,ITM expiry exit15minutes before
regular option close,funded physical fallback and shared limits. Active contract:
`docs/specs/V7_ACTIVE_INPUTS_20220315_OPTION_RISK.json`.

No full V7 dataset/model exists; readiness remains
`v7-readiness-20260917-entry-demand.json` (three foundational passes/eight
substantive stages unpassed). Preserve untracked assembly modules and all unrelated
V6 changes. Previous handoff:
`handoff-history/HANDOFF-2026-09-17-before-reviewed-splits.md`.

Next exact gaps include later settlement calendars, foreign cash units, lifecycle
identities and option deliverables. FINRA's original 2023 annual schedule conflicts
with later DTCC normal processing on November10; do not infer from federal holiday
rules. January9,2025 trading was closed but settlement open. Prior DTCC original
URLs returned404 and direct OCC calendar URLs403; search text alone was not
admitted. Only two still-unresolved Massive stock_dividend records remain (ENVX,
OPEN), which may involve warrants. A diagnostic in
`/tmp/v7-foreign-matching-groups.json` identifies64 numerical cash matches with
MassiveUSD/Alpacaforeign=true (62 selected identities,2CCLunknown); numerical
agreement alone does not establish ADR units or gross/net treatment.
