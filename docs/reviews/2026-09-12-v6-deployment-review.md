# V6 scanner deployment review — September 12, 2026

**Verdict: hold scanner promotion; continue developing the GBT candidate.**
Readiness: **Needs revision**. Coverage: **Partial**; the important training,
reporting and integration findings are verified, but executable-quote replay,
full source parity, cost stress and independent ledger implementation remain
outside this review. Nothing was retrained or deployed to the scanner.

This review covers `v6-train-20260912r2`, the completed expanded-feature
campaign. The strong recorded GBT returns justify further work. They do not
establish that immediate scanner alerts will earn comparable returns.

## What the results actually support

| Test window, 2026 | GBT policy | Marked return | Marked maximum drawdown | Positions |
|---|---|---:|---:|---:|
| March 4–May 4 | EV 0.05 | +73.3% | 23.6% | 143 |
| May 5–June 30 | Filter 0.50 | +205.4% | 11.9% | 137 |
| July 1–August 24 | Rank 0.50 | +61.3% | 22.4% | 156 |

These are separate tests of validation-selected policies using single GBT
seeds, conditional on a globally frozen proposal generator. They are not
three tests of the final 40-member EV ensemble. Test windows are disjoint,
validation follows the generator optimization horizon, and split assignment
uses exit-time purging and a one-day embargo. Do not add these returns or
compare them directly with pre-audit v5 results as a controlled experiment.

The original report's baseline column is **validation**, not test. This review
adds a frozen-baseline replay over the same test dates, using the **shared
simulator for both sides**. The values below differ from the marked table
because accounting differs; marked baseline comparison remains required.

| Fold | GBT shared return | Baseline shared return | GBT shared maxDD | Baseline shared maxDD |
|---|---:|---:|---:|---:|
| 1 | +72.3% | −5.5% | 22.2% | 41.5% |
| 2 | +194.4% | +372.6% | 7.3% | 36.7% |
| 3 | +59.5% | −20.9% | 15.5% | 41.5% |

The GBT improves raw return in two folds and drawdown in all three. Fold 2's
baseline earns more with substantially higher drawdown; it is not honest to
say v6 wins every measure. Selection/capacity differ by policy, as intended.

Fold 3 replay reproduced all reported shared metrics: 156 positions, 75 wins,
107 symbols and 37 entry dates. Separate arithmetic reproduced its return
moments and reported deflated-Sharpe score. The final marked replay also
matched exactly: **241 positions, +648.8249% return, 12.5673% maxDD**.
Both selections and the marked replay reuse canonical accounting helpers:
this establishes reproducibility, not independent proof of realistic fills.

## Decision-changing problems and proposed fixes

### 1. Neural training failed numerically

**Finding, P1:** all **20 of 20** NN completion receipts contain `val_loss: NaN`.
All four prepared windows retain missing means and standard deviations for
`tv_ict_ASIA_range_value_atr14` and `tv_ict_LNDN_range_value_atr14`.
Independent inspection of the first 1,024 training rows per window finds two
non-finite inputs per row. Filling missing values with a missing mean leaves
these neural inputs unusable.

Inspected final-selection seed-0 classifier and magnitude files each contain
128 non-finite first-layer weights, exactly the 64 outgoing weights for each
of those two features. All 372,764 retained final-validation NN probabilities
and EV predictions are constant. Zero selected neural trades therefore do
**not** show that a functioning neural model lost to GBT.

