# Handoff — V7 item 6-1: seven common-share rename records consumed

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

Seven finite undated name-change records now have primary-notice effective dates
and exact adjacent composite/share-class identities: FB→META, FISV→FI, FI→FISV,
GPS→GAP, SQ→XYZ, GOLD→B and SATS→ECHO. These six securities retain their common
shares; no new chart factor, cash entitlement or successor identity is created.
Date-only notices use a conservative next-midnight New York publication bound.

Coverage consumes these seven records separately from price actions and retains
identity-event IDs in actual feature declarations. Admission increases by 5,644
to **584,804 history sessions** (580,427 no-price-event /4,377 price-event).
Action-blocked sessions fall to 29,803; identity-blocked remain 52,632. The other
660,465 rows outside these six securities have unchanged coverage fields.

Current original partition: **10,428 =8,964 compiled cash/split +90 unrelated
cash +7 reviewed rename +1,367 pending**. The 4,481 cash/split events, raw prices,
membership and selected identities remain unchanged. The previous GAP repair,
48 additional cash events and no-event policy implementation remain intact.

Six captured two-session feature boundaries pass the actual proposal loader and
saved 15-minute feature path: META/FI/FISV/GAP/XYZ/ECHO. Barrick correctly remains
blocked by a separate AMRK→GOLD ticker-reuse record. Resolving one record does
not silently clear another. These bounded stores are not full feature production.

The physical ledger has an exact-clock stock rename handler and portfolio event
scheduling before same-clock marks. It preserves cash, quantities, settlement
commitments, cost and security identity. Funded synthetic tests cover inventory,
exercised-call delivery, liquidation and rejected option handling. **No actual
held market replay or option-deliverable admission is claimed.** Open options or
merger phases reject stock-only notices before mutation.

Focused regression: **59 tests passed**. Full suite: **2,093 tests +18 subtests
passed**, 19 warnings, 168.78 seconds. All launched builds/checks completed.
Six new primary notices were captured; earlier Fiserv notices reused. Two timed
out endpoints have retained exchange-hosted fallbacks. V6 was not changed.

[Full rename evidence](docs/reviews/2026-09-17-v7-common-share-renames.md) and
[preceding no-event/repair evidence](docs/reviews/2026-09-17-v7-action-coverage.md).

## Current immutable artifacts

Under `nn_meta/validation/`:

- History: `v7-security-history-20260917-gap-r2`.
- Inventory: `v7-action-inventory-20260917-tail`.
- Price actions: `v7-ordinary-actions-20260917-tail-gap-r2`.
- Unrelated cash: `v7-other-instrument-actions-20260917-tail-gap-r2`.
- **Renames:** `v7-common-share-renames-20260917`.
- **Coverage:** `v7-action-coverage-20260917-renames`.
- New verification: `v7-rename-consumers-20260917`, six `v7-rename-feature-check-*`
  stores and `v7-rename-tests-20260917`.
- Prior verification: `v7-coverage-consumers-20260917`,
  `v7-coverage-feature-check-20260917-SPY`, `v7-coverage-tests-20260917`.
- Supplemental daily inputs: `v7-gap-daily-20260917/{2025,2026}`.

Under `nn_meta/data_v7/`: `rename-notices-20260917`,
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
3. Resolve **206 complex records**, including 40 undated name-change records.
   Pure ticker changes need dated identity plus primary-notice review; process
   dates alone are not effective dates. GAP's pure rename is now resolved;
   Barrick still needs a separate unrelated AMRK→GOLD treatment. Actual mergers/spinoffs must retain
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
Current shared quota: 63,056,786,455 bytes, zero reservations. Recheck before
acquiring another named necessary input; no broad collection campaign.

No full V7 dataset or trained model exists. Saved readiness remains
`v7-readiness-20260917-entry-demand.json` with three foundational passes and eight
substantive stages unpassed. Preserve uncommitted assembly modules and unrelated
V6 edits. This milestone makes no deployment or training launch.

Previous handoff: `handoff-history/HANDOFF-2026-09-17-before-common-share-renames.md`.
