# EXPERIMENTS — every generation's verdict in one table

The scoreboard. One row per evaluated model generation / major run; newest
first. "Ex-outlier" is the ex-top3 check — the difference between a broad
edge and a lottery ticket. Full detail lives in each row's report path.
When the expert panel goes live, the second table tracks realized (paper)
per-expert performance.

## Backtest / walk-forward verdicts

| Gen | Date | Data regime | Verdict | Headline | Ex-outlier signature | Detail |
|---|---|---|---|---|---|---|
| v4 ledger re-run (Option B) | pending | 118 sym / ~2y, mark-to-market selection | — | — | — | `TODO.md` phase 1 |
| v4 Option A bundle | 2026-07-21 | full v31 dataset, nested final pass | deployable **candidate** (gates 4/5) | gbt/filter/thr 0.5, 40 seeds → `model_final_v4/` | selected under the old simulator — Option B re-checks | `docs/specs/V4_OUTLINE.md` |
| v4 nested walk-forward | 2026-07-21 | 118 sym / ~2y, purged, per-fold selection | causal fixes **real** | folds: +754.6% / +354.3% / +117.4% | worst fold retains 31% ex-top3; winners diversified, no repeat symbols | `docs/specs/V4_OUTLINE.md` stage 0 |
| v4 ablation | 2026-07-21 | static window, 4 treatments | `prem_spot` **was leaking** | legacy +136.6% → corrected **+72.6%** (still positive) | — | `docs/specs/V4_OUTLINE.md` stage 0 |
| v3.1-at-scale | 2026-07-21 | 118 sym / 5 pools / ~2y flat-files | ROBUST but **shelved** | WF 2/3 folds; one-shot +499% | fold 2 +1136% → **+18% ex-top3** (one 31x TQQQ trade); fold 3 real miss (−25.7% vs baseline +299%) | `docs/v31_run_history.md` |
| v3-small | 2026-07-11 | 55 sym / 7 strategies / ~2y | **ROBUST & LIVE** | beats baseline 3/3 folds; test +257.9% | ex-top3 barely moves in any fold (broad-based) | `nn_meta/reports_v3/meta_report.md` |
| GBT baseline (v3 data) | 2026-07-11 | 344k rows | NN ≈ tree on AUC (0.61–0.62) | pruned the pool: volume strat earns 0.28% gain | top feature was `prem_spot` (17%) — the future leak, on the record early | `nn_meta/artifacts_v3/gbt_report.md` |
| v2.2 | 2026-07 | 56 sym / 4 strategies / ~2y | ROBUST (retired baseline) | — | — | `nn_meta/reports/meta_report.md` |

## Live experts (the panel)

| Expert | Live since | Pool / policy | Ledger | Status |
|---|---|---|---|---|
| v3 | 2026-07-11 | v3, rank/label_excess/32x16, thr 0.6 | server alerts (no paper ledger yet) | **live**, ~1 alert/week |
| v4 | **2026-08-16** | v31 causal, gbt/filter thr 0.5 (Option A bundle) | `.v4_paper_ledger.json` on server | **live — paper mode**; bundle hot-swaps after the Option B re-finalize |
