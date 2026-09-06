# Experimental TradingView model feature matrix

`nn_meta/tradingview_features.py` projects the numerical/state scopes of all 13
pinned publications into **96 fixed float64 columns**. It does not admit them to
a model or proposal pool. Contract: `2026-09-06-tv13-features-v1`.

The existing source files, numerical adapters and licenses remain authoritative.
The bridge uses their pinned adaptation-manifest defaults. It checks the source
registry before and after calculation and records all 13 fixture identities,
the projection hash, inputs, actual parameter bindings and context provenance.
New calculations in this module do not establish TradingView execution parity.

## API and required context

```python
from nn_meta.tradingview_features import (
    feature_requirements, feature_schema, validate_feature_inputs,
    tradingview_features,
)

result = tradingview_features(
    completed_bars,
    minimum_tick=instrument_minimum_tick,
    timeframe_flags=exact_flags,
    dependency_metadata=context_provenance,
    as_of=observed_at,
    session_policy="source_literal",  # explicit RTH source behavior
)
features = result.values
available_at = result.available_at
```

`feature_requirements()` describes dependencies without calculating features.
`validate_feature_inputs(...)` rejects missing, late, malformed or unsupported
context before invoking ports. `feature_schema(minimum_tick=..., session_policy=...,
vwap_mode="reset_flags")` returns every column and its transform, source IDs and
the exact fixed parameters for capture/preflight tooling.

- Bars are nonempty, finite `Open/High/Low/Close/Volume`, with positive Close and
  nonnegative Volume. Their unique increasing timezone-aware index labels 15m
  bar opens. Overlapping or off-grid bars fail. The caller supplies completed
  bars and an explicit timezone-aware `as_of`; any later bar close fails.
- `minimum_tick` is the instrument's explicit `syminfo.mintick`. It is passed
  to Uptrick, ICT, AMD and geometric Footprint. It is never inferred from price
  differences. Input price/feed/session/adjustment settings must match capture.
- `timeframe_flags` is exactly aligned to bar opens and normally has boolean
  `vwap_reset`, boolean `htf_change`, and timezone-aware `available_at`. Every
  flag must be known by its corresponding bar open. The HTF expression is
  exactly Pine `timeframe.change("2D")`, the author's automatic period at 15m.
  Calendar bucketing or UTC resampling is not a substitute.
- Alternatively, pass `vwap_observations`, an aligned frame containing `vwap`
  and timezone-aware `available_at`, and omit `vwap_reset` from `timeframe_flags`.
  Each nonmissing VWAP must be available by the matching bar close. This binds
  actual observed source VWAP without assuming the implicit `ta.vwap(hlc3)`
  reset equals `timeframe.change("D")`. Supplying both alternatives fails.
- `dependency_metadata` requires nonempty `symbol`, `calendar_id`, `htf_period`
  (exactly `2D`), `vwap_anchor`, `timeframe_flag_basis`, `chart_session`, and
  `history_origin` strings. The declared aware history origin must equal the
  first supplied bar. Metadata is recorded caller provenance, not independently
  verified exchange or TradingView evidence.

Strict session coverage is the general API default. On consecutive RTH-only
days, Setup's default 09:30–16:00 membership stays true across the overnight
gap. `source_literal` preserves that source behavior: it does **not** invent an
outside-session bar or reset the opening range the next morning. The matrix
contains `tv_setup_session_gap`, and metadata records the policy and gap count.
A matching fixture must use the same chart session. ICT's narrower sessions
retain their own strict gap checks; unsupported hidden session transitions fail.

No AMD HTF bias observations are needed because the pinned source default has
`use_htf_bias=False`. ICT D/W/M features are outside this compact projection, so
no D/W/M flags are synthesized. The four source-default ICT windows remain
ASIA 20:00–00:00, LNDN 02:00–05:00, NYAM 09:30–11:00 and NYPM 13:30–16:00 in
America/New_York.

## Feature scope

