# V6 reviewed: hold scanner promotion; dashboard summaries live — September 12, 2026

Campaign `v6-train-20260912r2` completed at 17:15:02 UTC. All stage receipts
returned 0. Final ensemble: GBT × 40, EV threshold 0.05, no drawdown brake,
164 features, full-ensemble risk gate eligible. It remains research-only under
the unverified TradingView contract; nothing was deployed to the scanner.
All 225 pinned research-source hashes remain unchanged from the scope.

## Results and evidence

[Full training summary](docs/reviews/2026-09-12-v6-training.md) now records
runtime, dataset, folds, calibration, PBO/DSR, objective comparisons, final gate
and limitations. Marked test return/maxDD by fold: +73.3%/23.6%,
+205.4%/11.9%, +61.3%/22.4%. Final validation: +648.8%, 12.6% maxDD,
241 kept trades. That final tail is selection/revalidation, not another test.
Deployment review found all 20 NN receipts have NaN validation loss. Two
all-missing ICT columns left NaN arrays and inspected weights; final NN
predictions are constant. The zero-trade family comparison is invalid.
GBT results remain worth developing: matching shared-accounting test baselines
show v6 higher return in 2/3 folds and lower drawdown in all three. The final
241-position marked ledger replays exactly, but aggregate-bar fills can be
delayed and base costs omit explicit spreads. Expanded live inputs are not
connected to scan_pass. Verdict: hold scanner promotion; no retraining or
scanner deployment was performed during review. See the
[deployment review](docs/reviews/2026-09-12-v6-deployment-review.md).

Evidence root: `nn_meta/campaigns/v6-train-20260912r2/v6/`:
`continuation_scope.json`, `runs/continuation/*.json`, `reports/evaluate.*`,
`reports/objective-comparisons/`, `model_final/{ensemble_config,manifest}.json`.
The original build's OOM failure and first continuation's memory-throttle stop
remain preserved. Do not relabel or overwrite those campaigns.

## Watcher fixed and dashboard delivered

The old progress timer checked `v6-local-20260906`, creating the false stopped
report. `scripts/watch_v6_progress.py` now understands the continuation
supervisor, seed jobs and stages without workers. The installed service binds
explicitly to r2 and omits `--telegram`, as requested. Local receipts are in
`logs/v6-progress/v6-train-20260912r2/`. No Telegram summary was sent.

The private dashboard at https://stonks-22367.web.app now has Training with
Compare and V2/V3/V3.1/V4/V5/V6 report views. Completed v6 summary and all six
versions were verified in the live home document; public frontend HTTP 200,
anonymous data reads 403. `TRAINING_ROOT` and `TRAINING_CAMPAIGN` are configured
in the existing home publisher environment. The minute publisher updates both
Research and Training; original source text and downloads stay private.

Dashboard code is `7d82c85` (initial library `e86f9fb`) on
`ops/firebase-dashboard-20260911`, pushed and
active in `/home/healy/Coding/HealyLabsDashboard`. Its detailed review and
handoff are in that checkout. Do not merge its older research snapshot over
main. Scratch development clone: `/tmp/healys-training-library`.
The correction detects failed NN losses, shows `Complete · review required`,
and includes the deployment review as a private source/download. Revised
desktop/phone warning rendering and publisher regression checks passed.

Validation: main 1,472 tests + 18 subtests; dashboard 16 publisher tests,
7 frontend units, 8 desktop/phone browser checks, 2 Auth emulator checks,
production build and private-evidence bundle scan. User systemd reported
successful training exit and successful post-completion publisher execution.

Next: enforce finite NN preprocessing/training checks in a fresh scope, run
frozen-policy execution/cost and same-marked-ledger baseline comparisons, then
complete verified live inputs and forward shadow evidence before promotion.
Preserve the existing campaign and its failed NN evidence. Production ops and FA remain separate in
`/tmp/healys-server-alert-readiness` and `/home/healy/Coding/HealysAutomation`.
Standalone iOS still needs Mac/device acceptance. Actual broker sale
verification remains pending. Preexisting untracked `nn_meta/artifacts_v6/`
is untouched and must not be added. Prior full state is archived in
`handoff-history/HANDOFF-2026-09-12-before-watcher-dashboard-completion.md`.
