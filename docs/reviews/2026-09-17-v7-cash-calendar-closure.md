# V7 cash continuation and reported settlement dates

This is an item 6-1 checkpoint, not completion of dividends or permission to
advance to 6-2. The user directed finishing the dividends while conserving
storage, then explicitly accepted the documented extension of the existing
pre-tax cash model to the original 528 remaining groups as each passes review.

## Result

- 36 additional cash groups: 18 FCX and 18 SLB; 4,527 total price actions.
- 4,373 cash entitlements: the original 4,337 objects remain unchanged and
  36 reviewed events use the separately accepted extension.
- 586,876 admitted history sessions, up 36. The other 667,203 coverage rows
  are unchanged; 27,731 action-blocked and 52,632 identity-blocked rows remain.
- Exactly **492 dividend review items remain**: 437 uncompiled cash groups
  and 55 already compiled events with unresolved record/payment-date treatment.
- The original Alpaca capture supplies 1,212 trade-to-settlement mappings from
  January 2022 through October 2026. All 1,210 whose cash-availability horizon
  fits the captured trading calendar pass; the final two correctly lack a
  covered next-open horizon. All existing cash releases fit the coverage.

The new cash census reconciles all 10,428 original provider records: 9,179
resolved and 1,249 pending. It counts symbol/ex-date groups rather than provider
rows, and keeps price-action and held-cash work disjoint. The 437 groups comprise
328 unit/term reviews, 47 combined groups, 34 mismatches, 14 single-provider,
11 missing selected identities and 3 adjacent-continuity cases. Complex non-cash
actions and other identity/lifecycle work remain separate.

## Terms and source review

FCX's 18 original dated issuer notices explicitly declare a total $0.15 per
common share, including base and variable cash. Whole-group replacement avoids
both omitted variable components and duplicate provider totals. The issuer's
December 20, 2023 notice resolves the January 11, 2024 ex-event's payment date
to February 1 rather than the conflicting February 5 provider date. Notices and
original record hashes are in `V7_PRIMARY_CASH_REVIEWS_20260917.json`.

Four captured SLB quarterly releases establish exact common-share terms and
dates for May/September/December 2022 and February 2023. The remaining 14 SLB
records retain the existing matching-provider reconstruction basis: an earlier
primary USD/common-share witness and the unchanged selected security/identity
span resolve the foreign-unit flag; both unique providers agree on the original
amount. Amount publication remains explicitly unverified. The compiler rejects
unequal amounts, unknown currency, ADR-unit substitutions, identity changes and
combined records. There is no global waiver of the foreign flag.

The finite model extension is
`docs/specs/V7_REMAINING_STOCK_CASH_ADMISSION_20260917.json`, binding the exact
proposal and its 528 original groups. It preserves the existing pre-tax accrual,
receivable, release, withholding and fee rules. Source/identity/date review is
still mandatory. This does not expand chart admission, infer missing dates,
resolve due bills, or admit option deliverables. The preview is historical;
the authorized artifact is `v7-stock-cash-extension-20260917`.

## Settlement source already present

The extended Alpaca calendar's **original response**, not merely its exchange
session list, contains `settlement_date` for every trade date. Captured Alpaca
API documentation explicitly defines that field as the settlement date for the
trade date. `ReportedSettlementSchedule` preserves that direct mapping and the
existing conservative cash-availability rule: first captured regular open
strictly after settlement. It never constructs a settlement-business-day union
or infers bank holidays from trading dates.

All 46 independently reviewed original FINRA 2022 pairs match. Original mappings
also retain November 10, 2023 normal settlement, the May 2024 T+1 transition,
and January 9, 2025 settlement despite the exchange closure. The normalized
schedule does not claim historical publication or actual broker posting. Its
receipt binds the original calendar response and field-definition review.
Prior failed DTCC/OCC downloads remain historical and are not treated as sources.

## Actual consumer verification

All 36 cash boundaries pass actual raw-minute loading and feature production:
one 15-minute MA variant, 52 observations per event. The pre-event prefix stays
unchanged; the prior-price factor equals `(raw_close - cash) / raw_close`,
volume units stay unchanged, and ex-session raw prices are preserved. These are
bounded consumer checks, not complete feature stores.

The reported-settlement verification rechecks all 4,337 original entitlements,
consumes them through the actual no-inventory portfolio (no invented cash), and
repeats the captured funded AAPL purchase/receivable/release case. The extension
verification preserves those original objects and consumes all 4,373 current
cash events through the portfolio. Its funded AAPL evidence is inherited from
that unchanged, freshly verified base; it does not claim a funded FCX/SLB trade
or a completed strategy outcome.

Full suite: **2,225 tests and 18 subtests**, 19 warnings, 126.43 seconds, exit 0.
Receipt: `v7-cash-calendar-tests-20260917`. The extension verification CLI was
added after the full suite and executed successfully against the actual
artifacts. No model training, deployment or V6 policy change.

## Current artifacts and storage

All artifact names below are under `nn_meta/validation`:

- `v7-primary-cash-20260917`: preserves 4,491 actions, adds 22 primary reviews.
- `v7-cash-units-20260917`: adds 14 matching SLB unit reviews; use this action set.
- `v7-action-coverage-20260917-cash`: current coverage.
- `v7-cash-consumers-20260917` and its 36 feature stores: real boundary checks.
- `v7-reported-settlement-20260917`: direct settlement schedule and original cash verification.
- `v7-stock-cash-extension-20260917`: current 4,373 entitlements.
- `v7-stock-cash-extension-verification-20260917`: actual extension consumer checks.
- `v7-dividend-closure-20260917-r3`: current 492-item census. Earlier census
  outputs are historical; r1 also predates the corrected Alpaca payable-date display.

Acquisition quota is 63,071,664,529 bytes, zero reservations. This continuation
added 3,401,154 bytes relative to the earlier 63,068,263,375-byte checkpoint,
including three newly captured IBM/Target/PNC date-review documents not yet
admitted. New derived artifacts/consumer stores use approximately 298 MiB.
No stock or option price archive was downloaded. Reuse existing captures; keep
new evidence to named documents. Before bulk acquisition/full stores, forecast
storage and establish a total-project budget, distinct from the acquisition cap.
