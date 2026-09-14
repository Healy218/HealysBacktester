# V6 evaluation failed at fold 3; watcher/dashboard follow repair run — September 13, 2026

Latest observation: the repair run stopped at **17:13:07 UTC** during fold 3
NN policy evaluation. `mark_to_market_portfolio` raised
`AccountingDataError: no available cash for entry at 2026-05-21 14:00:00`.
All 15 fold NN seeds have finite classifier/magnitude loss/weight/prediction
receipts; two GBT fold seeds completed. The final 40-seed fit and automatic
execution validation have not started. Do not report the service as running.
The cash-ledger failure still needs a reproduced, reviewed fix and a new
source-bound continuation; no failure evidence has been overwritten.

The hourly watcher was still configured for `v6-train-20260912r2`. It has been
updated in source to `v6-neural-repair-20260913r2` and now follows pipeline
supervisor, execution validation and readiness phases; failures override a
completed training receipt. Dashboard collector fixes also keep an evaluation
failure visible when no finalize log exists. Installed watcher service and
dashboard `TRAINING_CAMPAIGN`/`PROGRESS_RECEIPT` now point to the repair run.
The watcher completed successfully at 17:48 UTC; its hourly timer is enabled,
next scheduled run 18:00 UTC (13:00 CDT). Telegram stays disabled. The existing
dashboard minute timer publishes the updated source/configuration; a manual
publish hit the existing 55-second rate limit, so do not force duplicate starts.
The next scheduled publication succeeded at **17:48:25 UTC**, with no issues.
Installation backups/receipt: `/tmp/healys-v6-watcher-rebind/`. Watcher report:
`logs/v6-progress/v6-neural-repair-20260913r2/progress.txt`.
Validated 18 watcher tests, 19 dashboard publisher tests, and 36 combined
watcher/follow-up/pipeline tests. Original training scope and 15 NN artifact
receipts reverified unchanged. No training restart was attempted.

The user asked to code the September 12 review follow-up. Neural guards,
frozen execution/cost validation, matching marked baseline, independent cash
ledger, sealed expanded live inputs, isolated shadow recording/replay and
private dashboard publisher integration are implemented. Scanner promotion
remains on hold. The user explicitly requested full retraining; its durable
service ran and failed as described above. Scanner deployment and notifications
remain off.

[Implementation review](docs/reviews/2026-09-13-v6-followup-implementation.md)
and [commands/evidence runbook](docs/specs/V6_FOLLOWUP_RUNBOOK.md).

## Neural repair

`nn_meta/neural_validation.py` implements train-only inactive-column handling.
Entirely unobserved training columns stay zero at validation/inference;
missing other values use the training mean. Infinity/overflow, invalid labels,
non-finite losses, weights or predictions prevent successful NN receipts.
Reference evaluation/finalization, parallel workers and loaders share this
policy. GBT retains native NaN handling. Old failed NN evidence is preserved.

A real-data two-epoch, one-seed numerical smoke used 8,192/2,048 evenly sampled
rows and all 164 features. Both heads produced finite, nonconstant predictions.
Only the two original ICT Asia/London range columns were inactive; the RTH-only
history does not observe those overnight sessions. This is not performance
validation. Evidence: `nn_meta/validation/v6-neural-smoke-20260913/`.

Full-training scope `v6-neural-repair-20260913r2` launched at 16:44 UTC:
226 source hashes and 1,376 inputs, original three folds and 40 final seeds.
Service: `healys-v6-neural-repair-20260913r2.service`, invocation
`16cede3136944071b855c6df5fb1e25c`. Two workers/two threads, CPU quota 600%,
CPUs 2–7 and 10–15 (two physical cores reserved), nice 10, 24 GiB memory cap,
2 GiB swap cap; no soft-memory throttle. Observed 15.7 GiB current/17.7 GiB
peak memory. At 16:49 UTC fold 1 has four completed NN seeds; both heads have
finite losses/weights/predictions on 282,878 validation rows. Classifier loss
0.6471–0.6480, magnitude loss 0.1096–0.1100. No family verdict yet.

