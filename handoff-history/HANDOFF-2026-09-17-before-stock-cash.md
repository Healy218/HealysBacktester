# Handoff — V7 item 6-1: unrelated rename records reconciled

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

Three additional finite relevance reviews resolve AMRK→GOLD (Gold.com),
BNZI→PARA (Banzai) and SPCX→SPCK (SPAC ETF) as unrelated to the scoped Barrick,
Paramount and SpaceX securities. Primary effective-date notices and original
adjacent composite/share-class identities identify both unrelated rename legs;
a distinct captured scoped witness prevents ticker-only inference. No new
exclusion or successor/entitlement relation is created.

Coverage now combines treatment references against the original inventory,
independent of artifact build order. Current partition: **10,428 =8,964 compiled
cash/split +93 unrelated +7 scoped rename +1,364 pending records**. Cash/split
events remain 4,481; the seven previous scoped rename treatments remain intact.

Admitted history rises by 2,026 to **586,830 sessions** (582,440 no-price-event,
4,390 compiled-price-event). Action-blocked rows: 27,777; identity-blocked:
52,632. The other 663,852 rows outside the three affected scoped securities have
unchanged coverage. Raw observations, selected identities, membership and all
previous chart events are unchanged.

Real two-session proposal-loader/15-minute feature checks pass B (780 minutes),
PARA (778), SPCX (780), each with 52 observations. Barrick now correctly consumes
its previously reviewed GOLD→B identity event. Earlier six scoped-rename checks
remain historical evidence. No full feature production or held market replay
is claimed. Existing stock rename ledger/portfolio code remains unchanged.

Focused relevance tests: **10 passed**. Full suite: **2,103 tests +18 subtests
passed**, 19 warnings, 201.56 seconds. All launched builds/checks completed.
Three primary notices captured; two Banzai issuer-domain timeouts have a retained
Nasdaq-distributed issuer fallback. No V6 change, deployment or training launch.

[Full relevance review](docs/reviews/2026-09-17-v7-unrelated-renames.md),
[prior scoped renames](docs/reviews/2026-09-17-v7-common-share-renames.md),
[prior coverage/repairs](docs/reviews/2026-09-17-v7-action-coverage.md).

## New held-cash policy accepted — implement next

The user explicitly accepted
`docs/specs/V7_STOCK_CASH_LEDGER_PROPOSAL_20260917.json`:
4,337 of 4,392 compiled cash events have agreeing ex/record/pay dates and no
flagged due-bill chronology. Proposal: accrue a pre-tax receivable on entitled
funded shares, include it in equity but not spendable cash, release cash at the
first captured regular open after the agreed pay date, and model zero withholding.
Broker posting is not verified. **This decision is settled; do not ask again.**
Active policy: `docs/specs/V7_STOCK_CASH_LEDGER_ADMISSION_20260917.json`.
Implement its funded-share receivable/release ledger and actual consumer checks
next. The other 55 cash events need separate date review. This is a separate
admission from the earlier feature/no-event decisions.

## Current immutable artifacts

Under `nn_meta/validation/`:

- History: `v7-security-history-20260917-gap-r2`.
- Inventory: `v7-action-inventory-20260917-tail`.
- Price actions: `v7-ordinary-actions-20260917-tail-gap-r2`.
- **Unrelated records:** `v7-other-instruments-20260917-renames` (45 cash groups +3 renames).
- **Renames:** `v7-common-share-renames-20260917`.
- **Coverage:** `v7-action-coverage-20260917-relevance`.
- Current verification: `v7-relevance-consumers-20260917`, three
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
Current shared quota: 63,057,207,992 bytes, zero reservations. Recheck before
acquiring another named necessary input; no broad collection campaign.

No full V7 dataset or trained model exists. Saved readiness remains
`v7-readiness-20260917-entry-demand.json` with three foundational passes and eight
substantive stages unpassed. Preserve uncommitted assembly modules and unrelated
V6 edits. This milestone makes no deployment or training launch.

Previous handoff: `handoff-history/HANDOFF-2026-09-17-before-unrelated-renames.md`.

Independent next review identified: 12 Massive split records use adjustment_type
stock_dividend. Ten appear to describe actual same-share splits (GOOG/GOOGL, GME,
TSLA, PANW, APH twice, ORLY, IBKR, CRWD); ENVX/OPEN may instead be warrants.
Do not map the type globally. Primary notices must establish exact ratios, dates,
shares and availability; no split-admission code or captures yet for this batch.
A separate diagnostic found only 64 one-per-provider exact cash matches with
Massive USD and Alpaca foreign=true (62 exact selected identities); the rest of
the 358 unreviewed-term groups are not resolved by removing a foreign flag.
No additional foreign-unit assumption has been proposed or authorized.
