# Handoff — October 7, 2026 — ETFE v5 closed as failed; 2026 test unspent

## Focus and result

- **v5 training** (`etfe-training-v5-20261007-r0`): 82 / 84 fits. All 63
  validation fits are complete. `final/nn-return_huber-29` and `-47` were
  OOM-killed at the 20G cap; they are not needed now that v5 is closed.
- **v5 validation replay:** 1 of 54 configurations passed, but the attribution
  shows the profit comes entirely from intrinsic-value expiry closes (unsellable
  deep-ITM 0DTE calls). Every other exit loses in every fold, for the baseline
  and for the selected configuration alike.
  [EXPERIMENTS](docs/EXPERIMENTS.md) has the numbers.
- **User decision:** record v5 as failed and do not run the 2026 test
  ([DECISIONS](docs/DECISIONS.md)). The 2026 window remains unspent for a
  future pre-registered design.

## Status at session end

No ETFE jobs running. Attribution script and per-trade logs were scratch-only
(not committed); the method is reproducible from `exit_kind` in the dataset v4
labels plus `nn_meta/etfe/eval_portfolio.py`.

## Next actions

1. **User decision:** the next ETFE direction, or a return to other work. Across
   v3–v5, no model selection is profitable on exits it controls (strategy,
   OTM and sellable-ITM exits). Any successor must be a new pre-registered
   design that prices expiry within liquidity limits from the start.
2. Commit hygiene: never use a path-limited `git commit -- file` on files with
   others' uncommitted hunks; stage only your own hunks (`git apply --cached`).

## Selected artifacts

[CURRENT_STATE](docs/CURRENT_STATE.md); labels v4, dataset v4, experiment v5 and
training v5 roots under `nn_meta/validation/`. Preserve unrelated dirty V6/V7 work.

[Previous handoff](handoff-history/HANDOFF-2026-10-07-before-v5-verdict.md).
