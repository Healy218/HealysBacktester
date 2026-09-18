# V7 6-1: ten reviewed same-share splits

The finite [review declaration](../specs/V7_DIVIDEND_SPLIT_REVIEWS_20260917.json)
resolves ten provider groups reported by Massive as `stock_dividend` and by
Alpaca as forward splits. Eight original OCC notices hosted by MIAX were captured
and their first-page stock terms visually reviewed; issuer releases establish the
GME and CRWD terms. Original bytes, receipt hashes, exact provider references,
selected adjacent security identities and conservative publication clocks are
retained. The type is never remapped globally. ENVX and OPEN remain unresolved.

| Security | Effective session | Total new shares per old share |
|---|---|---|
| GOOG / GOOGL | 2022-07-18 | 20 each |
| GME | 2022-07-22 | 4 |
| TSLA | 2022-08-25 | 3 |
| PANW | 2022-09-14 | 3 |
| APH | 2024-06-12 | 2 |
| ORLY | 2025-06-10 | 15 |
| IBKR | 2025-06-18 | 4 |
| CRWD | 2026-07-02 | 4 |
| APH | 2026-09-03 | 2 |

The compiler preserves the previous 4,481 actions byte-for-object and adds ten,
for **4,491 events**. The full original partition is 10,428 =8,984 action records
+93 unrelated records +7 rename records +1,344 pending. Coverage increases by
exactly ten sessions to **586,840**; 667,229 other rows are unchanged. Remaining
rows: 27,767 action-blocked and 52,632 identity-blocked. Every split passed the
actual raw-minute feature loader and a two-session, 15-minute MA store (52
observations each), with pre-event prefixes unchanged and post-event price and
volume units reconciled. These stores are bounded checks, not full-catalog builds.

`PhysicalLedger.apply_stock_split` and `physical.splits` in the shared portfolio
adjust funded stock inventory and pending stock deliveries at the effective open.
They preserve cash, payables, settlement dates and already accrued cash amounts.
The quantity-delta ledger carries the changed share count into later dividends.
Open options and differing stock symbols reject before mutation: OCC contract
transitions require separate exact deliverable evidence. Whole event groups with
cash or other entitlements cannot enter this finite same-share compiler.

A captured accounting case buys ten TSLA shares on August 22, 2022 at the
observed $875.96 ask, reserving $8,772.7394 with existing costs. The reviewed 2022
calendar settles August 24 with availability August 25. At the split open the
pending funded quantity becomes 30; cash remains $91,227.2606 after settlement.
At 13:31 UTC, an observed $302.19 bid gives $100,292.9606 equity. Two two-minute
Alpaca SIP captures contain 6,630 and 6,918 records, with original exact-date
references and the existing historical quote-size evidence. This is a retained
stock accounting/mark case; it does not fabricate a liquidation or strategy result.

Artifacts under `nn_meta/validation/`:

- `v7-reviewed-splits-20260917`: combined immutable action inputs.
- `v7-action-coverage-20260917-splits`: complete grid and record partition.
- `v7-split-consumers-20260917`: ten actual feature boundaries, plus corresponding
  `-features-SYMBOL-DATE` stores.
- `v7-stock-split-verification-20260917`: captured funded TSLA ledger and mark.
- `v7-stock-cash-verification-20260917-splits`: fresh verification after the ledger
  changed; all 4,337 cash clocks/amounts, 46 settlement table pairs, 681 empty
  2022 portfolio events and the funded AAPL case still reconcile. The earlier
  cash verification remains historical; the cash compiler r3 is unchanged.

Focused tests: 60 passed across reviewed splits, held splits and stock cash.
Full suite: 2,163 tests +18 subtests passed, 19 warnings, 171.02 seconds; receipt
`v7-split-tests-20260917`.
No training, deployment, full held-history admission or readiness claim follows.
Item 6-1 remains open; subsequent numbered items remain queued.
