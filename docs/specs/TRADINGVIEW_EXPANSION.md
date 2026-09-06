# TradingView expansion — selection and implementation plan

Status: scope researched and first implementation batch September 5, 2026 (Chicago).
The user requested the ten most boosted scripts across the supplied general
listing and the three most boosted Editors' Picks, before corrected research
artifacts are rebuilt. These are additions to the existing Keltner/BBW work.

## Selection scope and evidence

- [Supplied general listing](https://www.tradingview.com/scripts/?script_access=all):
  all **42 exposed pages, 1,000 unique scripts**, including every access/type
  category returned by that URL. Its default sort is `latest_popular`, which
  does not order scripts strictly by cumulative boosts. The returned scripts
  were published August 12–September 5, 2026. **This is the top ten within
  those supplied pages, not the all-time TradingView library.** An optional
  clarification about all-time scope was asked; absent a reply, the supplied
  pages define this selection.
- [Editors' Picks](https://www.tradingview.com/scripts/editors-picks/): all
  **32 pages, 758 unique scripts**. The final page contains 14 entries and no
  next-page link; the general listing ends with 16 entries on page 42.
- Ranked each complete listing by exact public `likes_count` (boosts), not
  views, comments, page position or rounded displayed counters. Page counts,
  reported totals, unique IDs and terminal pagination reconcile.
- **13 distinct selected indicators; no overlap.** Exact public Pine revisions
  are now acquired with source hashes, attribution and license records in
  [tradingview_sources](../../indicators/tradingview_sources/). Exported
  TradingView numerical parity remains pending.
- [Machine-readable snapshot](tradingview-boost-snapshot-2026-09-05.json)
  preserves all ranked metadata, publication versions, source URLs, page
  hashes and server timestamps. Captured around 20:03–20:07 Chicago on
  September 5 (September 6 UTC). Counts can change and represent an interval
  snapshot. Publication versions below are not Pine language versions.

## Ten highest boosts across the supplied general-listing pages

| Rank | Indicator | Author | Boosts | Publication version |
|---|---|---|---:|---:|
| 1 | [AMD Po3 with Live Edge Stats](https://www.tradingview.com/script/hkKioUnL-AMD-Po3-with-Live-Edge-Stats-WillyAlgoTrader/) | WillyAlgoTrader | 5,261 | 1 |
| 2 | [Volume Footprint: Measuring by Math & Geometry](https://www.tradingview.com/script/Tm1cGCPD-Volume-Footprint-Measuring-by-Math-Geometry/) | ata_sabanci | 4,571 | 4 |
| 3 | [Volume-Weighted Order Block Zones](https://www.tradingview.com/script/KcnNgwDI-Volume-Weighted-Order-Block-Zones-BigBeluga/) | BigBeluga | 4,057 | 1 |
| 4 | [Structural Liquidity & POC Matrix](https://www.tradingview.com/script/I8HrQVRv-Structural-Liquidity-POC-Matrix-BigBeluga/) | BigBeluga | 2,455 | 1 |
| 5 | [Setup Scanner [GBB]](https://www.tradingview.com/script/XWuYNmhD-Setup-Scanner-GBB/) | GoodBadBitcoin | 2,237 | 2 |
| 6 | [Gaussian Filter Trend](https://www.tradingview.com/script/AqRNdhlR-Gaussian-Filter-Trend-QuantAlgo/) | QuantAlgo | 2,003 | 1 |
| 7 | [RSI Probability Matrix](https://www.tradingview.com/script/c25U5rsF-RSI-Probability-Matrix-ChartPrime/) | ChartPrime | 1,928 | 1 |
| 8 | [Fibonacci Trend Continuation Signals](https://www.tradingview.com/script/U7CZ8jtj-Fibonacci-Trend-Continuation-Signals-AlgoAlpha/) | AlgoAlpha | 1,877 | 1 |
| 9 | [HTF Log-Regression Volume Profile](https://www.tradingview.com/script/kwXpL7yZ-HTF-Log-Regression-Volume-Profile-BigBeluga/) | BigBeluga | 1,875 | 4 |
| 10 | [Uptrick: Adaptive Trend Trail](https://www.tradingview.com/script/f4N0F439-Uptrick-Adaptive-Trend-Trail/) | Uptrick | 1,653 | 1 |

## Three highest boosts across Editors' Picks

| Rank | Indicator | Author | Boosts | Publication version |
|---|---|---|---:|---:|
| 1 | [Market Structure Break & Order Block](https://www.tradingview.com/script/DkE7UniD/) | EmreKb | 60,704 | 9 |
| 2 | [ICT Killzones + Pivots [TFO]](https://www.tradingview.com/script/nW5oGfdO-ICT-Killzones-Pivots-TFO/) | tradeforopp | 55,049 | 19 |
| 3 | [Support Resistance Channels](https://www.tradingview.com/script/Ej53t8Wv-Support-Resistance-Channels/) | LonesomeTheBlue | 46,188 | 6 |

## Engineering order

This order was initially inferred from the linked authors' descriptions.
The pinned sources and adaptation manifests now define implemented scope.
All thirteen remain in scope, including modes awaiting a data/parity answer.

1. **Pin sources and define contracts for every selection.** Record authors,
   publication versions, source hashes, licenses, imports, defaults, warm-up,
   input data, numerical outputs and alert conditions. Separate the indicator
   calculation from any proposed strategy entry/exit rule. Chart-only tools
   need explicit mechanical rules before becoming proposal families. Existing
   Keltner breakout/mean-reversion and BBW rolling-minimum/percentile differences
   are resolved here too.
2. **Shared bar calculations and trend state.** Gaussian Filter Trend,
   Fibonacci Trend Continuation and Uptrick build on smoothing, range/ATR and
   persistent directional state. Reuse primitives only after checking Pine
   initialization and rounding. Port signal state independently of the authors'
   simplified performance dashboards.
3. **Confirmed structure and sessions.** Implement EmreKb market structure,
   Support Resistance Channels, Volume-Weighted Order Blocks and ICT Killzones.
   Shared helpers cover pivot knowledge times, durable zones, session calendars,
   timezone/DST boundaries and level invalidation. Graphics anchored to an old
   pivot become available at confirmation, never on that earlier pivot bar.
4. **Composite setups and sequential statistics.** AMD Po3, Setup Scanner and
   RSI Probability Matrix need state machines and observation-time bookkeeping.
   Setup Scanner contains six setups: preserve their identities and inspect
   signal priority versus raw alerts. Historical outcomes may update statistics
   only once resolved; final-chart win-rate tables cannot label earlier rows.
   Define same-bar target/stop ambiguity and retain the corrected options ledger
   as the evaluation basis.
5. **Volume distributions and higher timeframes.** Structural Liquidity & POC
   Matrix and HTF Log-Regression Volume Profile require exact bin/distribution
   semantics and historical snapshots of developing profiles. Any higher-
   timeframe input must honor its actual availability. Keep evolving-session
   information distinct from a completed session's final boundaries/profile.
6. **Footprint modes with explicit data contracts.** Volume Footprint offers
   separate geometric OHLCV, intrabar directional-volume and native footprint
   engines. Inventory all modes; verify which can be reproduced with our data.
   A geometric estimate cannot be presented as equivalent to native footprint
   data. Intrabar/native modes require the historical/live twin and parity gate
   in [REALTIME_SPEC](REALTIME_SPEC.md); unresolved modes stay visibly pending.
7. **Integration and corrected research.** Admit each validated calculation/
   strategy through the proposal sweep/frozen replay interfaces, scoped grids,
   feature schema and versioned provenance. Finalize the generation boundary
   after the source/data audit, then prepare a corrected baseline and expanded
   pool for comparison. Never reuse pre-audit v5 outputs or the old v6 shards.

## Acceptance checks before the rebuild

- Pinned TradingView fixtures on identical OHLCV/session inputs; compare values,
  confirmed event timestamps and state transitions, with explicit tolerances.
- Prefix invariance: later bars cannot alter an earlier available output;
  forming-bar, delayed-pivot, HTF and outcome-resolution cases are covered.
- Stateful incremental replay equals batch computation, including session
  changes, gaps, missing volume and restart boundaries.
- Sweep and frozen-parameter replay match all four signal frames. Verify causal
  `available_at` alignment and the live/offline path for each admitted feature.
- Full existing suite remains green; first-batch integration:
  **790 tests and 18 subtests passed, 10 warnings** (planning baseline: 642).
- New research uses fresh current-contract inputs, valid post-optimization
  evaluation windows, mark/cash/cost reconciliation and preserved gate refusals.
  Boosts select the requested research scope; they do not establish performance.

## First implementation batch

Run `./venv/bin/python -m indicators.tradingview_registry` to verify all thirteen
source hashes and print current implementation identities. The identity binds
the Pine source, adaptation manifest, implementation, signal wrapper and shared
math/validation dependencies. The historical ranking snapshot remains unchanged.

| Selection | Implemented scope | Remaining boundary |
|---|---|---|
| Gaussian Filter Trend | Filter, adaptive bands, direction, source alerts, four-frame wrapper | Exported numerical fixtures |
| Fibonacci Trend Continuation | Midline/bands/Fib levels, continuation and reversal events, wrapper | Exported fixtures; opposite-flip exit is local policy |
| Uptrick Adaptive Trend Trail | Composite regime, adaptive Supertrends, trails, accepted events, wrapper | Exported fixtures; source account simulation excluded |
| RSI Probability Matrix | Source-gated entries, reference resolutions, causal bucket counts, wrapper | Target-first ambiguity explicitly flagged; counters are not option-ledger results |
| ICT Killzones + Pivots | Session extrema, breaks, range levels, causal session statistics and availability | Feature-only; D/W/M requires exact exchange boundary flags |
| Market Structure Break & Order Block | Zigzag, market direction, MSB events and wrapper | Box/zone arrays remain unported; statement-order fixtures needed |
| Support Resistance Channels | Confirmed pivots, channel snapshots/strengths, break events and wrapper | Equal-pivot convention needs fixtures |
| Volume-Weighted Order Block Zones | Causal zone creation, strength, invalidation, retests and snapshots | Feature-only; fixed calculation origin and fixtures required |

All implementations remain outside active proposal pools. Shared Pine seeds,
NA behavior and comparisons have local tests; flat-RSI builtin behavior and
several pivot/state edges still require actual TradingView outputs. Local
hand-computed tests and independent source review are not cross-platform parity.

Five selected scripts remain source-pinned without Python implementations:
AMD Po3, Volume Footprint, Structural Liquidity & POC Matrix, Setup Scanner,
and HTF Log-Regression Volume Profile. Footprint's `TradingView/ta/14` library
is pinned; its unused transitive `RelativeValue/3` dependency is documented as
pending. Native/intrabar modes remain subject to their separate data contracts.

No corrected freeze/build/evaluation or deployment has run. Campaign isolation,
the corrected downloader boundary, raw-history recovery pilot, actual server
inventory and a contract preview are recorded in
[readiness review](../reviews/2026-09-05-readiness-milestone.md).
The shared alert-format go/no-go remains in force for a production format change.
