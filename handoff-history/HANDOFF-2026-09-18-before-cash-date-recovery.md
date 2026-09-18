# Handoff — V7 item 6-1: cash extension and settlement schedule

## Goal, scope and settled decisions

The user directed finishing all dividends and the remaining handoff work so we
can move to step 2, with constrained disk capacity. Continue the seven TODO
items in order. **6-1 remains open; 6-2 through 6-7 are queued.** Do not call
this checkpoint dividend completion. Work on main; preserve unrelated V6
changes and untracked assembly files. Stage only owned paths.

Four decisions are settled; do not ask again:

1. Matching ordinary provider terms as effective-session reconstruction,
   publication unverified: `V7_ORDINARY_ACTION_ADMISSION_20260917.json`.
2. Provider-union no-event completeness after applicable conflicts resolve:
   `V7_NO_EVENT_ADMISSION_20260917.json`.
3. Original 4,337-event pre-tax funded-stock cash model:
   `V7_STOCK_CASH_LEDGER_ADMISSION_20260917.json`.
4. **The user accepted extending that same model to the original 528 remaining
   dividend groups as each passes amount, date and identity review.**
   `V7_REMAINING_STOCK_CASH_ADMISSION_20260917.json` binds its exact proposal.
   No further per-issuer model approval is needed within this scope. This does
   not waive unresolved terms/dates/identity or expand chart admission.

Policy/spec paths are under docs/specs. Cash still accrues on funded beneficial
shares at ex-open; its receivable adds equity but cannot fund spending. Release
at the first captured regular open strictly after reviewed pay date, zero modeled
withholding/fees, pro-rata fractions. Actual broker posting remains unverified.

## Completed checkpoint

36 additional price actions and held-cash entitlements: all 18 pending FCX and
all 18 pending SLB groups. FCX original dated issuer notices explicitly resolve
total base-plus-variable cash to $0.15 per common share. Their January 11, 2024
ex-event pays February 1, correcting an original conflicting February 5 record.
Four primary SLB quarterly notices resolve common-share terms/dates. The other
14 retain the existing matching-provider availability assumption after exact
common-share unit review: earlier primary witness, unchanged identity span,
unique providers, identical original USD amounts. No global foreign-flag waiver,
ADR conversion or gross/net rate reconciliation is implied.

Current totals: **4,527 price actions; 4,428 cash actions; 4,373 cash entitlements;
586,876 admitted history sessions.** The original 4,491 actions and 4,337 cash
entitlement objects are preserved unchanged. Original-record partition:
10,428 =9,079 action +93 unrelated +7 rename +1,249 pending records.

All 36 actual raw-minute feature boundaries pass: one 15-minute MA variant,
52 observations each, unchanged pre-event prefixes, cash price factors and
unchanged volume units. 667,203 other coverage rows remain unchanged. These
bounded stores are not the full step-2 features.

**The later settlement-year gap is resolved without new market-data downloads.**
The already captured original Alpaca calendar response includes documented
`settlement_date` for each trade date. `ReportedSettlementSchedule` consumes
this exact mapping, not a guessed business-date calendar. 1,212 mappings cover
January 2022–October 2026; all 1,210 with a captured subsequent availability
open verify, and the final two correctly fail beyond the calendar horizon.
All 46 independent FINRA 2022 table examples agree. The mapped dates retain
November 10, 2023 normal settlement, the May 2024 T+1 transition, and January 9,
2025 settlement despite the exchange closure. Broker posting and historical
calendar publication are not claimed.

The current schedule covers all existing cash releases (latest October 16,
2026). Fresh verification consumes all 4,337 original events and repeats the
captured funded AAPL $23 dividend case. Extension verification preserves those
objects and consumes all 4,373 events in the actual no-inventory portfolio
without creating cash. It inherits that same verified funded AAPL case; no
funded FCX/SLB fill, liquidation or completed strategy outcome was fabricated.

62 new focused tests pass. Full suite: **2,225 tests +18 subtests**, 19 warnings,
126.43 seconds, exit 0; receipt `v7-cash-calendar-tests-20260917`. The later
extension verification CLI was run successfully against actual artifacts after
that full-suite run. No training, deployment or V6 policy change.
[Checkpoint review](docs/reviews/2026-09-17-v7-cash-calendar-closure.md).

## Current immutable artifacts

All names below are under nn_meta/validation unless stated otherwise:

- History `v7-security-history-20260917-gap-r2`: 667,239 rows /591 IDs /1,129 sessions.
- Inventory `v7-action-inventory-20260917-tail`: 10,428 original records.
- **Actions `v7-cash-units-20260917`.** Parents `v7-primary-cash-20260917`,
  `v7-reviewed-splits-20260917` and `v7-ordinary-actions-20260917-tail-gap-r2` remain.
