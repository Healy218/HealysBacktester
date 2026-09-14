# V6 follow-up implementation — September 13, 2026

Current update: the cash-ledger failure described below is repaired in
`v6-cash-repair-20260913`. Its full rerun has passed all three evaluation folds
and is training the final GBT ensemble. All 20 NN selection seeds are finite;
1,537 tests plus 18 subtests passed before launch. The watcher and dashboard
follow the replacement. See the [cash-repair review](2026-09-13-v6-cash-repair.md).

Neural numerical checks, frozen execution revalidation, the sealed live-input
adapter, isolated shadow recording/replay, and private dashboard publisher
integration are implemented. Scanner promotion remains on hold. Full repaired
training launched at 16:44 UTC September 13 through the durable pipeline below.
Actual forward collection has not been launched.

Latest status: the full run **failed at 17:13 UTC** during fold 3 policy
evaluation, after all 15 NN fold seeds completed finite validation. The cash
ledger rejected an entry at `2026-05-21 14:00:00` because no available cash
remained. Two GBT folds completed. Final ensemble training and automatic
validation have not started. This is an operational evaluation failure, not
a healthy model-family verdict or a completed gate result. The run is preserved
for diagnosis. The hourly watcher/dashboard are now rebound to this campaign;
Telegram remains off.

The watcher was run successfully at 17:48 UTC and its next hourly run is
18:00 UTC. It tracks pipeline validation/failure states as well as training.
The private dashboard uses the same campaign and reports evaluation failure
even before a finalize log exists. Validation: 18 watcher tests and 19 dashboard
publisher tests; 36 combined watcher/pipeline/follow-up tests passed. The
original training scope and all 15 neural artifact receipts remain unchanged.
The dashboard's scheduled publication succeeded at 17:48:25 UTC with no issues.

## Authorized full rerun

`healys-v6-neural-repair-20260913r2.service` runs the fresh repair scope with
two workers/two threads, the original three folds and forty final seeds. It
reserves two physical cores, uses a 600% CPU quota/nice 10, and caps memory at
24 GiB plus 2 GiB swap. Invocation: `16cede3136944071b855c6df5fb1e25c`.
At 16:49 UTC four fold-1 neural seeds have passed finite classifier/magnitude
loss, weight and prediction checks across 282,878 validation rows. This is
numerical health evidence; selection and final performance are still pending.

The added `scripts/v6_training_pipeline.py` automatically runs execution
revalidation after training and writes a model-bound readiness inventory.
It preserves failure logs, verifies completed output hashes before resume,
and refuses source drift. `scripts/v6_readiness.py` checks NN health, stage
receipts, ensemble hashes/seed counts, execution scenarios and supplied forward
quote reports. It reports external parity and release review as outstanding;
it does not turn research results into scanner authorization.

Latest full regression suite: **1,522 tests plus 18 subtests passed**.
Fifteen new tests cover malformed/mismatched evidence, finite validation for
both heads, missing forward exits, model identity, failure isolation, checked
resume and service limits. Existing failed campaign artifacts remain intact.

## Neural repair and real-data check

All-missing training features are explicitly disabled for the entire fit,
including validation and inference. Means and deviations use only training
rows. Non-finite arrays, losses, weights and predictions prevent successful
neural receipts; defective old receipts refuse reuse. Reference and parallel
paths persist/read the same inactive-feature policy.

The original Asia/London ICT range features are missing because the declared
local history is RTH-only and those default sessions are outside RTH. The
repair preserves missing observations and does not invent overnight prices.

A two-epoch, one-seed numerical smoke used 8,192 evenly spaced training rows
and 2,048 validation rows from the preserved final-window arrays, with all
164 features. Both heads produced finite predictions and 2,048 distinct
outputs. Both original all-missing features were recorded as inactive.
The sample's magnitude targets were already winsorized in the original arrays;
this is a numerical/integration check, not a performance evaluation or completed
family comparison. Evidence: `nn_meta/validation/v6-neural-smoke-20260913/`.

Fresh scope `v6-neural-repair-20260913r2` is running with 226 bound sources
and 1,376 input references. It retains the original training budget and can
reuse compatible completed assembly/objective comparisons. Corrected family
selection and final training are incomplete following the fold-3 failure.
The earlier prepared
scope without `r2` was superseded by the final source changes and is preserved.

