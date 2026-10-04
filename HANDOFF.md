# Handoff — October 3, 2026 — ETFE first-run plan

## Selected work and result

User requested the full plan through a working ETFE expert that completes a
build/freeze/train run, plus notes updated under document ownership rules.
Documentation completed; no acquisition/build/training campaign launched.
[Full sequence](ROADMAP.md#etfe-first-run-sequence),
[technical acceptance](docs/specs/ETFE_FIRST_RUN.md),
[documentation review](docs/reviews/2026-10-03-etfe-first-run-plan.md).

ROADMAP owns all stages and dependencies. TODO owns current ETFE-0 actions only.
The sequence is contract → measured resource pilot → acquisition/input freeze →
causal strategies/features → execution/labels → full build/recovery → dataset and
experiment freeze → all declared fits → evaluation/model freeze → expert proof.
Resources are measured before bulk work, with final admission before training.

## Current implementation and artifacts

Selected setup: `nn_meta/validation/etfe-setup-20261003-vwap-r1/`.
Plan SHA256: `3995e19af4462e24f7e570ba8f39923ae2cedc8b4d3f1cdd35b1a2a70169ac64`.
Current scope: `docs/specs/ETFE_SCOPE_VWAP_20261003.json`.
[State pointers](docs/CURRENT_STATE.md#october-3-etfe-setup),
[existing commands](docs/reference/ETFE_SETUP.md).

The completed-minute VWAP reference and immutable setup are implemented; prior
46 focused tests and six saved Alpaca sample checks passed. Both predecessor and
VWAP integrity checks pass. All 20 families/25,353 ticker variants are retained.
Full acquisition, feature replacement, execution, dataset and training are open.
No ETFE input/dataset/model freeze or full-build/training receipt exists yet.

## Next selected phase — ETFE-0

1. Verify exact earliest provider timestamp and fixed-window boundaries.
2. Complete inherited feature inventory and explicit trade/bar replacement map.
3. Declare full VWAP execution/missingness/liquidity and end-boundary contracts.
4. Declare targets, folds, finite trials, baselines and acceptance/decision policy.
5. Derive required capture demand and representative bounded resource-pilot plan;
   close the source/feature/execution contract before dependent bulk work.

Use TODO for the task details. Do not move later roadmap work into a competing
queue or reopen the already accepted VWAP choice. Definition of done includes
separate dataset and model freezes, all fits completed, evaluated verdict and
clean-process inference/replay/restore. A rejected model can finish a valid
experiment; it cannot be promoted. Data/causality failure blocks completion.

## Constraints and preservation

SPY/QQQ/VOO only; 1/5/15m signals; one-minute completed option VWAP references;
Alpaca-only options, earliest history through October 2, 2026 inclusive.
No Massive inputs, old model weights, invented quotes, silent date changes,
within-bar lookahead or automatic deployment. Existing readiness flags stay false.
Memory/storage/ETA await measured workload; do not assume MRHA capacity.

[Previous handoff](handoff-history/HANDOFF-2026-10-03-before-etfe-first-run-plan.md)
and [previous TODO](handoff-history/TODO-2026-10-03-before-etfe-first-run-plan.md)
are archived. V7 archive remains complete; V7 and unselected campaigns stay paused.
Preserve unrelated dirty work and .env. Planning adds no EXPERIMENTS verdict or
maturity score increase. Next implementation starts with the current ETFE-0 tasks.
