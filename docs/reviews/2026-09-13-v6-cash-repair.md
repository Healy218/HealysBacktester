# V6 funding rejection and restart — September 13, 2026

The `v6-neural-repair-20260913r2` run failed during fold-3 NN policy evaluation
after all 15 neural fold seeds passed numerical checks. The failure was
reproduced using the five saved fold-3 models and the exact 239,793 validation
rows, without fitting new models or changing data.

The rejected APLD entry was at `2026-05-21 14:00:00`. Available cash was zero
while marked equity was `0.7294973240556901`, held in CRWD, JPM and QQQ positions.
Positive unrealized equity does not fund a new purchase. The cash guard was
correct; the evaluator was wrong to abort the entire policy grid for this
unfundable candidate book.

The ledger still refuses unfunded entries, now with a specific
`UnfundedEntryError` carrying the trade, timestamp, cash and equity. Evaluation
catches only that error and records an ineligible policy with unavailable
return/drawdown and the funding reason. Corrupt/missing marks, inconsistent
fills and other accounting errors still propagate. An unfundable baseline or
required outlier-comparison book cannot waive eligibility. Marked test reports
show infeasibility explicitly instead of presenting a return or crashing.

Quote/cost validation can report the same funding refusal only when its
independent ledger also rejects the same trade/time with matching balances.
That is recorded as an independently matched rejection, never a matching equity
curve or a zero-loss return. Structural errors and disagreements remain fatal.

The unchanged fold-3 NN predictions now complete all 15 policy configurations:
one is rejected for funding, and 14 continue. The selected configuration in
this diagnostic is EV/0.05 with a 0.30 drawdown brake. This is a replay of the
failed validation case, not a completed retraining or fresh performance result.
Both ledgers independently confirm the funding refusal in all four aggregate
cost scenarios. Evidence is preserved under:

- `nn_meta/validation/v6-cash-failure-reproduction-20260913/`
- `nn_meta/validation/v6-cash-fix-preflight-20260913/`

Additional corrections: resumed training checks the artifacts named inside
stage receipts; unchanged receipt JSON cannot hide a changed model. Aggregate
execution revalidation passes through the original drawdown brake and retains
its frozen allocation fractions. It does not recompute counterfactual sizing;
braked quote replay still requires separate causal sizing support and refuses
unsupported use.

Replacement campaign: `v6-cash-repair-20260913`. Preserve the failed campaign;
do not edit its scope or reuse its NN weights under changed training-source
hashes. The replacement retains three folds, five NN selection seeds per
partition, forty final seeds and the original eligibility thresholds. It
reuses only verified completed assembly/objective comparisons. The two-worker,
two-thread service reserves two physical cores and uses a 600% CPU quota,
24 GiB memory cap and 2 GiB swap cap. Scanner promotion remains separate.

The full regression suite passed **1,537 tests plus 18 subtests** before launch.
The service started at **18:04:23 UTC**, invocation
`ab73abc136394dd2aa1de01f3b662d37`. All three actual evaluation folds completed
with exit 0. The full pipeline completed at **19:47:00 UTC / 14:47 CDT** with
20 finite NN selection seeds, four GBT selection seeds and 40 final GBT seeds.
The final research gate selected GBT, EV threshold 0.05, without a drawdown
brake: +648.8% historical validation return, 12.6% maximum drawdown and 241
positions. These results overlap prior selection/tests; they are not a fresh
holdout. All 32 aggregate execution comparisons matched the independent ledger.
Nested training artifacts and pipeline output hashes reverified at 19:59 UTC.
The watcher and dashboard follow this campaign; the watcher reports completion.
Telegram stays disabled. Scanner promotion remains blocked on actual quote/roll
evidence, forward replay, external feature/feed parity and operating review.

Current launch/status paths are recorded in `HANDOFF.md`.
