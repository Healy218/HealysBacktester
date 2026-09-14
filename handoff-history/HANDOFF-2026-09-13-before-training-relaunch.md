# V6 follow-up coded; full repair training and forward evidence next — September 13, 2026

The user asked to code the September 12 review follow-up. Neural guards,
frozen execution/cost validation, matching marked baseline, independent cash
ledger, sealed expanded live inputs, isolated shadow recording/replay and
private dashboard publisher integration are implemented. Scanner promotion
remains on hold. No full retraining, scanner deployment or notifications ran.

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

Fresh full-training scope `v6-neural-repair-20260913r2` is prepared: 226 source
hashes and 1,376 inputs, original folds/seed budget. Use the runbook's
`continue_v6_training --repair-neural ... --run` command when starting the full
rerun. The older prepared scope without `r2` was superseded during coding;
preserve it and use r2. No corrected family comparison has completed yet.

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
Publisher environment was not changed and no new evidence was published.
Code installation status: all four tested publisher files applied to the
dashboard checkout. Receipt/backups: `/tmp/healys-v6-dashboard-followup/`.

## Validation and preserved state

Full suite: 1,506 tests + 18 subtests passed; subsequent focused checks cover
final small changes and the additional snapshot-sealer test. Dashboard:
16 existing publisher tests plus three integration tests passed. Actual-data
preview has 32 scenario rows and no follow-up integrity issues.
All 121 original final-bundle artifact hashes match; all 20 original failed
NN receipts remain. Preexisting untracked `nn_meta/artifacts_v6/` is untouched
and must not be added. Changes are uncommitted on `main`.

Next operating steps: full corrected training, actual quote/roll replay,
TradingView/provider/receipt parity and forward shadow evidence before any
promotion. Production ops/FA remain separate. iOS Mac/device acceptance and
actual broker-sale verification remain pending.
Prior handoff: `handoff-history/HANDOFF-2026-09-13-before-v6-followup-implementation.md`.
