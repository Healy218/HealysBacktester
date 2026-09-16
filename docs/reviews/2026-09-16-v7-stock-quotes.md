# V7 Alpaca stock-quote adapter and real capture

## Implemented

`nn_meta/v7/stock_quotes.py` captures historical Alpaca SIP stock quotes with
literal symbols (`asof=-`), exact nanoseconds and bounded complete pagination.
Alpaca's inclusive end becomes an exclusive end by subtracting one nanosecond.
Errors, unexpected symbols, token cycles, page-budget exhaustion and malformed
clocks fail; an observed empty complete interval is distinct from missing data.

The stock tape supplies sized observed buy/sell quotes and causal bid marks to
the existing physical ledger interface. It retains security and receipt identity,
uses the captured regular-session calendar and only regular firm quotes. A newer
invalid market cannot be bypassed with an old mark. Conflicting same-timestamp
states have no proven order and are rejected. Post-decision latency/deadline and
mark-age rules use the existing QuotePolicy. Reported size is a research liquidity
constraint, never a guarantee of broker execution.

`StockQuoteArchive` verifies receipts and bound identity/size evidence and keeps
a bounded LRU cache. Overlapping shards require explicit reconciliation; each
requested fill/mark window currently must fit in one shard. Full demand generation
must arrange those windows or add verified adjacent-shard assembly.

`scripts/capture_v7_stock_quotes.py` accepts bounded requests, verifies exact-date
exchange-listed company identity against the active universe and exclusions,
refuses OTC identity references, captures only Alpaca SIP prices, and uses the
existing shared quota and 100 GiB disk reserve. Acquisition is serial to protect
V6. Frozen captures can be reused only after scope/evidence verification.

## Dated size conversion

Alpaca changed quote sizes from round lots to shares on November 3, 2025.
Pre-transition conversion requires an explicit legacy lot size and evidence;
post-transition sizes are already shares. Never multiply every historical quote
by 100. The AAPL pilot declares the standard 100-share legacy lot against captured
provider evidence. Full-universe special-lot/security-date review is outstanding.
The timestamps are historical SIP-feed quote timestamps; local historical receipt
latency is unknown, as recorded in each manifest.

Primary sources captured under `nn_meta/data_v7/stock-quote-docs-20260916`:

- [Historical quote endpoint](https://docs.alpaca.markets/us/reference/stockquotes-1)
- [Dated size change](https://docs.alpaca.markets/us/v1.1/changelog/marketdata-bid-and-ask-size-display-change)
- [Provider explanation of earlier quote sizes](https://forum.alpaca.markets/t/why-can-i-see-odd-lot-quotes-in-sip-feed/16000/4)

Requests: `nn_meta/validation/v7-stock-quote-doc-requests-20260916.json`.
The documentation captures total 1,387,215 response bytes.

## Actual pilot

Request: `nn_meta/validation/v7-stock-quotes-pilot-requests-20260916.json`.
AAPL May 5, 2022, 13:30–13:32 UTC; exact-date FIGI BBG000B9XRY4 identity comes
from `nn_meta/data_v7/action-reference-20260916/AAPL/2022-05-05`.

Command:

```bash
./venv/bin/python scripts/capture_v7_stock_quotes.py \
  --requests nn_meta/validation/v7-stock-quotes-pilot-requests-20260916.json \
  --output nn_meta/data_v7/stock-quotes-pilot-20260916 \
  --budget-root nn_meta/data_v7
```

Captured **20,628 quotes**, all regular-condition `R`, in a complete paginated
receipt at `nn_meta/data_v7/stock-quotes-pilot-20260916/6a13b036cf269e72be05fe912713804d8bab3614249b0e4dc661901feadfe16e`.
Verification report: `nn_meta/validation/v7-stock-quotes-pilot-20260916/report.json`.
At the 13:30 decision, the first admitted quote after the one-second latency is
13:30:01.018340895 UTC: ask $163.83 with 100 shares and bid $163.78 with 700 shares.
The 13:31 causal bid mark is $163.79 from 13:30:59.732256292 UTC.
These are independent example buy/sell selections from the same observation,
not a claimed completed portfolio path or realized round trip.

## Validation and outstanding integration

Focused tests: 29 passed across stock quotes and physical execution, including
15 new stock tests. Tests exercise size conversion before/after November 3,
pagination, exact bounds, incomplete/empty capture, malformed clocks, security
mismatch/exclusion, unknown lot units, invalid latest markets, ambiguous ties and
consumption by a funded inventory ledger. The ledger test uses a synthetic
settlement calendar; it is not official settlement evidence.

Full-suite result is recorded in the current HANDOFF and
`/tmp/v7-stock-quotes-20260916-tests.log` after completion.

This is a required adapter and real source pilot, **not full-universe readiness**.
Remaining physical dependencies include historical settlement dates, official
expiry references/deliverables, full liquidation demand/capture and end-to-end
funding/stock/cash reconciliation. No readiness stage was manufactured or waived.
Quota after capture: **62,557,784,397 /250,000,000,000 bytes**, no reservations.

## Settlement event correction and source conflicts

`SettlementCalendar.settlement` now accepts a covered trading date that is
not a settlement date (for example Columbus Day). T+2 before May 28, 2024,
and T+1 from that date count later captured settlement dates directly from
the event date. The event is not rolled forward first. Unknown/nontrading
dates and invalid clocks remain rejected. Conservative cash availability
continues at the next trading open after settlement. Synthetic regression
cases include October 10, 2022 and October 14, 2024 and funded inventory.
Full suite: **1,804 tests and 18 subtests**, 18 warnings, 87.43 seconds;
`/tmp/v7-settlement-event-20260916-tests.log`.

The official calendar is still unfinished. Captured FINRA 2023 PDF page 3
lists November 10 as a banking/settlement holiday, while indexed later DTCC
notice 19155-23 describes normal November 10 processing. Original DTCC bytes
remain unavailable (HTTP 404); search snippets are not admitted evidence.
Carter's January 9, 2025 market closure also needs distinct settlement evidence.

The captured Nasdaq URL containing `2025/06/02/0761-25_Holiday...` currently
serves a **2026** holiday table. Both pages were rendered and inspected.
Its filename/URL cannot establish a 2025 historical publication vintage.
Captured bytes and receipts remain under
`nn_meta/data_v7/public-settlement-extra-20260916`; it is not admitted as
a 2025 historical calendar. The other two requests in that batch failed
HTTP 404. Request declarations: 
`nn_meta/validation/v7-settlement-evidence-extra-requests-20260916.json`.

Latest readiness checkpoint:
`nn_meta/validation/v7-readiness-20260916-stock-settlement-checkpoint.json`.
The three input/inventory checks pass; eight substantive stages remain missing.
