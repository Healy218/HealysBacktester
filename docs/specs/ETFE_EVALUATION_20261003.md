# ETFE evaluation and finite experiment contract

Declared before ETFE labels or performance inspection. This specifies
ETFE-0.experiment-contract; the [JSON declaration](ETFE_EXPERIMENT_20261003.json)
holds exact dates, parameters and trial IDs. It is not a fitted experiment or
a dataset freeze. Source/history blockers still prevent admission.

## Targets and eligible rows

For a completed isolated path let A be its actual initial option cash debit
including fees/slippage, and P its final net cash P&L including all rolls,
exercise and stock legs. Define R=P/A, win=1[R>0], weighted-win sample weight
clip(abs(R),0.01,5). Win uses unweighted binary cross entropy; weighted-win uses
that fixed weight with binary cross entropy; robust return predicts R with
the declared Huber loss. Wins at exactly zero are false. No labels for unfilled,
size-ineligible, boundary-censored, input-unresolved or funding-unresolved paths.
Account for them all by ticker/family/timeframe/target/reason; unresolved source
or funding outcomes block full evaluation, not just the rows they would remove.

No censored outcome can enter imputation, supervised training, threshold choice,
or scored predictive metrics. No label computed with data outside the fixed
window. Boundary-complete predictive metrics are explicitly conditional; do
not extrapolate them to the censored population. Every strategy/parameter logical
row is retained; computation deduplication stores multiplicity and restores the
same logical loss weights. Statistical uncertainty clusters by session and
portfolio; duplicate/correlated SPY/VOO rows are not independent observations.

## Chronological folds

Training starts at the verified history boundary, currently unresolved. Fix
validation periods now: 2024-07-01–2024-12-31, 2025-01-01–2025-06-30 and
2025-07-01–2025-12-31. Training in each fold ends at the preceding civil day.
Final test is 2026-01-01–2026-10-02; final refit training ends 2025-12-31.
Use actual sessions inside these inclusive dates. If the verified start or
coverage leaves a fold without sufficient data, fail that declared experiment;
do not slide dates after looking at outcomes.

For a split boundary B, define E as the open of the **tenth preceding exchange
session**. Retain training rows only if their decision and full terminal
exit/roll/stock/cash-settlement horizon are both strictly before E. Exclude the
ten sessions [E,B) from training decisions and labels. This one-sided gap suits
expanding historical training; no future rows enter the training set. Require
validation horizons to finish before its period end, with the same treatment
for final test. At the final refit apply the ten-session gap before test again.
Feature lookbacks may read earlier inputs, but fitted preprocessing and labels
may not use embargo/validation/test rows. Store exact session lists, row IDs and
purged reasons in the later dataset freeze.

Each evaluation portfolio starts with $100,000 cash and no inherited positions.
Keep decisions through its stated end and carry censored positions as liabilities;
do not erase positions to report a clean period return. Revalidation accurately
describes market dates already inspected in predecessor work. The final test is
untouched by **this ETFE fitting/selection**, not claimed to be new market history.

## Processing and fits

Fit numeric medians on retained training rows only; all-NaN columns get a
predeclared zero fill and keep their missingness mask. This is allowed for natural
missingness/structural parameters, not absent required source coverage. Save
training medians, means and standard deviations; use population standard
deviation with a scale of 1 for constant columns. NN uses training standardization
of imputed values; GBT consumes imputed unscaled values plus masks. Indicators
are unscaled. No calibration, dimensionality search, feature selection or early
stopping based on validation is permitted.

Per fold use 21 configurations: three training-estimated constant objectives,
GBT and NN for three objectives at seeds 11,29,47. Three validation folds give
63 fits. Predeclare all 21 final training refits on pre-test data, for **84 required
fit receipts** total. Final selection remains locked before test predictions;
test outputs of unselected trials are retained solely for accounting/reporting.
Missing/failed fits mean incomplete campaign. Pilot fits are not among these 84.