`scripts/v6_training_pipeline.py` runs training → this new model's 32 execution
comparisons → `scripts/v6_readiness.py` inventory. It keeps per-stage logs,
hash receipts and failure/resume state. No automatic scanner promotion.
Status: `nn_meta/campaigns/v6-neural-repair-20260913r2/v6/runs/pipeline/status.json`.
Training stage: `runs/continuation/latest.json`; detailed log:
`runs/continuation/evaluate.log`; service log: `runs/training-service.log`.
Final inventory will be `runs/pipeline/readiness.json`; execution output will
be `nn_meta/validation/v6-neural-repair-20260913r2-execution/`.
Do not edit scope-bound sources or pipeline sources while this service runs;
source/input drift fails the next stage check. The older prepared scope without
`r2` is preserved and must not run.

## Execution evidence

`nn_meta/validation/v6-execution-20260913r3/` contains completed frozen
revalidation: candidate versus matching frozen-DTE baseline, four latency
cases and four cost scenarios. All 32 equity curves/maxDD values match a
separate cash/event implementation. At base costs, original selected fills:
candidate +648.8%/12.6% maxDD (241 positions); baseline +90.6%/50.6% (205).
A five-minute post-signal-close entry limit retains only 52 candidate positions
(+48.2%/9.5%) and 120 baseline positions (−13.8%/57.6%).

These are final-tail selection/revalidation results, overlapping earlier tests,
not a fresh holdout or achievable alert returns. Rejected positions do not
backfill slots. Aggregate spreads are assumptions. Actual quote-tape and roll
coverage remain required for quote-based campaign results. Quote replay code
handles ask/bid prices, dollar commissions, slippage, receipt chronology,
missing exits, roll plans and independent cash accounting. Earlier execution
reports remain preserved; r3 binds all directly consumed calculation sources.

## Live, shadow and dashboard

`nn_meta/live/v6_inputs.py` validates sealed technical history/raw prices,
prior-date contracts, prior daily context and receipt-based tick windows.
Training history origins/defaults stay bound. Journal normalized fields are
verified against raw msgpack payloads; provider-condition mapping needs evidence.
A heartbeat does not certify complete capture. Expanded `scan_pass` supplies
these inputs before detection/projection and currently requires `--shadow`.

Shadow records immutable first-observed candidates/baseline decisions and
optional execution quotes in separate SQLite state. It does not drain outboxes
or open paper positions. `replay_v6_shadow` uses actual observed decision times
and bound frozen exit receipts; unresolved selections suppress performance.
No actual forward scope or live parity/capture evidence has been collected.

Dashboard integration patch/module: `integrations/dashboard/`. The tested
publisher changes are staged in `/tmp/healys-v6-dashboard-followup/publisher`.
The separate dashboard checkout is `/home/healy/Coding/HealyLabsDashboard`;
its existing generic Training renderer needs no frontend changes. Optional
`V6_EXECUTION_ROOT` / `V6_SHADOW_ROOT` select evidence under `TRAINING_ROOT`.
Publisher campaign/progress settings were updated to the repair run; the new
optional execution/shadow evidence paths remain unconfigured pending results.
Code installation status: all four tested publisher files applied to the
dashboard checkout. Receipt/backups: `/tmp/healys-v6-dashboard-followup/`.

## Validation and preserved state

Full suite after the launch/pipeline additions: **1,522 tests +18 subtests
passed** (16 upstream warnings). Dashboard:
16 existing publisher tests plus three integration tests passed. Actual-data
preview has 32 scenario rows and no follow-up integrity issues.
All 121 original final-bundle artifact hashes match; all 20 original failed
NN receipts remain. Preexisting untracked `nn_meta/artifacts_v6/` is untouched
and must not be added. Changes are uncommitted on `main`.

Next operating steps: reproduce/fix the fold-3 cash-ledger failure, resume in a
reviewed fresh training scope, then automatic validation, actual quote/roll replay,
TradingView/provider/receipt parity and forward shadow evidence before any
promotion. Production ops/FA remain separate. iOS Mac/device acceptance and
actual broker-sale verification remain pending.
Prior handoff: `handoff-history/HANDOFF-2026-09-13-before-v6-followup-implementation.md`.
Prelaunch handoff: `handoff-history/HANDOFF-2026-09-13-before-training-relaunch.md`.