Every name begins with `tv_<prefix>_`. Exact full column names and order are in
`FEATURE_NAMES`, derived from the explicit `FEATURE_SPECS`, and available through
`feature_schema()`. Added port columns cannot silently expand the matrix.

| Prefix | Pinned publication | Columns | Selected information |
|---|---|---:|---|
| gaussian | AqRNdhlR v1 | 6 | Direction, smoothed efficiency, two source alerts, trend-line distance, width |
| fibonacci | U7CZ8jtj v1 | 6 | Direction, continuation alerts, flip, midline distance, source volatility |
| uptrick | f4N0F439 v1 | 5 | Direction, regime, two source alerts, inner trail distance |
| structure | DkE7UniD v9 | 5 | Market direction, two MSB alerts, last confirmed high/low distances |
| sr | Ej53t8Wv v6 | 6 | Inside-channel state, two alerts, strongest channel bounds and strength |
| probability | c25U5rsF v1 | 7 | RSI, two raw signals, active side, resolved count, two reference win fractions |
| ict | nW5oGfdO v19 | 16 | Per enabled session: membership, high/low break events, observed completed-range average |
| order_blocks | KcnNgwDI v1 | 6 | Bull/bear active counts, retest labels, latest bull/bear trigger distances |
| amd | hkKioUnL v1 | 6 | Phase, long/short source entries, compression rank, range width, resolved count |
| setup | XWuYNmhD v2 | 15 | Long/short raw events for all six identities, VWAP distance, ORB completion and gap flags |
| liquidity | I8HrQVRv v1 | 6 | Top/bottom sweeps, profile-ready state, POC and liquidity-level distances |
| htf | kwXpL7yZ v4 | 7 | Log-regression slope, directional volume delta, regression/POC distances, completed POC and readiness |
| footprint | Tm1cGCPD v4 | 5 | Geometric buy fraction, profile tilt, fresh chart POC distance, freshness, selected table-window bar count |

Setup identities retain source order: VWAP, EMA, BRT, SWEEP, DIV, ORB. They are
separate events, so simultaneous source setups are not collapsed into a new
entry policy. Feature-only sources supply levels, counts and their own label
events; the bridge invents no trade direction or entry/exit rule for them.

AMD phase encoding is fixed: idle=0, accum=1, sweepPending=2, manip=3, dist=4.
It describes source state, not a ranked probability. RSI reference rates become
available only from resolved prior/current-close outcomes; absent samples are
NaN. Their source conflict ordering remains unchanged. These underlying-price
reference statistics are not option returns or an independently validated edge.

## Normalization and causality

Price levels become `(source_level - current_Close) / Pine_ATR14` and use suffix
`_distance_atr14`. Price ranges divide by that same ATR and use `_atr14`.
Source percentages divide by 100 and use `_fraction`. The HTF log-regression
slope is already dimensionless per bar and remains in source units. Source
counts, directions and exact boolean events retain their meaning; events are
represented as float 0/1. No expanding/global standardization is performed.

ATR14 uses completed current bars and source warmup. Zero ATR, unformed levels,
missing observations and uninitialized statistics stay NaN. There is no fill,
backfill or clipping. Liquidity POC requires its ready flag, HTF POCs require
their respective current/completed ready flags, and Footprint POC requires a
fresh calculation. A persisted stale Footprint chart level is not presented as
a fresh current feature.

All feature rows become available at **bar open + 15 minutes**, including
confirmed pivots whose drawings point to older bars. Completed HTF profiles
first appear on the first observed bar of the next period. Availability is
returned separately from the numeric matrix; callers must enforce it when
joining features to decisions. Histories must retain the same first calculation
bar across training, replay and inference. The bridge has no bounded-memory
incremental-state implementation; recomputation consumes the fixed full prefix.

Footprint uses the declared geometric engine only. Its buy/sell allocation is
a modeled OHLCV split, not observed aggressor volume. Source-default window=5,
view_ticks=5, profile_period=23 and resolution=100 are preserved. Unused Simpson
residual/overlap diagnostics are explicitly disabled for this projection;
unused bins/chart objects are not returned. Native and intrabar engines are
unsupported here and are never approximated by an implicit fallback.

