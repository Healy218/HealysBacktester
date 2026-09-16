# REALTIME_SPEC — live feeds on the server and the v7 "real-time capable" contract

**Status:** drafted 2026-09-05 (the day Massive Advanced + Alpaca Algo Trader
Plus landed). Feeds code: `nn_meta/live/feeds/`. Supersedes nothing; extends
V4_OUTLINE's point-in-time contract to intraday data.

**September 15 scope amendment:** the 15-minute-only V7 cadence below is
historical and superseded by [MULTITIMEFRAME_RESEARCH](MULTITIMEFRAME_RESEARCH.md):
1/5/15/30-minute signals with one-minute observed option execution. Current
feature inventory and remaining freeze gates are in the
[feature audit](../reviews/2026-09-15-v7-feature-and-freeze-audit.md).
The live/offline parity requirement remains applicable before live promotion;
example future features below are not extra admitted model columns.

## 1. What the feeds are for

Two daemons on the Hetzner server, each writing a small on-disk store:

| Feed | Source | Store | Readers |
|---|---|---|---|
| Stock 1m bars, SIP, union universe (~443 names) | Alpaca `StockDataStream(feed=sip)`, `bars` channel, one connection | `barstore` (1m parquet per symbol per session; 15m aggregated on read — parity-checked bar-identical to REST) | every expert's `_bar_loader` for TODAY's bars; v7 intraday features |
| Option NBBO, OPRA, dynamic set ≤ 1,000 | Alpaca `OptionDataStream(feed=opra)`, `quotes` channel | `quotestore` (latest bid/ask per contract, JSON) | alert text (bid/ask/spread), paper seat fills; Massive REST snapshot is the fallback |

Freshness is a **heartbeat file** per feed; a reader that finds it older
than `_FEED_MAX_AGE_MIN` (3 min) falls back to REST with the cache bypassed.
The day-keyed CSV cache is only ever used for CLOSED sessions (≤ yesterday)
— the 2026-09-05 incident (EXPERIMENTS) must be structurally impossible.

Operational shape on the server: no sudo → `@reboot` cron line + a 5-minute
watchdog line (`pgrep || nohup …`) per daemon; logs `logs/feeds_*.log`; the
17:00Z heartbeat digest gains a "feeds" line (stale heartbeat = page).

## 2. The v7 real-time contract (what "capable of using real-time data" means)

The panel's decision is still made on a CLOSED 15-minute bar (V4 contract:
`available_at` = bar close, no forming-bar lookahead). Real-time data enters
v7 in three places, each with a rule:

1. **Intraday features at the 15m decision point.** Any feature derived from
   sub-15m data (1m bar shape, realized-vol-of-the-bar, trade-count
   acceleration, option spread/imbalance at the decision time) is allowed
   ONLY if it has an **offline twin** computed from history with identical
   code: stock 1m from Alpaca SIP history (2016→), option 1m/trades/quotes
   from Massive flat files (aggs/trades 2017→, quotes 2022-03→). The gate is
   a **parity test**: live-feed value vs offline-twin value for the same
   (symbol, bar) over ≥ 1 session, tolerance 0 for bar-derived, ≤ 1 tick for
   quote-derived (quote sampling is time-based). No twin, no feature.
2. **Execution realism.** The paper seat fills at the streamed NBBO (buy at
   ask, sell at bid) and the quote-verified ledger (TODO "Massive Advanced"
   D3) is the offline twin — same accounting code, quotes from REST history.
3. **Cadence.** v7 keeps the 15m cadence for decisions; the feeds make the
   pass instant (no REST) and exact (the just-closed bar). A sub-15m seat is
   a separate spec, not a v7 change.

Non-goals: websocket-driven signal generation (no closed-bar contract),
wildcard option subscriptions (Business tier), anything that needs the
forming bar.

## 3. Build order

- [x] `barstore` + 1m→15m aggregation, parity-checked (SPY/NVDA/PEP, 2026-09-04: max diff 0.0 on OHLCV).
- [x] `stock_stream` daemon (backfill today over REST, stream, heartbeat, reconnect).
- [x] `_bar_loader` composition: cached history ≤ yesterday + streamed/forced today.
- [x] `quotestore` + `option_stream` (dynamic watch file, ≤ 1,000 contracts).
- [ ] Alert path: register the alert's contract in `option_watch.json`; show bid/ask/spread from the store (Massive snapshot fallback).
- [ ] Server: deploy both daemons (cron @reboot + watchdog), heartbeat digest line, one full session of parity logs (Monday 2026-09-08).
- [ ] v7 features: pick the first intraday feature set, write the offline twins from Massive history, parity test, then they join the v7 schema.
