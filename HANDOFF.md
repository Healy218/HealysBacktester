# Handoff — October 5, 2026 — Underlying quotes and discovery continuation

## Focus and completed result

User asked to continue, then clarified the small ETF universe/SIP terminology.
Universe remains **SPY, QQQ, VOO**. SIP is the underlying stock quote feed;
option entries/exits still use completed-minute VWAP. No extra ticker or strategy.
Completed **ETFE-1.stock-quote-pilot** within finite capture/diagnostic scope,
plus a second discovery batch. [Review](docs/reviews/2026-10-05-etfe-stock-quotes.md),
[machine receipt](docs/reviews/2026-10-05-etfe-stock-quotes.json).

- Stock quotes: all 54 short windows across six dates, including early close,
  busy session, size-unit transition and fixed-end day. 216 successful GETs /
  1,943,472 occurrences; 221,209,361 raw payload bytes, 352,271,006-byte root.
- Every quote occurrence, raw size, nanosecond timestamp and diagnostic value
  reconciles. 1,991 crossed quotes retained/flagged; their midpoint is null.
  First-page resume preserved eight files; final zero-request restart 868 files.
- Alpaca announced round-lot to share sizes beginning November 3, 2025. The
  announcement does not prove historical backfill representation. Raw sizes
  stay unchanged; normalized share quantities and capacity admission stay null.
- Quotes do not supply the official underlying close required for exercise.
  Dated exercise references, deliverables, option hours and admission remain open.
- March 26–April 15 expiry discovery: 126 successful GETs / 7,344 records, all
  normalized and audited. Zero-request restart preserved 507 files. Ninety-eight
  empty queries do not prove historical nonexistence.
- Frontier r2 independently reconciles 684 / 6,300 queries captured, 5,616
  remaining, 45,470 returned symbols and 1,197,044 gross symbol/session edges.
- All 304 focused tests pass, including ten new quote transport/normalization
  checks. Prior bound sources/artifacts remain unchanged; quote engine is separate.

## Evidence boundary and stopping point

Original schema: 1,501 normalized partitions / 1,971,486 records. Quotes have a
separate schema/root with 216 Parquets / 1,943,472 records. No real execution,
scientific label or feature admission follows. January usable history stays open.
Quote density projected over the entire calendar gives a nonrepresentative
1.32 TB raw scenario before typed data/copies, not a forecast or upper bound.
Full phase-B/C budgets require actual demand. No process remains running.
No training, orders, deployment or change to the 0–5 DTE rule occurred.

## Next selected work

1. **ETFE-1.demand:** continue measured contract discovery and derive exact
   full-window signal/feature/trade and holding/roll/exercise window unions.
   Use quote density to constrain budgets; do not launch a whole-calendar quote
   pull or treat gross returned-symbol envelopes as exact required demand.
2. **ETFE.provider-contract / action-timing / history-boundary:** establish dated
   quote-size representation, official exercise references, option hours/terms,
   action revision availability and scoped usable coverage. Keep raw data intact.
3. **ETFE-4.pilot:** real feature/execution/isolated-label/dataset/training smoke
   with resource and recovery evidence, followed by full build/freeze gates.

## Selected artifacts

`nn_meta/validation/etfe-demand-frontier-20261005-r2/` (r0/r1 retained).
`nn_meta/data_cache_etfe/alpaca-fresh-20261005-discovery-r1/` and
`nn_meta/data_cache_etfe/normalized-20261005-discovery-r1/`.
`nn_meta/data_cache_etfe/alpaca-fresh-20261005-stock-quotes-r0/`.
[State](docs/CURRENT_STATE.md#october-4-etfe-fresh-alpaca-setup),
[commands](docs/reference/ETFE_SETUP.md#bounded-underlying-quote-pilot),
[contract](docs/specs/ETFE_STOCK_QUOTES_20261005.md).
Evidence ZIP indexes 2,095 files. Bound sources stay immutable; use successors.
Preserve unrelated dirty work. [Previous handoff](handoff-history/HANDOFF-2026-10-05-before-stock-quotes.md).