## Validation and external gate

Local tests cover all 13 direct adapter projections, flat-market known results,
source-default order-block confirmation timing, RTH source-literal behavior,
warmup and session-boundary prefix equality, future price/volume/context
perturbation, exact observed VWAP, timestamp units, and invalid dependencies.
These are local source/contract tests, not exported-Pine parity fixtures.

POC and Footprint profile histories require fixed-origin terminal Bar Replay
observations to match their upstream `barstate.islast` scope. A normal historical
CSV cannot establish that historical profile parity. HTF flags, actual VWAP or
verified anchors, instrument tick, chart settings, availability, and ATR14 used
for normalization must be bound to the same capture. Registry/feature identities
must match the captured implementation. `external_parity` and `model_admission`
remain false in every result; an independent integration gate owns admission.

`setup.session_gap` is a local timestamp diagnostic, not an original Pine plot.
Footprint freshness and completed HTF snapshots also require reviewed
instrumentation or comparison against the correctly ordered terminal captures.
For RTH-only charts, inactive ASIA/LNDN ranges can remain entirely NaN; parity
checks must compare missingness and false membership/events rather than require
finite observations from absent sessions.

## Measured local cost

One synthetic full-prefix calculation on the development machine, while other
research work was running, took 2.50 seconds for 1,000 bars and 43.90 seconds for
15,000 bars. The 15,000 × 96 matrix occupied about 12.17 MB including its index.
At 15,000 bars, Footprint used 23.70 seconds, AMD 9.19 seconds and HTF 4.89 seconds.
These are observations, not resource or latency guarantees; session shapes,
profile searches and source state can change cost. The benchmark used explicitly
synthetic 24x7 flags, so it provides no exchange-calendar or source-parity evidence.
Compute once for each fixed history and join the resulting matrix; repeatedly
recomputing the full prefix for every model row would multiply this cost.

The focused bridge suite passed 35 tests. Broad source-port regressions and
external fixture gates are separate from this bounded bridge verification.

## Directional proposal bridge

`nn_meta/tradingview_proposals.py` exports `STRATEGIES`, `SWEEP_GRIDS`, source
metadata and exact fixed-input declarations. The eight families are
`tv_gaussian`, `tv_fibonacci`, `tv_uptrick`, `tv_msb`, `tv_sr`,
`tv_rsi_probability`, `tv_amd` and `tv_setup`. Seven have one source-default
column. Setup has its six typed identity columns with the same default stop
and timeout. Selecting a Setup column retains all six identities in the source
book, preserving competition, accepted entries and priority.

Its sweep/single API requires explicit `context`, using the feature API's
keyword fields. The ordinary proposal router obtains that mapping from
`bars.attrs['v6_tradingview_context']`. A training prefix slices flags and
observed VWAP to that exact prefix, retains the declared first calculation bar,
and caps `as_of` at its last bar close. Suffixes and isolated windows fail.
Internal calculation copies discard routing attrs; the caller's context is
unchanged. Frozen `setup_identity` values remain strings through portfolio
parameter recovery and exact replay selection.

These grids reject nondefault parameters or added optimization combinations.
The other five sources remain features. In particular, no native footprint,
POC, zone or session state becomes a fabricated directional trade event.
Proposal exits and source-reference book limits are recorded separately from
source alert meaning. Calling the registry does not enable a pool, certify
external parity, or replace the options execution ledger; integration owns
those gates.

`REQUIRED_OUTPUT_EVENTS` also exports the exact source booleans consumed by the
eight wrappers, keyed by publication ID. External proposal evidence must cover
these in addition to the model-feature fields. In particular, Setup's accepted
per-identity entries and exits are distinct from its raw setup conditions;
feature-only comparisons of the raw flags do not validate proposal execution.
