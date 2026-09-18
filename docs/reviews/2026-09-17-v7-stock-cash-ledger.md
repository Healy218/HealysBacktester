# V7 authorized pre-tax cash-flow implementation

The user accepted the finite [stock-cash proposal](../specs/V7_STOCK_CASH_LEDGER_PROPOSAL_20260917.json).
The [active admission](../specs/V7_STOCK_CASH_LEDGER_ADMISSION_20260917.json)
is implemented for **4,337 existing cash events across 272 securities**. This
does not close TODO 6-1 or establish full held-history/training readiness.

## Compiled terms and consumers

`nn_meta/v7/stock_cash.py` and `scripts/compile_v7_stock_cash.py` verify the exact
authorized set against the original inventory, retained action receipts and
agreed ex/record/pay dates. They retain each original source reference, source
amount, currency/unit, policy identity, availability assumption and modeled
release clock. There are no new events or changed chart factors. The other 55
compiled cash events remain excluded: 41 pay-date issues, 13 record-date issues
and one date/due-bill issue.

`PhysicalLedger` records beneficial share changes on funded purchases, completed
exercise decisions and sales. The ex-session open accrues gross cash on shares
owned before that session. Receivables add equity without increasing spendable
cash. They survive a later sale and release once at the first captured regular
open strictly after payment date. Fractional paper shares accrue pro rata;
withholding and dividend fees are zero modeled assumptions. Historical broker
posting is not verified.

The shared portfolio schedules accrual and release before same-clock marks and
new entries. Outstanding receivables keep completion false even after all
positions have closed. Exact regular-open validation, settlement coverage,
chronological processing and cash reconciliation reject unsupported/mistimed
events before ledger mutation. Open options alone confer no stock entitlement;
changed option deliverables remain separate.

## Original settlement evidence and captured accounting case

The archived [FINRA October 15, 2021 notice](https://www.finra.org/sites/default/files/2021-10/information-notice-101521.pdf)
was rendered and all four pages inspected. Pages 2–3 supply 46 trade/settlement
pairs and the annual holidays, including June 20 Juneteenth and separate October
10/November 11 bank holidays. The normalized 2022 weekday settlement calendar
has 249 business dates and agrees with every pair. The retained trading calendar
differs exactly on the two reviewed bank holidays. This review covers **2022
only**; later years and crossing-year settlement horizons are not admitted.

Review: `docs/specs/V7_SETTLEMENT_2022_REVIEW_20260917.json`.
Original source: `nn_meta/data_v7/public-settlement-20260916/finra-2022-holidays`.
The existing 2023 FINRA/DTCC conflict, 2025 mourning exception and failed original
OCC/DTCC captures remain open. No additional data acquisition was needed here.

The existing AAPL May 5, 2022 SIP quote supplies a simulated 100-share purchase
at $163.83, 13:30:01.018340895 UTC, against dated identity and legacy-size evidence.
The existing stock costs reserve $16,407.5745. Purchase settlement is May 9;
conservative availability is May 10. The May 6 dividend accrues $23 while the
purchase is unsettled, cannot fund another entry, and releases May 13. Final cash
is $83,615.4255 plus 100 retained funded shares. Duplicate release adds nothing.
This is a source-backed accounting case, not a completed strategy outcome or
stock sale; no unavailable held market mark was invented.

## Verification and retained outputs

`scripts/validate_v7_stock_cash.py` independently checks all 4,337 source amounts,
approved identities/dates and release opens. The actual portfolio consumer also
processes the 681 eligible events whose accrual and release lie within the
reviewed 2022 settlement year, with no inventory: cash stays $100,000 and no
dividend income is created. Synthetic tests separately exercise fractional
shares, exercised calls, put delivery, purchases at ex-open, pre/post-ex sales,
equity conservation, blocked spending, calendar boundaries, corrupt balances,
and shared-portfolio completion before/after payment.

- Current compiler: `nn_meta/validation/v7-stock-cash-entitlements-20260917-r3`.
- Verification: `nn_meta/validation/v7-stock-cash-verification-20260917`, including
  source hashes, report, funded ledger, empty-inventory replay and normalized
  settlement calendar.
- The first and r2 compiler outputs predate final source validation and are
  preserved as historical artifacts.
- Cash-specific tests: 28 passed. Full suite: **2,131 tests +18 subtests passed**,
  19 warnings, 163.96 seconds; `nn_meta/validation/v7-stock-cash-tests-20260917`.

Reproduction (new immutable outputs required):

```bash
./venv/bin/python scripts/compile_v7_stock_cash.py \
  --actions nn_meta/validation/v7-ordinary-actions-20260917-tail-gap-r2 \
  --inventory nn_meta/validation/v7-action-inventory-20260917-tail \
  --calendar nn_meta/data_v7/exchange-calendar-20260916/calendar.json \
  --policy docs/specs/V7_STOCK_CASH_LEDGER_ADMISSION_20260917.json \
  --output nn_meta/validation/v7-stock-cash-entitlements-20260917-r3
./venv/bin/python scripts/validate_v7_stock_cash.py \
  --events nn_meta/validation/v7-stock-cash-entitlements-20260917-r3 \
  --actions nn_meta/validation/v7-ordinary-actions-20260917-tail-gap-r2 \
  --calendar nn_meta/data_v7/exchange-calendar-20260916/calendar.json \
  --quotes nn_meta/data_v7/stock-quotes-pilot-20260916/6a13b036cf269e72be05fe912713804d8bab3614249b0e4dc661901feadfe16e \
  --settlement-review docs/specs/V7_SETTLEMENT_2022_REVIEW_20260917.json \
  --output nn_meta/validation/v7-stock-cash-verification-20260917
```

Remaining work includes all unresolved identity/action cases, 55 excluded cash
events, later settlement years, splits/lifecycle and option-deliverable treatment
over full actual held paths. Feature coverage remains 586,830 admitted sessions;
this accounting milestone does not alter it. V6 and live operation are unchanged.
