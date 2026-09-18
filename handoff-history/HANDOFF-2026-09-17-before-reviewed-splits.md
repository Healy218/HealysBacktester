# Handoff — V7 item 6-1: authorized dividend ledger implemented

## Instruction and settled decisions

Continue coding the seven-item sequence in [TODO](TODO.md), update documentation
and notify the user when all remaining tasks are done. **6-1 remains open; 6-2
through 6-7 remain queued.** Do not equate this milestone with V7 readiness.
Preserve V6 operation and unrelated dirty work; no blanket staging or reset.

All three admission questions are settled; do not ask again:

1. Matching ordinary provider terms are accepted as historical reconstruction,
   applied only from the effective session; publication remains unverified.
   Active policy: `docs/specs/V7_ORDINARY_ACTION_ADMISSION_20260917.json`.
2. The user explicitly accepted the documented provider-union no-event
   reconstruction assumption after all applicable conflicts are resolved.
   Active policy: `docs/specs/V7_NO_EVENT_ADMISSION_20260917.json`.
   Each consumer retains the assumption and completeness_verified=false.

3. The finite pre-tax stock-cash model is accepted for 4,337 existing events.
   Active policy: `docs/specs/V7_STOCK_CASH_LEDGER_ADMISSION_20260917.json`.
   Accrue entitled funded beneficial shares at ex-open; receivables add equity
   but not spendable cash; release at first regular open after pay date; zero
   modeled withholding/fees; broker posting remains unverified.

These decisions do not admit unknown identities, unresolved complex actions,
the other 55 compiled cash events or changed option deliverables.

## Completed milestone

The finite authorized stock-cash compiler seals **4,337 events /272 securities**,
with the other 55 cash events explicitly excluded. Original provider references,
source amounts, reconciled ex/record/pay dates, policy identity and release clocks
are retained. Current output is `v7-stock-cash-entitlements-20260917-r3`; the first
and r2 outputs predate final validation changes and remain historical.

PhysicalLedger now tracks funded beneficial quantity deltas from stock purchases,
exercise and sales. It accrues receivables before ex-session trading; cash release
is exactly once at the modeled regular open. Equity includes receivables;
entry/exercise funding cannot spend them. The portfolio schedules both events,
preserves entitlements after stock liquidation and remains incomplete while a
receivable is outstanding. Runtime rejects mistimed events, unsupported terms
and clocks outside captured settlement coverage before mutation.

Full finite census verification independently reconciles all 4,337 amounts,
source identities, approved dates and release opens. The already captured AAPL
May 5 quote funds a simulated 100-share purchase at $163.83. It reserves
$16,407.5745 including existing costs, settles May 9 with conservative availability
May 10, accrues $23 on May 6 and releases that cash May 13. Ending cash is
$83,615.4255 plus 100 retained funded shares. This is an accounting case, **not**
a completed strategy outcome, stock sale or held-mark replay.

The four-page original FINRA October 15, 2021 notice was rendered and visually
reviewed. Its 2022 calendar has 249 settlement days; all 46 original trade/date
pairs reconcile, including Juneteenth, Good Friday and the separate Columbus/
Veterans bank holidays. This calendar admits **2022 only**. Across 681 eligible
2022 events, the actual portfolio consumer with no inventory creates no dividend
income. No new acquisition was needed. 2023–2026 settlement calendars still need
original-source review; do not silently use a trading calendar for settlement.

Verification: `v7-stock-cash-verification-20260917`. Tests: cash-specific 28 passed;
full suite **2,131 tests +18 subtests passed**, 19 warnings, 163.96 seconds.
All compiler/verification/test processes completed with exit 0. Test receipt:
`v7-stock-cash-tests-20260917`.
[Cash ledger review](docs/reviews/2026-09-17-v7-stock-cash-ledger.md).

Earlier relevance milestone remains current: 4,481 chart actions, seven scoped
renames and 93 unrelated records; 586,830 history-admitted sessions. Full original
partition: 10,428 =8,964 cash/split +93 unrelated +7 rename +1,364 pending.
Action-blocked rows 27,777; identity-blocked 52,632. Cash implementation does not
change that feature-history coverage or admit full held-position histories.

