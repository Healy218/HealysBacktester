# Handoff — October 3, 2026 — ETFE quote 404 diagnosis

## Selected work and outcome

User asked to investigate the Alpaca historical option quote 404s.
Diagnosis complete: the public historical-quotes route is unsupported.
Alpaca staff explicitly confirmed this limitation; 13 live GET controls showed
working historical trades and latest OPRA quotes for SPY, QQQ and VOO, while
six historical-route variants returned 404. Credentials/latest OPRA access work.
[Review](docs/reviews/2026-10-03-etfe-quote-404.md),
[portable evidence](docs/reviews/2026-10-03-etfe-quote-404.json).

ETFE-0 remains selected and open. The unresolved provider contract is an actual
historical quote-supply gap, not a request-format repair. No methodology changed.

## Selected artifacts and verification

- Setup: `nn_meta/validation/etfe-setup-20261003-r0/`.
- Plan SHA256: `8e43d74e2d89d9b3aaaf58d2a65f2acbc713dfa44f19466ee95af5279aa8e707`.
- New evidence: `probe-quotes-r1/DIAGNOSTIC.json`, per-request JSON and raw bodies.
  13 live requests, zero transport failures, all receipt/body/source hashes checked.
  Sandbox-only failed `probe-quotes-r0` retained; not provider evidence.
- New independent consumer: `scripts/diagnose_etfe_quotes.py`. Fixed allowlist,
  GET only, 13-request ceiling, fresh outputs, size limits and credential protection.
  Frozen setup producers remain unchanged; integrity verifier still passes.
- Original evidence: `probe-r1/PROBE.json` and `probe-boundary-r0/BOUNDARY.json`.
  All-three ETF samples reach January 18, 2024; global first timestamp unverified.
- Setup retains all 20 families and 25,353 ticker/variant combinations. Prior
  30 focused setup tests passed. Readiness remains false; no build/training launch.

## Next action and constraints

Resolve `ETFE.provider-contract`: evidenced Alpaca historical delivery outside
this public API, or an explicit user-approved methodology/scope change. Do not
repeat unsupported-route probes without new evidence. Latest snapshots and
prospective quote recording cannot backfill the fixed historical window.
Historical trade/bar modeling changes the inherited execution/feature contract.

ETFE is a brand-new expert: SPY/QQQ/VOO, 1/5/15-minute signals; V7 strategy/timing
specifications with the later midpoint/risk amendments. No V7 weights/checkpoints.
Start remains Alpaca's earliest options history, end October 2, 2026 inclusive.
No Massive quotes, including archived V7 copies. No synthetic spreads, feature
removal or silent date movement. Complete quote/contract/feature coverage and
causal execution/resource evidence are required before an expensive campaign.

## Preserved work

Previous handoff: [setup snapshot](handoff-history/HANDOFF-2026-10-03-before-quote-diagnosis.md).
V7 archive is verified complete on MRHA/v7: 2,847 shards, 325.63 GiB and 35,031
eligible local files reclaimed. [Audit](docs/reviews/2026-10-03-v7-archive-completion-audit.json).
V7 research and other unselected campaigns remain paused. No orders,
subscriptions, messages to Alpaca, streaming captures or deployments this turn.
Preserve unrelated dirty work and the secret root .env.
