# Handoff — October 3, 2026 — ETFE contracts and source blockers

## Selected work and result

User selected ETFE-0: resolve history boundary and complete feature, execution,
evaluation and acquisition contracts in ROADMAP order. Four definitions are
now declared. **ETFE-0.contract remains open** on source evidence H1/R1/R2/P1.
[Contract index](docs/specs/ETFE_CONTRACT_20261003.md),
[review](docs/reviews/2026-10-03-etfe-contract.md),
[roadmap sequence](ROADMAP.md#etfe-first-run-sequence).
No integrated pilot, bulk acquisition, dataset build or training was launched.

## Changes and evidence

- Complete 221-field inherited inventory; thirteen source scopes and 442 model
  inputs including missingness masks. Quote fields receive new trade/bar names.
- Execution defines integer contracts, 1% participation, pre-cost 12.5% leg stop,
  partial exits, missing valuation, settled-cash rolls and physical delivery.
- Three temporal folds, ten-session embargo/full-horizon purge, 84 required fits
  including final refits, fixed thresholds/baselines/acceptance and abstention.
- Acquisition defines sources, resumable page chains, corrections/missingness,
  full demand and a bounded resource-pilot workload with stop/reserve rules.
- Ten live Alpaca GETs completed at 20:08:37 Central. Pre–January 18 samples
  were empty only for three named contracts. Current January 2024 metadata
  includes size 100, multiplier 0 and T+1; it is not dated settlement evidence.
- Fixed civil end is 2026-10-03T04:00:00Z exclusive. October 2 stock session is
  13:30–20:00 UTC. Dated option-class hours remain separately unverified.

## Stopping point and next actions

TODO closes four definition tasks, not source admission. Resolve these before
ETFE-4.pilot under the authoritative ROADMAP sequence:

1. H1: authenticated provider-global first-history timestamp/scope, or complete
   global inventory. January 18 first samples cannot establish that boundary.
2. R1: feasible complete historical discovery and dated contract/adjustment,
   multiplier/deliverable/exercise and weekly-eligibility evidence.
3. R2: dated class/expiry/early-close hours. Current Nasdaq web/PDF lists differ
   on VOO's 16:15 inclusion; do not choose a universal close from current text.
4. P1: source confirmation for historical trades versus indicative feeds.
   Trade conditions are mapped; no-ID samples retain page/row occurrence identity.
5. Seal an immutable contract successor after resolution; then run the bounded
   ETFE-4.pilot, preserving full strategy/universe/date scope and measured limits.

No provider message has been sent. The remaining unknowns are source facts,
not a request to pick a new date, remove features or restore Massive quotes.

## Selected artifacts and verification

Setup remains `nn_meta/validation/etfe-setup-20261003-vwap-r1/`, plan SHA256
`3995e19af4462e24f7e570ba8f39923ae2cedc8b4d3f1cdd35b1a2a70169ac64`.
Contracts and machine registries live under `docs/specs/ETFE_*20261003.*`.
[Portable receipt](docs/reviews/2026-10-03-etfe-contract.json) binds the evidence
ZIP, 42 source snapshots, contracts and ten raw live controls. Verify with
`./venv/bin/python scripts/verify_etfe_contract.py`; setup integrity is separate.
[Exact pointers](docs/CURRENT_STATE.md#october-3-etfe-setup).

Preserve unrelated dirty/untracked work and all previous setup artifacts.
V7 archival stays complete; other workstreams stay paused. No EXPERIMENTS
verdict or maturity increase. Previous handoff is archived
[here](handoff-history/HANDOFF-2026-10-03-before-etfe-contract.md).
