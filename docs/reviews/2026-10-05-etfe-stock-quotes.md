# ETFE underlying quote pilot and discovery continuation — October 5, 2026

Completed **ETFE-1.stock-quote-pilot** within finite transport/diagnostic scope,
plus the next discovery batch. The universe remains **SPY, QQQ, VOO**. SIP is
the consolidated stock-market feed, not another security. Option execution
continues to use completed-minute VWAP; these stock quotes support the declared
underlying-price checks and eventual physical-share liquidation paths.
[Machine receipt](2026-10-05-etfe-stock-quotes.json),
[evidence ZIP](2026-10-05-etfe-stock-quotes-evidence.zip),
[contract](../specs/ETFE_STOCK_QUOTES_20261005.md).

## Capture and normalization

The new source-bound quote transport preserves the earlier acquisition engine.
It captured all **54 windows / 135 ticker-minutes** across six dates: January 19
and November 29, 2024; April 4, October 31 and November 3, 2025; October 2, 2026.
Each ETF/date has 150-second windows around the stock open, stock close minus
15 minutes, and stock close. These are sampling anchors; the stock calendar does
not establish dated option-class cutoffs or official exercise references.

**216 HTTP 200 responses / 1,943,472 quote occurrences** reached transport EOF,
within the 256-attempt study cap. All 54 windows contain observations. Capture
took 241.60 seconds across the first-page stop and two resumptions. Raw response
bodies occupy 221,209,361 bytes; typed data/receipts occupy 130,440,798 bytes;
the complete root occupies 352,271,006 bytes at review time.

| Underlying | Quote occurrences | Successful pages |
| --- | ---: | ---: |
| SPY | 748,933 | 83 |
| QQQ | 901,706 | 98 |
| VOO | 292,833 | 35 |

Parquet preserves every raw occurrence, nanosecond timestamp, bid/ask, raw sizes,
conditions/exchange/tape inside raw JSON, and source/page/ordinal identity.
**1,991 crossed quotes** are retained with explicit flags and null diagnostic
midpoints. The independent occurrence and Decimal numeric audit passes for all
rows. Equal timestamps are not deduplicated. The first-page resume preserved
eight files; a completed restart made zero requests and preserved 868 files.

## What remains unadmitted

Alpaca's [October 30, 2025 notice](https://docs.alpaca.markets/us/v1.1/changelog/marketdata-bid-and-ask-size-display-change)
announces that stock quote sizes change from round lots to shares on November 3.
The sample includes both sides of that date, but the notice alone does not prove
whether historical API data was rewritten. Raw sizes are retained unchanged;
normalized share quantities remain null. No blanket factor of 100 is applied.
Size divisibility is not proof of representation or executable capacity.

Alpaca's [automatic-exercise explanation](https://alpaca.markets/support/what-is-automatic-exercise)
identifies the underlying official closing price as the reference. This pilot's
quote midpoint is not an official close. Dated exercise references, deliverables,
option sessions and historical availability remain required for real admission.

The busiest window, QQQ at the April 4 open, contains 111,643 quotes / 12 pages
in 2.5 minutes. Applying this deliberately selected sample's mean byte density
to all 805,230 possible regular ticker-minutes gives a **1.32 TB raw-payload
scenario**, before typed files or copies. It is neither a representative forecast
nor an upper bound. Full phase-B/C budgets remain unresolved; exact path/window
unions must precede any broad stock-quote acquisition.

## Discovery and verification

The separate March 26–April 15, 2024 discovery batch completed **126 successful
GETs / 7,344 records**, normalized in 126 partitions. Ninety-eight queries are
empty, without implying historical nonexistence. Every raw occurrence reconciles;
zero-request restart preserved 507 files. Frontier r2 independently reconciles
all 2,073 ticker-sessions: **684 / 6,300 queries captured, 5,616 remaining**,
45,470 returned symbols and 1,197,044 gross known-symbol/session edges. Current
listings remain discovery records, not historical eligibility or market bars.

The earlier normalization schema now contains **1,501 partitions / 1,971,486
records**; the 216 quote Parquets and their 1,943,472 records have a separate
source-bound schema/root. The evidence ZIP hashes all 2,095 local files and
includes metadata/source snapshots; large bodies and Parquets remain local.

All **304 focused ETFE tests pass**, including ten new quote scope, early-close,
DST, pagination, corruption, quality, crash-budget and resume checks. No process
remains running. Full demand, dated admission, integrated real pilot, dataset
freeze and training remain open. No orders, deployments or new tickers.