## Matching marked baseline and execution sensitivity

The final frozen candidate and frozen-DTE baseline use the same final-validation
population, same mark stream, same costs and same cash-ledger rules. A separate
cash/event implementation matched every equity observation and maximum
drawdown in all 32 policy/latency/cost combinations.

| Fixed selection, base costs | Candidate positions | Candidate return / maxDD | Baseline positions | Baseline return / maxDD |
| --- | ---: | --- | ---: | --- |
| Original retained fills | 241 | +648.8% / 12.6% | 205 | +90.6% / 50.6% |
| At most 5 minutes after signal close | 52 | +48.2% / 9.5% | 120 | −13.8% / 57.6% |
| At most 15 minutes after signal close | 90 | +72.0% / 10.5% | 145 | −20.5% / 60.8% |

The largest aggregate-cost scenario adds a 100-bps half spread plus higher
fees/slippage; original retained fills then return +299.9% for the candidate
and +8.1% for the baseline. These are assumed aggregate costs, not observed
quote execution. Rejected positions are removed without backfilling slots.

This tail was already used for family/ensemble selection and overlaps earlier
tests. These numbers are **revalidation, not a fresh holdout**. They do not
measure achievable prompt-alert returns. The latency screen retains just
52/241 candidate positions at five minutes, a material execution limitation.

Evidence: `nn_meta/validation/v6-execution-20260913r3/`, including immutable
scope, selected positions, scenario curves, rejections, results and completion
hashes. Inputs are checked against the original campaign's completed receipts.
The earlier implementation-run reports without `r3` are preserved too.

## Quote and live/shadow paths

The quote engine supports bounded entry latency, as-of receipt timestamps,
stale/invalid/zero-size quotes, actual ask/bid spread, dollar commission,
adverse slippage, explicit roll plans, conservative missing exits and separate
cash-ledger checking. It rejects incomplete roll plans and contract-expiration
mismatches. Fractional contracts, displayed-size screening and a weekday mark
cadence do not establish real execution capacity or complete exchange coverage.

No historical execution quote tape/complete roll export was supplied for this
revalidation, so no quote-based campaign returns are reported.

The live snapshot adapter supplies shared expanded inputs, raw spot and a
prior-date chain to `scan_pass`, attaches context before proposal detection,
and uses sealed daily context instead of an unrelated local-cache fallback.
It preserves training history origins and rejects stale/changed inputs. Tick
features verify the original raw journal payload and use receipt availability
with an explicit evidence-bound provider-condition mapping. Heartbeats cannot
certify capture completeness. Missing coverage is a recorded scan failure.

`--shadow` records every candidate variant, first-observed predictions,
candidate/baseline selections and optional execution quotes in separate SQLite
state. It never drains notification outboxes or opens paper positions. Its
scope binds model bytes, policy, budget, baseline and source code. Forward
replay requires frozen, receipt-bound exit plans and refuses to report a
resolved-only subset while other selected signals remain unresolved.

Actual TradingView fixture parity, live capture/condition evidence and forward
observations remain outstanding. None were fabricated by the implementation.

## Dashboard and verification

The four tested publisher files are applied in the separate dashboard checkout.
Its publisher campaign/progress settings now follow the repair run. Optional
execution/shadow evidence views remain unconfigured pending new results.
The integration uses the existing Training table
renderer. Explicitly configured execution/forward paths are bounded, private,
model-bound reads. Revalidation labels and stale/missing forward data remain
visible. The live-data preview contains 32 scenario rows and no follow-up
integrity issues. The original failed-NN warning remains
because that displayed campaign has not been replaced.

Validation after the full training launch: 1,522 repository tests and 18
subtests passed, including the snapshot sealer and pipeline failure/resume tests.
All 16 existing dashboard publisher tests and three follow-up integration tests
passed. The repaired reference NN finalizer, persisted-loader round trip,
raw receipt checks, no-notification shadow pass, forward replay and independent
quote accounting have regression coverage.

All 121 original final-bundle artifact hashes still match. All 20 original
NaN NN receipts remain present and unchanged. `nn_meta/artifacts_v6/` remains
untouched. Full retraining failed during evaluation; no scanner deployment or notifications
occurred.

Commands, evidence schemas and remaining operating steps are documented in
[the runbook](../specs/V6_FOLLOWUP_RUNBOOK.md).
