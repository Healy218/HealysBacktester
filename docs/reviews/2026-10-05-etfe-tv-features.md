# ETFE thirteen-source TV feature components

Completed **ETFE-2.tv-components**: all **96 registered TV-derived projections**
on fresh Alpaca stock bars, across SPY/QQQ/VOO and 1/5/15-minute charts.
[Component contract](../specs/ETFE_TV_FEATURE_PILOT_20261005.md),
[machine receipt](2026-10-05-etfe-tv-features.json).

The selected immutable root is `nn_meta/validation/etfe-tv-features-20261005-r0/`.
Plan SHA256: `796a24e7a3a659513f8317fbdd89f65d6c9f28afbf5e40f527cd6f369c438bab`.
No old market data, metadata, configuration, feature arrays or models were used.
The reused source files are mathematical kernels bound by exact source hashes.
No new downloads, simulated execution, labels, training or deployment occurred.

## Scope and measured result

The study rebuilds the January 2–19 stock prefix from selected normalized
minutes, reconciles it to the preceding causal study, and observes January
18–19. All **2,964 closed bars** are retained, with **458,133 original logical
signal/target memberships**. An event does not need an option acquisition
candidate to retain its underlying TV diagnostics. This preserves the existing
262,698 events without a prior-date candidate rather than dropping them.

| Native source | Registered projections |
| --- | ---: |
| Gaussian | 6 |
| Fibonacci | 6 |
| Uptrick | 5 |
| Market structure | 5 |
| Support/resistance | 6 |
| RSI probability | 7 |
| ICT sessions | 16 |
| Volume order blocks | 6 |
| AMD | 6 |
| Setup | 15 |
| Liquidity POC | 6 |
| Higher-timeframe profile | 7 |
| Geometric footprint | 5 |
| **Total** | **96** |

Of 284,544 value cells, **256,822 are finite and 27,722 explicitly missing**.
Every field has a float64 diagnostic value, uint8 missing mask and reason.
Readiness is field-specific: initialized state/event zeros cannot stand in for
unavailable history. ATR normalization, confirmed pivots, resolved probability
history, valid profiles and completed opening ranges remain required where
applicable. All output model-feature admission flags are false.

The complete calendar determines HTF anchors: actual opens for 240/720-minute
buckets and immutable session-ordinal pairs for 2D. Setup ORB/VWAP uses completed
raw minutes. ICT ASIA/LNDN membership is false on observed RTH bars; absent
session ranges/break levels stay missing. Geometric footprint remains an OHLCV
approximation, not measured bid/ask order flow. A missing source bin taints all
subsequent recursive values without filling, dropping or restarting history.

## Validation and recovery

**143 focused ETFE tests passed**, including fourteen new TV tests. They cover
all thirteen sources at every timeframe, cold starts, missing-minute taint,
zero ATR/directional volume, readiness predicates, delayed publication rejection,
HTF anchors and changes to future observations.

For all nine real scopes, January 18 close and January 19 midday define eighteen
prefix checks. Every preceding value/reason matches a separate prefix run;
eighteen extreme future-price/volume perturbations also match. Numerical
rtol=atol=1e-12 is unchanged. No future input is used to fill a missing value.

An independent scalar auditor rederived ATR and all 284,544 projections,
prerequisite decisions, masks and reasons from retained native fields. It also
reconciled all event ordinals to the exact ticker/timeframe/close observation.
This is independent projection reconciliation, **not an independent native-kernel
implementation or exported TradingView/Pine parity proof**.

Actual one-scope process stop/resume retained four receipt/payload hashes and
computed the remaining eight scopes. Total component compute **76.14 seconds**,
peak RSS **1,010,085,888 bytes (0.94 GiB)**, root **11,186,177 bytes**, including
27 Parquet payloads totaling 10,547,061 bytes. These are bounded component
measurements, not integrated capture/build/train resource forecasts.

The [evidence ZIP](2026-10-05-etfe-tv-features-evidence.zip) retains 58 source,
plan, receipt and audit members plus a checksum inventory for all 27 local
Parquet payloads. ZIP SHA256:
`0ad7b9d3b1c6fcc95d2e17e44b02db34ad1fb6a281e325b5272c2b92f3461172`.

## Option-window clarification and remaining work

The preceding ten option diagnostics remain unchanged. Of 4,739 windows,
**2,936 lack at least one of the ten**: 2,714 have unresolved observations,
30 are outside stock-session scope, 189 have ambiguous equal-time trade
ordering, and three have trades without the required bars. These groups are
disjoint here. The last two groups retain partial values; the first two have
all ten missing. The other 1,803 windows have all ten values. Missing data are
not converted to zeros or interpreted as confirmed no trading.

The fifteen shared stock, ten option and 96 TV formulas are diagnostic
components, not a completed/admitted 221-field schema. Remaining work includes
daily stock/option context, event/contract/sector/parameter fields and variant
projections; dated actions, option terms/hours and publication/selection evidence;
full phase-B/C demand; and the integrated ETFE-4.pilot. Usable history remains
unresolved. Earlier completed acquisition and feature evidence stays complete.
