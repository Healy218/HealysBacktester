# Handoff — dividend portion complete, September 18, 2026

The interrupted dividend work is finished. Do not restart the old issuer search
or treat archived remaining counts as live. Current overall item is still 6-1:
noncash/identity lifecycle and complete held-position treatment. No training,
deployment, bulk acquisition or V6 policy change was performed.

## Final verified artifact

`nn_meta/validation/v7-dividends-complete-20260918`

- 10,428 original provider records reconcile: 10,194 resolved / 234 pending noncash.
- 4,854 cash price events and 4,918 separately dated cash payment leaves.
- Zero uncompiled dividend groups; zero missing held-cash treatments.
- Every cash factor checked against actual raw preceding prices and dated identity.
- Canonical history remains 667,239 rows, with 587,284 admitted history sessions.
- All payments pass source/component/clock/settlement checks. Actual zero-inventory
  portfolio replay creates no receivable and ends with the original $100,000.
- `dividends_complete=true`; `step_1_complete=false`, `research_ready=false`,
  and full `held_position_admitted=false`.
- Full suite: **2,338 tests plus 18 subtests passed**, 19 warnings, 127.33 seconds.
  Log: /tmp/v7-dividend-tests-final-20260918.log.

The completion audit is
[docs/reviews/2026-09-18-v7-dividends-complete.md](docs/reviews/2026-09-18-v7-dividends-complete.md).
TODO has the dividend subtask checked; the seven overall readiness items remain open.

## Inputs and consumers

Final artifact contains actions.json, events.json, unresolved.json,
coverage.parquet, auxiliary_cash_actions.json, price_boundary_checks.json,
treatments.json, dispositions.json, report.json and all immutable input bindings.
Reproducer: scripts/finalize_v7_dividends.py; use a fresh output directory for
a new revision. The final audit rejects incomplete payment partitions or
inconsistent raw-price factors before declaring dividend completion.

Canonical study history remains
`nn_meta/validation/v7-security-history-20260917-gap-r2`.
`v7-dividend-boundary-history-20260918` is only the finite dividend compilation
view, with three preceding-scope observations and five separate cash security IDs.
It preserves trading membership byte-for-byte and does not replace the feature
history. The 16 auxiliary cash events accrue only to beneficial holdings under
the correct identity. They do not convert predecessor shares to successors.
ANTM/ELV June 2022 is explicitly routed by dated same-FIGI evidence. First-scope
features remain cold on March 15 despite the verified prior-close factor.

Trading and reported settlement clocks are now captured through 2027-01-08:
`nn_meta/data_v7/dividend-calendar-20260918/{calendar,settlement_calendar}.json`.
Every original calendar/settlement row in shared coverage was preserved.
Original inventory is v7-action-inventory-20260917-tail, renames are
v7-common-share-renames-20260917, and original other/disposition treatments are
v7-dividend-dispositions-20260918 (all under nn_meta/validation).

## Explicit model and source decisions

The user approved the native-currency FX rule. The 24 remaining groups / 27
payments use the last official Bank of Canada daily observation strictly before
ex-date, fixed for cash and price. Preserve native amount, rate/date, fx_model
and policy identity. This is modeled USD cash, not actual depositary conversion.
PBR currencyPerDr already includes its ADR ratio. No withholding/fee model.

SILJ December 2025 is resolved by the visually inspected issuer ICI tax table:
December29 ex/record, December30 pay, $0.55410448 cash. It supersedes the
conflicting backfilled website dates; tax gross-up is not extra cash.

ETHE September3 is one explicitly documented provider precision reconciliation:
original $0.025932 rounds to the other original USD report $0.0259, with matching
dates. A separate finite policy preserves the precise original and sets
primary_amount_verified=false. The September issuer notice was unavailable;
earlier issuer SEC evidence establishes units only. This is not a general
tolerance or a primary-source amount claim.

All source captures are retained under
`nn_meta/data_v7/dividend-finish-20260918`. R1–R12 reviews, FX and provider
precision reviews/policies, and their producer modules are frozen by receipts.
Never edit those bytes in place to bypass verification. The historical producer
registry preserves exact old snapshots. Follow DOCUMENTATION's traps.

## Next session

Continue the remaining **noncash** records and security lifecycle dependencies
from the final artifact's unresolved.json, including option deliverables and
funded predecessor/successor transitions. Do not advance to 6-2 until full 6-1
evidence passes. Keep the original dates, securities, exclusions and study
membership fixed. Reuse captures, name missing consumer inputs before acquiring
anything, and honor four outer workers / one inner thread, 100 GiB reserve,
250 GB acquisition ceiling and a separate total-project forecast before bulk work.
About 459 GiB was free at completion.

Work stays on main with scoped commits/pushes. Preserve the large unrelated
V6/assembly dirty and untracked set; none of it was staged for this dividend work.
Earlier checkpoints are archived in handoff-history/.
