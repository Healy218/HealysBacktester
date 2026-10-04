# Handoff — October 3, 2026 — ETFE Alpaca pull diagnosis

## Selected work and result

User asked to investigate Alpaca pulls for ETFE data while ETFE-0 remains active.
Historical trade/bar requests and multi-page retrieval work in the tested sample.
Old contract metadata and source provenance remain unresolved; no bulk capture,
integrated pilot, dataset build or training started. Four component contracts
remain declared. **ETFE-0.contract is open** on H1/R1/R2/P1.
[Diagnosis](docs/reviews/2026-10-03-etfe-alpaca-pulls.md),
[contract index](docs/specs/ETFE_CONTRACT_20261003.md),
[roadmap sequence](ROADMAP.md#etfe-first-run-sequence).

## Changes and evidence

- 40 live GETs: 37 HTTP 200, three intentional HTTP 400 feed controls; no
  transport failures, authentication failures or rate limits in these runs.
- Historical trades reject `feed` itself, including opra and indicative.
  Omit it on this route; latest-data feed selection is a separate interface.
- Twelve Jan 18, 2024 opening-minute trades reproduce three ETF bars' OHLC,
  volume/count and rounded VWAP. Six pages recover the same trade occurrences.
- February/March metadata samples report multiplier 0, size/deliverables 100.
  June 2024 and later samples report multiplier 100. Preserve raw anomalies.
- OCC memo 53848 explains QQQ's adjusted strike and 100-share delivery.
- Nasdaq alert 2026-10 establishes VOO's 16:00→16:15 ET close transition
  effective February 25, 2026. Full dated session coverage remains open.
- More pre-floor long-dated price samples are empty. Catalogue records can
  predate available prices; neither result proves a provider-global floor.

## Stopping point and next actions

1. H1: obtain precise provider history floor/scope explaining January observations
   versus published February coverage; do not shorten the requested date window.
2. R1: resolve old zero multipliers and complete dated contract eligibility,
   adjustments, delivery/exercise and availability evidence. Current expired
   catalogue responses are not historical as-of chains.
3. R2: incorporate VOO's sourced transition into complete dated class/expiration/
   early-close rules. The named Nasdaq ambiguity is explained, not all R2.
4. P1: obtain explicit historical-trade route provenance confirmation. Feed
   selection is unsupported; sample agreement with OPRA bars is scoped evidence.
5. Seal an immutable contract successor, then the bounded ETFE-4.pilot in ROADMAP
   order. These API controls are not the integrated capture/build/train pilot.

No provider message was sent; the review records concrete support questions.
Historical quotes remain unsupported. Preserve the VWAP choice, all three ETFs,
all strategy families and fixed October 2 end; no Massive fallback.

## Selected artifacts and verification

Setup: `nn_meta/validation/etfe-setup-20261003-vwap-r1/`; plan SHA256
`3995e19af4462e24f7e570ba8f39923ae2cedc8b4d3f1cdd35b1a2a70169ac64`.
Pull runs: `nn_meta/validation/etfe-alpaca-pulls-20261003-r1/` and `-r2/`;
sandbox-only r0 retained. [Portable receipt](docs/reviews/2026-10-03-etfe-alpaca-pulls.json)
binds 88 ZIP members, both source versions, reports and raw HTTP receipts.
Six focused offline tests pass; existing portable contract verifier still passes
with source gate open. Exact pointers: [CURRENT_STATE](docs/CURRENT_STATE.md#october-3-etfe-setup).
Preserve unrelated dirty/untracked work and frozen predecessor artifacts.
V7 archive remains complete; other campaigns remain paused. No experiment verdict
or maturity increase. [Previous handoff](handoff-history/HANDOFF-2026-10-03-before-etfe-alpaca-pulls.md).
