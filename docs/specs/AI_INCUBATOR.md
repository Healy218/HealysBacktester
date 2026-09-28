# Continual research and training incubator

## Purpose and selected scope

The September 27, 2026 user direction supersedes the earlier replay-only
incubator. Its purpose is to extend research datasets as market data arrives,
train updated candidate models, evaluate them and freeze reproducible new
artifacts. Selected implementation scope is **V6 only**; V7 can replace it as
the latest admitted generation after its own data/model gates pass.

Training examples come from the full frozen proposal universe, independent of
paper selections, broker fills, portfolio capacity or the deployed model's
threshold. V5 paper outcome joins are no longer an incubator prerequisite.
Historical prediction refreshes remain valid inference evidence. Their
[original contract](../reference/AI_INCUBATOR_REPLAY_LEGACY.md) is historical.

## Incremental data, immutable freezes

- Reuse V6's externally anchored release, frozen per-symbol strategy parameters,
  DTE grids, 164-feature order and original training dataset. Do not rerun the
  historical strategy sweep or alter the original dataset/model seals.
- Append candidates after the base window ends (initially August 24, 2026).
  Enumerate all frozen symbols and eligible signals, including untraded ones.
- Reconstruct features from each signal's causal history and prior daily
  context, with the existing V6 SIP option-tick feature policy. Record historical
  reconstruction and retrieval time honestly; it is not prospective observation.
- Keep candidate features immutable. Hash-bound prior stock history must not
  change silently when extending a snapshot; revised history requires a new
  reviewed lineage.
- Retain open vectorBT proposals as pending. An open position's final data-window
  mark is not a completed outcome. Finish labels after the actual simulated
  strategy trade closes, using V6's existing training execution/cost rules.
- These labels use the frozen research option-aggregate executor and its
  simulated rolls/costs. They are not Alpaca fills and do not claim parity with
  the separate broker's premium-risk lifecycle. Keep that evidence boundary.
- Preserve unfilled proposals, pending outcomes and provider failures in coverage
  receipts. Provider errors cannot become successful empty coverage or labels.

## Daily stages

1. Select the last fully closed calendar session. Reuse its existing sealed
   data snapshot when available. Otherwise use the preceding session's sealed
   daily context and append completed-session stock bars in research storage.
2. Reuse sealed feature captures, enumerate new candidates and revisit unfinished
   labels. Symbol receipts reconcile the complete 449-symbol scope. Partial
   progress is restartable; a pilot/subset cannot enter full model training.
3. Build a dataset view from the immutable historical base plus all completed
   extension rows. Verify non-overlap and exact candidate identities.
4. Refit the fixed 40-member V6 LightGBM classifier/magnitude ensemble. Keep the
   existing hyperparameters and seed identities; no nightly family sweep and no
   unvalidated warm-start shortcut. Use train-only magnitude winsor bounds.
5. Use a chronological 40-observed-date validation tail with actual outcome-end
   purging and a one-day embargo. Compare the new ensemble with its incumbent
   and the zero-return baseline. Daily validation is reused for model selection;
   it must not be presented as an untouched prospective test. The initial tail
   overlaps the original incumbent’s training history, so the comparison is a
   conservative diagnostic, not an independent head-to-head performance test.
   The newest 40 observed dates are held out of weight fitting; their features
   and matured outcomes still enter the daily research artifacts.
6. Freeze a separate research candidate with hashes, parent/input lineage and
   evaluation. Advance an accepted-research pointer only after its declared
   diagnostic gate passes. Neither pointer deploys or promotes a model.

The initial diagnostic gate requires candidate return MSE no worse than both
incumbent and zero-return baseline, and classifier Brier score no worse than both the
incumbent and a training-prevalence constant baseline. This is a research-selection gate, not a profitable-trading verdict.

## Resources, recovery and morning deadline

Use autosized workers, bounded service memory/CPU and a finite wall-clock
budget. Preserve completed candidates, labels, arrays and member checkpoints.
Changed source, configuration or inputs must fail resume checks. A failed,
late, incomplete or rejected refresh leaves the previous accepted model intact.

Next-session readiness is the target, not an established SLA. The measured
full-size member benchmark is recorded in the September 27 continual-incubator
review; a member timing is not a nightly pipeline measurement.
Measure the initial catch-up separately from a steady one-session update.
No matured new labels means a pending run, not a fabricated new trained model.

## Ownership and navigation

[TODO](../../TODO.md) owns the selected implementation/validation checklist;
[ROADMAP](../../ROADMAP.md) owns milestone gates; [CURRENT_STATE](../CURRENT_STATE.md)
owns exact configuration, service and artifact pointers. Evaluated runs and
limits belong in dated reviews and EXPERIMENTS, not in this specification.