Constants: win is training mean(win), weighted-win is weighted training
mean(win), robust return minimizes training Huber loss. GBT uses 200 rounds,
31 leaves, learning rate .05, minimum leaf rows 20, max_bin 63, one numerical
thread, no subsampling. GBT return uses LightGBM Huber alpha .9. NN uses dense
64/32 ReLU layers, linear return or sigmoid classification output, Adam .001,
batch 4096, 10 epochs, no dropout or shuffle, Huber delta 1 for return. Save
library versions, all deterministic seeds and source hashes. Fixed source order
is (decision_ns, security, variant, right, target, contract). Resource-only
batch reductions after the pilot require a successor declaration before fitting;
do not change objectives, dates or search size based on pilot profitability.

## Decision policy and baseline comparisons

Each of 18 nonconstant models has three fixed entry thresholds: win and
weighted-win 0.50/0.55/0.60, robust return 0/.01/.02. Weighted-win score is a
ranking score, not a calibrated probability. At a signal close filter candidates
by threshold, rank score descending, then the execution tie key. Deduplicate
same underlying candidates before allocation; all variants still receive
predictions and census entries. Same score uses lexical trial ID/threshold.

Compare with cash; each of the three constant predictors with the same objective
threshold grid and ledger; and one no-model all-eligible policy using the stable
execution tie key. All use identical coverage/size/missingness, costs, dates,
capital and funding. Baseline predictions are training-only constants; they do
not know test win rate. Report all 54 nonconstant policy candidates and nine
constant policy combinations per period, plus cash/no-model.

Select using validation evidence only: candidate must have at least 100 completed
shared-ledger positions across validation, positive net return in each fold,
maximum drawdown <=20% in every fold, no unresolved liabilities/valuation gaps,
and positive aggregate excess over both cash and the best noncash baseline.
Choose greatest mean fold excess terminal-equity return; tie to lower drawdown,
then lexical trial ID and lower threshold. If none qualify, select abstain.
Do not average seed outputs into an undeclared ensemble or search further.

Before inspecting test, seal selected model family/objective/seed/threshold and
all final refit/preprocessing hashes. Test acceptance additionally requires
>=100 completed positions, positive excess net return over cash and best
predeclared noncash baseline, max drawdown <=20%, and a positive lower 95%
confidence bound for the mean paired daily excess return. Use 2,000 moving-block
bootstrap replicates of length 20 sessions with seed 20261003, sampling whole
date blocks of portfolio return differences. Predictive metrics retain all trials,
but only the locked policy can receive an acceptance verdict.

Run all execution stresses. Acceptance also requires nonnegative excess return
under 2x costs, 5-second lag and 0.5% participation, individually and combined;
more severe stresses are disclosed, not used to retune. Unknown held valuation,
unresolved physical funding or unresolved terminal liabilities prevent the
performance acceptance calculation. They cannot be assigned a cash return.
Failed performance criteria yield rejected/abstain; data/causality defects yield
incomplete/blocked. Both differ from deployed. No automatic promotion.

## Required evidence

Report log loss/Brier/reliability bins for win, weighted loss for weighted-win,
MAE/RMSE/Huber for return, and ranking diagnostics without probability claims
for weighted-win. Portfolio metrics include net return, annualized return when
defined, max drawdown, exposure, turnover, completed trades, skips, censored
capital, stock delivery, funding failures and uncertainty. Break down ticker,
family/timeframe/target and calendar quarter; retain all attempted trials.

ETFE-3.freeze binds the dataset, all logical row memberships, source contracts,
exact purge/embargo session lists and preprocessing design before full fitting.
ETFE-5 freezes every fit, prediction, chosen policy and accepted/rejected result.
Clean-process replay requires exact decisions/abstentions and score tolerance
atol=1e-6, rtol=1e-5, plus schema/source mismatch rejection and restart/restore
proof. Profitability is never assumed by completing this declaration.