- Renames `v7-common-share-renames-20260917`; unrelated records
  `v7-other-instruments-20260917-renames`.
- **Coverage `v7-action-coverage-20260917-cash`.** Use --renames when rebuilding,
  and pass --action-coverage to the actual proposal builder.
- `v7-cash-consumers-20260917` plus 36 corresponding feature stores.
- **Cash `v7-stock-cash-extension-20260917`** and
  `v7-stock-cash-extension-verification-20260917` (4,373 events).
- **Settlement `v7-reported-settlement-20260917/settlement_calendar.json`.**
  Schema `v7-reported-stock-settlement-v1`, consumed by ReportedSettlementSchedule,
  not the old business-date SettlementCalendar constructor. This artifact also
  holds fresh original-cash/funded-AAPL verification.
- **Dividend census `v7-dividend-closure-20260917-r3`** with exact uncompiled and
  missing-held work lists. r1 predates corrected display of Alpaca payable_date;
  r2 predates the newly authorized held-cash extension. Use r3.
- Earlier split, stock split/mark, rename and cash checks remain historical
  evidence. Supplementary GAP daily `v7-gap-daily-20260917/{2025,2026}` remains
  required/bound to selected history; never substitute raw prices.

New primary source roots under nn_meta/data_v7: dividend-tables-20260917,
settlement-field-doc-20260917, cash-date-notices-20260917. Existing
slb-cash-notices-20260917 supplied four notices; other SLB attempts timed out.
Do not retry the investorcenter table repeatedly: all 18 SLB groups are resolved.

## Exact remaining work

**492 dividend review items remain, not 528:**

- 437 uncompiled cash groups: 328 unit/term, 47 combined, 34 mismatch,
  14 single-provider, 11 missing selected identities, 3 adjacent continuity.
- 55 already compiled cash events needing record/pay-date treatment. Their exact
  original dates/references are in census missing_held.json. Many are nominal
  weekend/holiday dates versus later business dates; do not globally choose
  either provider or blindly roll them. INTU's January 10, 2025 ex-date follows
  a January 9 closed-market record date and needs explicit special-date review.

**Next useful evidence already captured, not yet admitted:**
`cash-date-notices-20260917/ibm-cash-history` lists the 2023/2024 IBM nominal
payment dates, `target-cash-history` is the issuer May 20, 2026 dividend-history
PDF, and `pnc-20230703-dividend` explicitly states the August 5 nominal date
with next-business-day payment. Inspect original bytes; visually review the
Target PDF table before using it. No primary date-review integration for these
three sources has been coded yet. The model extension is already authorized;
add exact source-bound date reviews, not another policy question.

Remaining non-dividend 6-1 work is unchanged:

- 162 eligible identity exceptions across ATVI12, BLK22, CCL16, DISCA14, DKNG18,
  RKLB4, SGEN10, SIRI15, SWTX17, TWTR1, VMW5, X7, XOM21 (172 incl. zero-bar cases).
- 21 other simple groups (458 simple groups including the 437 cash groups),
  203 complex records including 37 undated name changes. ENVX/OPEN reported
  stock dividends may be warrants; never convert them globally into splits.
- Complete actual held lifecycle and remaining split/option-deliverable
  treatment. Current action-blocked sessions: 27,731; identity-blocked: 52,632.
  Full required-scope consumer reconciliation is still required to close 6-1.

## Storage and fixed scope

User reports roughly 230 GB project usage and cannot support another 100 GB per
step. Continue reusing existing captures and acquiring only named small missing
sources. Before bulk acquisition/full stores, forecast storage and establish
an explicit total-project budget; 250 GB acquisition is not a total disk cap.
This continuation added 3,401,154 acquisition bytes plus about 298 MiB derived
artifacts/consumer stores, not a new price archive. Current acquisition quota:
**63,071,664,529 bytes**, zero reservations. Recheck before acquiring more.
Preserve immutable historical artifacts; changed producers need new outputs.
At most four outer workers/one inner thread, 100 GiB reserve.

Scope remains March 15, 2022–September 14, 2026; Alpaca stocks/Massive options;
no OTC; BBBY/FRC/REV/SI exclusions without replacement; 20 families, 11,268
variants/timeframes, 222 columns; raw stock execution, option midpoint, separate
costs, V7 12.5% premium stop, strategy exits, ITM expiry exit 15 minutes before
regular option close, funded physical fallback/shared limits and causal folds.
`V7_ACTIVE_INPUTS_20220315_OPTION_RISK.json` remains active. No full dataset/model
exists. Readiness remains `v7-readiness-20260917-entry-demand.json`, three
foundational passes/eight substantive stages unpassed. GOALS reassessment remains
September 21 after a full operational V6 week; this checkpoint proves no edge.

Previous handoff: handoff-history/HANDOFF-2026-09-17-before-cash-calendar-closure.md.