GBT predictions are finite and nonconstant. Its handling of missing values is
different: LightGBM supports NaN values natively by default. This does not
automatically invalidate the GBT's recorded results, although it invalidates
the family comparison. [LightGBM missing-value documentation](https://lightgbm.readthedocs.io/en/latest/Advanced-Topics.html#missing-value-handle).

**Fixed:** the training narrative now retracts the earlier operating-point-only
interpretation. Dashboard publishing detects failed NN validation losses and
places a warning beside the summary. Original training receipts and weights
remain unchanged.

**Fix proposed:** trace why these inputs are entirely absent; define a
training-only missing-column policy and enforce finite neural arrays,
losses, weights and predictions before writing success receipts. Use a fresh
scope for corrected NN/family evaluation. An explicitly GBT-only candidate can
be evaluated separately, but cannot claim to have beaten a healthy NN and
still faces the execution and live-input blockers below.

Source: `nn_meta/training_jobs.py`, `nn_meta/v4_evaluate.py`; campaign
`runs/prepared/*/arrays.json`, `runs/seed-jobs/*/nn-s*/complete.json` and
`reports/finalize_val_predictions.parquet`.

### 2. Execution assumptions are not established for immediate alerts

**Finding, P1:** the executor enters at the first future option aggregate
Open and exits at aggregate Close. There is no maximum entry-delay bound in
that path. Base costs total **0.15% per side**, without an explicit spread
allowance. Having option-tick features does not turn these labels into
bid/ask execution evidence.

For the final selected 241 positions, median entry lag is **75 minutes from
signal-bar start**, or 60 minutes after a 15-minute signal closes. Overnight,
weekend and holiday gaps contribute; these are wall-clock times, not missed
tradable minutes. Among the **176 same-date fills**, median post-signal-close
delay is **15 minutes**, and its 90th percentile is **127.5 minutes**.
No selected fill was after the planned exit or expiration date. The selection
joined uniquely back to the dataset, and the lead independently recomputed
the lag arithmetic from its timestamps.

This demonstrates a mismatch with prompt alert execution; it does not measure
the amount of return inflation. The marked final replay contains 1,518
observations after execution conversion; this review did not establish
complete intratrade quote coverage or worst-case drawdowns between marks.

**Fix proposed:** replay the frozen policies and baseline on the same marked
ledger with a declared fill-latency limit, executable bid/ask prices, realistic
spread/commission assumptions, stale/missing-quote handling and cost stress.
Do not retune policies on these already-inspected test outcomes. Where quote
history is unavailable, report that limitation and collect forward evidence.

Source: `options/execution.py:195`, `nn_meta/v4_accounting.py:18`, retained
dataset fill timestamps and selected mark stream.

### 3. The expanded live inputs are not connected

**Finding, P1:** expanded `build_candidate_batch` requires verified expanded
inputs, a point-in-time option provider and raw closes. The current
`scan_pass` call supplies none of them. A read-only invocation reproduced its
explicit “live adapter not configured” guard. This is a local source review;
the remote scanner's actual checkout was not freshly audited here.

The feature contract also remains
`2026-09-06-tv13-option-ticks-unverified-v1`; external Pine comparisons are
deferred. Copying model files or changing the pool variable does not provide
the missing inputs or establish parity. The existing paper flag still sends
tagged alerts and does not bypass this contract requirement.

**Fix proposed:** wire and verify the live feature adapter, complete the
required parity work, and record a forward shadow stream with dashboard
results before considering an alongside-scanner trial.

Source: `nn_meta/live/v4_candidates.py:58`, `nn_meta/live/v4_scan.py`,
`nn_meta/v4_loader.py` and the final feature contract.

### 4. Green gates and the large final return overstate certainty if read alone

**Finding, P1:** the final **+648.8% is selection/revalidation**, covering the
eligible May 26–August 21 tail, overlapping previous tests. It is not a fresh
holdout for the final ensemble. Configured gates check minimum trade count,
drawdown and validation return/drawdown against the baseline's ex-top3 bar;
they do not require healthy NN training, executable fills, fresh ensemble
evidence, cost stress or statistical confidence. The recorded pass is real
but narrower than a deployment verdict.

PBO is **0.178 / 0.178 / 0.490** and deflated Sharpe is
**0.00168 / 0.03256 / 0.46852**. These do not provide compelling statistical
confirmation. PBO uses roughly 39 validation entry dates and related policy
variants; DSR uses per-trade returns despite overlapping positions and unequal
trial sample sizes. Neither is a literal probability of successful deployment.
DSR is intended to adjust performance evidence for multiple testing and
non-normal returns. [Original DSR paper](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf).

On 2,048 evenly spaced validation rows, all 40 saved members produce different
predictions, but median pairwise correlations are **0.9956** for classifiers
and **0.9982** for magnitude heads. Forty seeds provide modest smoothing, not
40 independent confirmations. Row bagging is disabled by `subsample_freq=0`;
column sampling remains active. No evidence here establishes 40 seeds as
better than a smaller ensemble.

**Fix proposed:** keep the current final policy frozen; obtain forward data,
portfolio-return uncertainty using date blocks and complete trial accounting.
Benchmark seed-count convergence before expanding compute. Do not select a
new seed count by repeatedly inspecting these test folds.

## Recommended order

1. Repair finite-value handling and receipt validation; preserve this campaign.
2. Test whether the GBT edge survives realistic fills, stressed costs and the
   matching marked baseline. This is the main economic decision point.
3. Complete feature parity and the live adapter, then collect forward shadow
   evidence for the frozen candidate. Decide on an alongside-scanner trial
   from those results; do not replace an existing scanner now.

## Evidence and review limits

[Retained review calculations](2026-09-12-v6-deployment-review.json) include
the matching baseline replay, neural checks, member diversity, fold-3 replay
and final selected-fill verification. Original evidence is under
`nn_meta/campaigns/v6-train-20260912r2/v6/`. Scratch reproduction scripts and
selected rows are in `/tmp/v6-verdict-review/`. Primary research source hashes
remain unchanged; review edits affect reporting and monitoring only.

The review did not rebuild the full raw dataset, independently implement the
marked ledger, complete Pine parity, verify remote runtime or perform quote
replay/cost stress. The lack of these checks is a readiness gap, not a claim
that each would fail. Existing dashboard desktop/phone, download and privacy
checks are reused only for unchanged paths; the new warning is checked against
the revised payload and rendered summary.


## Review coverage

Totals are scoped component/question counts, not complete verification or an
accuracy percentage. Zero observed defects does not mean every check passed.
Training defects remain open even though their reporting is corrected.
The compact coverage record and evidence mapping are retained in
`/tmp/v6-verdict-review/coverage.json`.

### Report quality and usefulness

| Category | Observed defects | Assessment |
|---|---|---|
| Analytical clarity | 0 / 5 | Separate marked/shared tables and explicit corrected NN interpretation prevent invalid comparisons. |
| Visual and interaction consistency | 0 / 2 | Revised warning and source review inspected at desktop and phone widths; unchanged navigation/download evidence reused. |
| Dashboard usefulness and completeness | 2 / 6 | Deployment blockers and next steps are clear. Matching marked baseline, execution stress and forward proof are still absent. Partial review: 3 scoped items have incomplete or stale evidence (Expanded source parity; Matching marked baseline and independent ledger; Executable quote and stressed-cost comparison). |

### Analytical correctness and robustness

| Category | Observed defects | Assessment |
|---|---|---|
| Source authority and confidence | 0 / 7 | Retained campaign receipts, prepared inputs and code were inspected; raw archives and external Pine parity were not revalidated. Partial review: 1 scoped item has incomplete or stale evidence (Expanded source parity). |
| SQL/value accuracy | 0 / 6 | Fold-three shared metrics and final marked metrics reproduce; matching shared baselines and timestamp arithmetic checked. Independent ledger implementation remains unverified. Partial review: 1 scoped item has incomplete or stale evidence (Matching marked baseline and independent ledger). |
| Within-chart agreement | N/A | No quantitative charts in the reviewed v6 summary; table/value checks cover its figures. Not applicable: No quantitative charts in the reviewed v6 summary; table/value checks cover its figures. |
| Complete source details | 0 / 2 | Training reports and deployment review are attached privately with source hashes; quote execution evidence is unavailable. Partial review: 1 scoped item has incomplete or stale evidence (Executable quote and stressed-cost comparison). |
| Cross-artifact consistency | 0 / 3 | Corrected NN interpretation and matching accounting labels align across summary, review, scoreboard and dashboard payload. |
| Data-quality controls | 2 / 3 | NN non-finite inputs/losses/weights and delayed aggregate fills are demonstrated issues; external feature parity remains unverified. Partial review: 1 scoped item has incomplete or stale evidence (Expanded source parity). |
| Conclusion support | 0 / 4 | Hold verdict and GBT-only promise are supported; final validation is explicitly separated from independent test evidence. |
