# Handoff — October 3, 2026 — ETFE completed-minute VWAP

## Selected work and outcome

User approved option trade/bar methodology and delegated choosing high/low
midpoint or VWAP. Selected completed one-minute **VWAP**, with no fallback.
Implemented the causal reference component, v2 scope, independent preparation
consumer, new source snapshots and integrity verifier. No full execution engine,
training or deployment. [Contract](docs/specs/ETFE_VWAP_20261003.md),
[review](docs/reviews/2026-10-03-etfe-vwap.md), [TODO](TODO.md).

`ETFE.pricing-basis` is complete. ETFE-0 remains open for data/feature contracts
and boundary evidence. The historical quote acquisition requirement for pricing
is superseded; do not retry the unsupported route or reopen the user choice.

## Selected artifacts

- Selected: `nn_meta/validation/etfe-setup-20261003-vwap-r1/`.
- Plan SHA256: `3995e19af4462e24f7e570ba8f39923ae2cedc8b4d3f1cdd35b1a2a70169ac64`.
- Scope: `docs/specs/ETFE_SCOPE_VWAP_20261003.json`.
- Preparation/verification: `scripts/prepare_etfe_vwap.py` and
  `scripts/verify_etfe_vwap.py`; [commands](docs/reference/ETFE_SETUP.md).
- Price helper: `nn_meta/etfe/vwap_reference.py`. Reference observation only,
  not a fill. Validate contract/session/1Min/feed provenance in its consumer.
- Preserved predecessor: `nn_meta/validation/etfe-setup-20261003-r0/`.
  Original integrity verifier still passes; old sources/specs were not edited.
  Historical probes and quote diagnosis remain bound to that original setup.

46 focused tests passed; both setup integrity checks, source snapshots, catalog
byte identity and overwrite refusal passed. Six existing Alpaca 1Min samples
returned their actual VWAP through the component; no new provider calls.
All 20 families/25,353 ticker variants retained. Readiness remains false.

## Timing and next action

Use only completed bars: modeled availability at end + 1s, or later captured
availability. Maximum reference age 60s from bar end, positive VWAP/volume/count.
No within-bar lookahead, high/low fallback, fabricated spread or forward filling
across missing minutes. Historical revision/publication timing is still unverified.
The 1s entry latency, 60s deadline, fees/slippage and 12.5% premium stop remain.

Next: explicit trade/bar replacement map for quote-dependent features, source
coverage and timestamp/revision evidence, then causal execution/liquidity/cost
validation. Missing held marks cannot erase liabilities or imply successful exits.
Preserve all nonquote feature scope, strategy families and parameters, dated DTE,
expiry/roll/stock-delivery rules and portfolio/evaluation requirements.

Dates remain earliest Alpaca options history through October 2, 2026 inclusive;
exact global first timestamp remains open (January 18, 2024 sampled in all ETFs).
SPY/QQQ/VOO only, signal bars 1/5/15m, option reference bars 1m, Alpaca only.
No Massive inputs, V7 weights/checkpoints, bulk capture or expensive campaign.

## Preserved work

[Prior handoff](handoff-history/HANDOFF-2026-10-03-before-vwap-amendment.md).
V7 archive remains verified complete on MRHA/v7; research stays paused.
Other unselected campaigns stay paused. Preserve unrelated dirty work and .env.
