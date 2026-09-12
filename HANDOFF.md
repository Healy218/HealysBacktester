# V6 training running — September 12, 2026

Current campaign: `v6-train-20260912r2`, source `7137da6` on main.
User authorized performance optimizations, practical training recommendations,
later-work notes and launch. Evaluation has completed fold 1 and is on fold 2/3. Its first two
neural seeds completed; seeds 2 and 3 are running concurrently. Forty-seed final training is queued after evaluation,
subject to the existing final-ensemble gates. Nothing has been deployed.

## What completed

- Original `v6-local-20260906` built all 449 eligible symbols. Its monolithic
  assembly was OOM-killed at 10:59 UTC; preserve that failed receipt and scope.
- `v6-train-20260912` assembled all shards in 169.5 seconds: 4,281,562 retained
  rows and 62,289,803 marks. It completed both separate objective comparisons.
- That first continuation stalled at a 20 GiB soft memory throttle during
  evaluation preparation. It was stopped, not relabeled as successful.
  Initial implementation/source is preserved in commit `75af6cb`.
- The memory fix (`7137da6`) prepares the actual first fold in 29 seconds,
  with 15.21 GiB peak RSS and 8.26 GiB after releasing temporary data.
  R2 copies byte-identical completed dataset/comparison outputs with verified
  source/input compatibility and lineage. It does not repeat the raw build
  or retune experiments after their held-out readout.
- Latest full suite: 1,468 tests and 18 subtests passed. Tests include NN/GBT
  reference parity, seed resume/corruption, stream joins/labels/marks, temporal
  purge/folds, memory-bounded batching and completed-output reuse.

## Current runtime

Service: `healys-v6-training-20260912r2.service`, invocation
`443b9020ac7f4eb9b9c5111823d7079e`. Two seed processes, two threads each, CPU
quota 600%, affinity excluding two physical cores, nice 10, hard RAM cap
24 GiB and swap cap 2 GiB. No 20 GiB soft throttle. GPU disabled; its driver
was unavailable. Use the user systemd manager for live status; host PIDs may
not be visible inside the command sandbox's process namespace.

Paths relative to `nn_meta/campaigns/v6-train-20260912r2/v6/`:

- `continuation_scope.json`: current source/runtime and consumed-input hashes.
- `runs/training-service.log`: top-level stage transitions.
- `runs/continuation/latest.json`, `evaluate.log`: active stage and fold log.
- `runs/seed-jobs/*/nn-s*/worker.log`, `complete.json`: worker/checkpoint evidence.
- `reports/objective-comparisons/{plan,results}.json`: copied completed research.
- `model_final.staging/`: eventual final seeds; retained on gate rejection.

Restart command (same settings/source required):

```bash
./venv/bin/python -m scripts.continue_v6_training --parent v6-local-20260906 --campaign v6-train-20260912r2 --reuse-completed v6-train-20260912 --workers 2 --threads 2 --run
```

Run under a bounded background service. The launcher prevents duplicate owners,
checks bindings between stages and verifies completed seed/stage hashes.
Do not edit fingerprinted source or merge isolated FA/production changes while
this campaign runs. New code/input changes need an explicit new continuation.

## Results and outstanding work

Event balancing was mixed: held-out AUC 0.60438 versus baseline 0.60564;
log loss 0.65267 versus 0.65283. Keep the baseline objective. Downside Q10
pinball loss was 0.06757 versus constant baseline 0.08783, with 11.09% of
outcomes below the predicted 10th percentile. These are research metrics,
not a portfolio gate or established trading improvement.

Actual conditional folds, validation start / test start / test end (2026):
January 5 / March 4 / May 4; March 3 / May 5 / June 30; May 4 / July 1 /
August 24. Exit-time purge and one-day embargo remain. Original default fold
selection would exclude two of its three folds. Expanded TradingView parity
is still deferred; feature contract remains unverified and research-only.

Next: monitor worker completion/resources; inspect walk-forward and final gate
results; update EXPERIMENTS with a real verdict. Ranking, learned contract/exit
selection, richer overlap weighting, GPU/larger concurrency, calibration,
abstention and mature prospective FA have prerequisites in the review.

Details: [training review](docs/reviews/2026-09-12-v6-training.md),
[experiment scoreboard](docs/EXPERIMENTS.md), and TODO section 4.
The previous full handoff is archived at
`handoff-history/HANDOFF-2026-09-12-before-training-continuation.md`.

## Other work remains separate

Production ops: `/tmp/healys-server-alert-readiness`; FA runtime:
`/home/healy/Coding/HealysAutomation`; Firebase dashboard:
`/home/healy/Coding/HealyLabsDashboard`. Dashboard login was confirmed by the
user, and the standalone iOS branch still needs Mac/Xcode device acceptance.
The taken-contract parser fix was previously deployed; actual broker sale
verification remains pending. These systems were not revalidated here.
Older dashboard/watchers still reference their previous campaign receipts;
new training progress is in the paths above. No new notifications were sent.
Preexisting untracked `nn_meta/artifacts_v6/` is untouched and must not be added.
