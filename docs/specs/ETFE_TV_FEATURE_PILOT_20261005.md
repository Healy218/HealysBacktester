# ETFE TV feature component — October 5, 2026

Bounded successor component **ETFE-2.tv-components**, following ROADMAP's
first-run sequence. This does not close the full feature, frozen-input or
integrated resource/training pilot gates. All values remain raw-price,
final-vintage **diagnostics**, not admitted model features.

## Inputs and output

Use the selected fresh Alpaca normalization and calendar bound by
`etfe-causal-20261004-r0`. Reconstruct January 2–19 stock-session bars from
normalized minutes and compare the saved causal grid. Observe every January
18–19 closed bar for SPY/QQQ/VOO at 1/5/15 minutes. Keep the original 458,133
signal/target memberships and join every one to its ticker/timeframe/close.
No option observation is required to compute an underlying TV diagnostic.

The 96 fields in `ETFE_FEATURE_MAP_20261003.json` and its thirteen scope
parameters are authoritative. Pure numerical source kernels may be reused;
no old data, metadata, runtime configuration, feature arrays or models are
inputs. Fixed January 2 calculation origin, not an admitted history boundary.
Capture every transitive local numerical source, package version, input receipt,
readiness binding and this specification in the new immutable PLAN/source tree.
Use isolated `etfe-tv-features-20261005-r0`; never rewrite an earlier study.

## Projection and readiness

Compile the explicit registered formulas without eval. Prices relative to Close
and ranges divide by causal Wilder ATR14; percentages divide by 100; AMD phases
map idle/accum/sweepPending/manip/dist to 0/1/2/3/4. Nonpositive ATR is missing.
Write float64 values, uint8 missing masks and a reason for every field. The
PLAN's machine-readable bindings enumerate field-level prerequisite predicates.

- Gaussian direction/events/line/width require native width. Fibonacci state
  and events require bands. Uptrick state/events/trail require regime and gate.
- Structure state/events require both confirmed pivot pairs. SR events require
  a confirmed pivot; a channel strength requires its corresponding channel.
- Probability state requires signal and ATR; crossings also need the previous
  signal. Reference percentages additionally need same-side resolved outcomes.
- ICT membership is known from the observed RTH clock. Breaks require confirmed
  session levels; absent ASIA/LNDN ranges and breaks stay missing. No overnight
  bars are synthesized. Source-literal RTH resets remain local research.
- Order-block counts/retests require native ATR100 and volume-average history.
  AMD state/events/counts require compression-rank history.
- Setup events require positive ATR and their volume/EMA/VWAP/confirmed-pivot
  prerequisites; ORB requires all fifteen opening minutes. `or_done` itself is
  a known false before completion. HLC3 session VWAP uses completed raw minutes.
- Liquidity sweep checks need the preceding anchor; readiness needs a positive
  bin step, and POC requires native profile readiness.
- HTF delta requires positive directional volume; developing readiness requires
  regression availability. Completed
  readiness needs an observed completed regression. Completed POC is gated by
  its own readiness and becomes observable at the source's confirmation close.
- Footprint POC requires freshness; count/freshness flags need positive volume.
  Geometric volume allocation is an OHLCV approximation, not bid/ask flow.

Use native full-prefix recurrences and confirmation clocks. Missing source bins
remain grid rows and taint every later recurrence; never fill, compress or reset
history after gaps. Scope parameters are not a global warmup bar cutoff.
1m/5m HTF flags use actual session opens and 240/720-minute buckets; 15m uses
pairs of complete-calendar ordinals, unchanged across observation partitions.
Native availability must equal bar close. Any later supplied stock availability
is rejected, pending a separately versioned delayed-observation policy.

## Acceptance and resource scope

Single sequential writer, no worker pool. Maximum root 1 GiB, active compute
30 minutes; preserve max(100 GiB,20% disk) and max(2 GiB,20% RAM) reserves.
Record elapsed compute, peak RSS and actual output size. Predeclare two real
prefix boundaries per scope (January 18 close and January 19 midday), compare
all preceding observation values/reasons at rtol=atol=1e-12, and independently
perturb later stock OHLC and volume. Include 1/5/15m synthetic gap, cold-start,
zero-ATR, session/HTF, probability and validity-predicate tests.

Persist required native columns for transparent projection audit. An independent
scalar auditor recomputes ATR from fresh chart inputs and every projection,
prerequisite, mask, reason and event membership. This checks local projection
consistency, not independent reimplementation or exported Pine parity of the
thirteen native kernels. Actual one-scope stop/resume must retain existing
receipt/payload bytes. Component completion leaves dated actions, publication,
selection/session evidence, full schema, full phase-B/C demand and training open.