## Current immutable artifacts

Under `nn_meta/validation/`:

- History: `v7-security-history-20260917-gap-r2`.
- Inventory: `v7-action-inventory-20260917-tail`.
- Price actions: `v7-ordinary-actions-20260917-tail-gap-r2`.
- **Unrelated records:** `v7-other-instruments-20260917-renames` (45 cash groups +3 renames).
- **Renames:** `v7-common-share-renames-20260917`.
- **Coverage:** `v7-action-coverage-20260917-relevance`.
- **Stock cash:** `v7-stock-cash-entitlements-20260917-r3`,
  `v7-stock-cash-verification-20260917` (includes the normalized 2022 settlement calendar).
- Prior relevance verification: `v7-relevance-consumers-20260917`, three
  `v7-relevance-feature-check-*` stores, `v7-relevance-tests-20260917`.
- Prior rename verification: `v7-rename-consumers-20260917`, six `v7-rename-feature-check-*`
  stores and `v7-rename-tests-20260917`.
- Prior verification: `v7-coverage-consumers-20260917`,
  `v7-coverage-feature-check-20260917-SPY`, `v7-coverage-tests-20260917`.
- Supplemental daily inputs: `v7-gap-daily-20260917/{2025,2026}`.

Under `nn_meta/data_v7/`: `unrelated-rename-notices-20260917`, `rename-notices-20260917`,
`gap-history-repair-20260917`, `action-process-tail-20260917`, original
`daily-identities-20260916` and `start-20220315`. Earlier primary, identity,
source-routing and lifecycle artifacts remain unchanged.

Use `ordinary_actions.price_action` for action envelopes. Use `--renames` when
rebuilding coverage, and `--action-coverage` in the production proposal builder.
Saved feature declarations retain consumed identity-event IDs. Supplementary raw
roots must be bound through selected daily inputs. Changed producers require
fresh immutable artifacts; earlier coverage outputs remain historical.
The stock portfolio handler accepts reviewed events through `physical.renames`;
this does not infer option symbol/deliverable changes.

## Exact remaining 6-1 work

1. Resolve identity/lifecycle exceptions: 162 eligible mismatches across ATVI12,
   BLK22, CCL16, DISCA14, DKNG18, RKLB4, SGEN10, SIRI15, SWTX17, TWTR1, VMW5,
   X7, XOM21. Including zero-bar cases gives 172 distinct eligible exceptions.
   Actual changed share classes cannot use the previous same-share-class resolver.
2. Resolve **504 simple groups**: 358 unreviewed units/terms, 23 single-provider,
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
   dates, splits, lifecycle and option deliverables.
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
Current shared quota: 63,057,207,992 bytes, zero reservations. Recheck before
acquiring another named necessary input; no broad collection campaign.

No full V7 dataset or trained model exists. Saved readiness remains
`v7-readiness-20260917-entry-demand.json` with three foundational passes and eight
substantive stages unpassed. Preserve uncommitted assembly modules and unrelated
V6 edits. This milestone makes no deployment or training launch.

Previous handoff: `handoff-history/HANDOFF-2026-09-17-before-stock-cash.md`.

Independent next review identified: 12 Massive split records use adjustment_type
stock_dividend. Ten appear to describe actual same-share splits (GOOG/GOOGL, GME,
TSLA, PANW, APH twice, ORLY, IBKR, CRWD); ENVX/OPEN may instead be warrants.
Do not map the type globally. Primary notices must establish exact ratios, dates,
shares and availability; no split-admission code or captures yet for this batch.
A separate diagnostic found only 64 one-per-provider exact cash matches with
Massive USD and Alpaca foreign=true (62 exact selected identities); the rest of
the 358 unreviewed-term groups are not resolved by removing a foreign flag.
No additional foreign-unit assumption has been proposed or authorized.
