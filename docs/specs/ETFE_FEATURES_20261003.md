# ETFE feature definitions

This is the declarative feature contract for ETFE-0.feature-map, not a finished
feature implementation. The [machine registry](ETFE_FEATURE_MAP_20261003.json)
enumerates every one of the 221 inherited model fields in order, with disposition,
new name, formula, source, availability, window, warmup and missingness. It also
pins all thirteen source calculators and their defaults. Source feasibility
blockers live in the [source contract](ETFE_CONTRACT_20261003.md).

## Schema and availability

Use `etfe-trade-bar-features-v1`. Replace the ten `opt_tick_*` fields with ten
explicitly named trade/bar fields. Rename seven daily option-derived fields
with an `etfe_` prefix because VWAP-based context changes their meaning.
Replace `timeframe_30` by `timeframe_1`; retain 5/15 and all other scope.
The schema has 221 values plus 221 `missing__<name>` indicators: **442 model
inputs** in registry order, values first, indicators second. Values are nullable
float64 in the dataset, masks uint8; training converts finite transformed values
to float32. No IDs, outcomes, timestamps or availability fields enter the model.

Each row keeps proposal/variant/security/contract IDs, target and actual DTE,
signal-open/close, feature-as-of, source hashes, coverage status and a reason per
missing value. Logical identity is `(security, variant, direction, signal_close,
target_DTE, selected_contract)`; sharing physical arrays cannot discard logical
memberships. No model-ready row may contain an input available after decision.

Underlying features use complete session-aligned 1/5/15m OHLCV. Causal action
adjustments affect only information known in that epoch; execution and strike
selection use contemporaneous raw prices. Never use today's back-adjusted chart
without its dated action reconstruction. The pinned technical formulas are
written per field in the registry; bar counts remain bar counts at each timeframe.

At a signal close `t`, for timeframe `m`, option features use the `m` one-minute
bins in **[t-(m+1) minutes, t-1 minute)**. Each bin must be fully captured; its
bar end + 1 second must be <= t. This deliberately avoids using the bar ending
at t before publication. With captured later availability, omit unavailable
observations and mark the window missing; do not shift the window or change the
selected contract. All windows stay within the contract's regular session.
At the first session signal there may be no complete window.

Contract selection is frozen at signal close from prior-date observation and
dated-reference evidence under the execution contract, before examining the
feature window or any fill. A missing window cannot trigger a search for a more
profitable contract. Execution references may differ from feature bars because
execution occurs after signal close.

## Quote replacement semantics

Trade dispersion, bar freshness and tick-rule direction do not estimate a
spread, resting size, quote update rate or aggressor side. The registry replaces
these meanings and names explicitly. High/low is permitted only for a named
dispersion feature, never as a fill-price fallback. For trade statistics retain
condition policy, corrections, native IDs, exchange, event timestamp and modeled
availability. A trade without a verified applicable condition/availability rule
does not enter a model feature.

The research feature condition allowlist is H/I/J/S and lowercase a through s,
restricted to the dated regular session. Exclude A–G, t/u, v and unknown codes;
retain excluded counts/volume in audit metadata. This follows the price-and-volume
contributors in [Alpaca's aggregation FAQ](https://docs.alpaca.markets/us/docs/market-data-faq),
with an explicit RTH-only exclusion for v. Missing condition is not a regular
trade. H includes a late opening print: its event time plus one second is only
the declared final-vintage availability model, not known reporting time.
Reconciliation must respect that provider bar volume/count can include prints
which do not contribute to VWAP; do not demand VWAP=sum(p*s)/provider_bar_volume.

Trade signs use price changes against the immediately previous eligible trade
within the same window: +1, -1 or the preceding nonzero sign for equal prices.
The first trade and leading equal-price trades are unclassified. There is no
quote test. Equal-time records need a provider-defined total order; if unavailable,
the signed/classified fields are missing with `ambiguous_order`, not arbitrary
ordering by price. No last trade is borrowed across the window boundary.

Complete no-trade bins have zero counts/volume and no price. A complete empty
window has zero count/volume rates and bar-presence fraction; price/direction
ratios are missing. Uncaptured windows have missing statistics throughout,
not zeros. Entry execution still independently requires a positive fresh bar.

## Daily context

Retain realized log-return volatility over 5/21 consecutive sessions and beta
over 60 paired daily returns against SPY, all available next regular open.
SPY is already in the tradable universe; no additional market ticker is required.
Use as-of action-adjusted daily returns and raw closing spot for option inversion.

For each prior session, discover **all rights/strikes with actual 1–45 DTE**.
For each contract choose its last valid one-minute VWAP with bar end in
[stock_close-60 seconds, stock_close]; it must be available by next open. For
surface inclusion require premium >= $0.20 and positive dated strike. The ATM
band is abs(log(K/S)) < 0.01. Infer European Black–Scholes **proxy** IV at fixed
r=0.0425, q=0.012 and T=calendar_DTE/365; these are inherited engineering
assumptions, not observed historical rates or an American-option valuation.
Solve on sigma [0.000001,5], 100 bisection iterations, price tolerance 1e-8;
prices outside model bounds produce NaN with reason. Do not clamp to a bound.
Median eligible IV for 1–20 DTE is near, 21–45 far. Derived slope, five-session
change, SPY context and RV-minus-IV use these new fields and names.

Put/call ratio uses summed daily minute-bar volume for all discovered eligible
1–45 DTE contracts passing the same closing premium threshold, then clips the
ratio to [0,5] as in the inherited context. Record both raw ratio and clipped
value in audit metadata. A zero call denominator is missing. No daily IV/ratio
forward-fill: this expressly removes the inherited unbounded surface carry.
Natural lack of ATM observations is missing; incomplete catalog/capture is an
input failure. Missingness imputation cannot make a broken daily capture valid.

## Thirteen TradingView scopes and warmup

The registry preserves gaussian, fibonacci, uptrick, structure, sr, probability,
ict, order_blocks, amd, setup, liquidity, htf and footprint. Every projected
field names its calculator/field, transform and validity predicate; pinned source
bytes and default parameters are part of the formula. This includes the five
feature-only publications; none acquires an invented entry/exit strategy.

Run native recurrences from the fixed history origin, retain native minimum
periods/confirmation delays, and never backdate pivots or resolved outcomes.
All lookback and state parameters are enumerated in `tv_scopes[].parameters`.
An event is zero only after the source can actually determine absence of an
event. Before readiness, preserve NaN and a warmup reason. Strategy signals
must satisfy their native indicator prerequisites, without imposing an arbitrary
global burn-in that removes an entire family or timeframe.

Use the inherited local RTH chart policy: ICT's ASIA/LNDN intervals have no RTH
bars, so their range values are unavailable and observed RTH in-session flags
are false. They are not reconstructed from nonexistent overnight ETF trading.
Preserve the source-literal reset behavior and label this local research, with
external Pine parity still unverified. HTF mapping is 1m→240m, 5m→720m,
15m→2D. Intraday anchors use actual stock-session open; 2D pairs use the complete
calendar's session ordinal anchored at the history-origin session, not at each
partition. Both daily and indicator histories share that immutable origin.
Setup ORB uses all 15 completed opening minutes; HLC3 underlying session VWAP
is a separate indicator from the option execution VWAP. Geometric footprint
remains a bar-derived approximation, not observed bid/ask order flow.

Zero denominators, no profile, no resolved probability reference, natural
no-trade intervals and cold-start history are legitimate typed missingness.
Missing raw capture, unidentified actions, unknown availability or an incomplete
required scope block feature admission. Parameter fields absent for a family
are structural NaNs; constant ETF sector one-hots remain real metadata, not
missing quote values. All three symbols map to `idx_etf` with dated identity proof.

ETFE-2 must validate all 25,353 ticker/variant combinations, every field and
timeframe, prefix invariance, partition/batch invariance and source-direction
parity before schema admission. Numerical agreement of old V7 components is
not an ETFE whole-window coverage result.
