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
| v3 | 2026-07-11 | v3, rank/label_excess/32x16, thr 0.6 | server alerts (no paper ledger yet) | **live**, ~1 alert/week — NOTE: alert rate before 2026-08-16 was depressed by the thinning universe horizon (fixed; judge cadence from 08-17 on) |
| v4 | **2026-08-16** | v31 causal, gbt/filter thr 0.5 (Option A bundle) | `.v4_paper_ledger.json` on server | **live — paper mode**; bundle hot-swaps after the Option B re-finalize |
| v31 | **2026-08-16** | v31 legacy nn, rank thr 0.55 (40 seeds) | server alerts (`[v31]` label; no ledger yet) | **live — paper expert**; settles the outlier-fragility question with forward tracking |

## 2026-08-20 — v4 ledger re-runs on the VERIFIED dataset (GCP, image `493af85`)

First unconfounded ledger evaluation: dataset proven identical to stage-0, so
every delta below is the ledger/config, not the data. Both legs SUCCEEDED in
~30 min (e2-standard-8 STANDARD). Outputs + SHA256SUMS:
`out/evaluate-20260821T041241Z-49460/` (ablation),
`out/evaluate-20260821T041248Z-44b40/` (folds 3).

**Ablation** (schema x purged; marked = ledger, all rows 🄻):

| run | schema | purged | gate | test return | maxDD | marked |
|---|---|---|---|---|---|---|
| 1 | legacy | no | ✓ | +140.7% | 15.0% | +140.9% / 19.4% |
| 2 | v4 | no | ✓ | +52.5% | 32.2% | +54.3% / 35.7% |
| 3 | legacy | yes | ⚠ none cleared | -44.4% | 62.7% | -41.0% / 62.7% |
| 4 | v4 | yes | ⚠ none cleared | +82.0% | 17.3% | +84.1% / 25.4% |

- **Run 1 reproduces stage-0** (+140.7%/15.0% vs stage-0 +136.6%/15.0%) —
  closing the loop: same data in, same numbers out, and the void run's +64.4%
  is confirmed as pure corruption artifact.
- The ledger is not flattering: marked tracks sim closely with slightly HIGHER
  maxDD everywhere (e.g. 15.0→19.4). It is doing its job.
- **Both purged rows now FAIL the validation gate** (the void run claimed all
  gates passed — retroactively another corruption artifact). Their test numbers
  are diagnostic only. Purged-legacy collapsed outright (-44.4%/62.7%).
- Deflated Sharpe, winners: 0.791 / 0.533 / 0.001 / 0.424.

**Walk-forward, 3 folds** (v4 purged, all gates ✓):

| fold | test return | maxDD | marked | dSharpe |
|---|---|---|---|---|
| 1 | +177.4% | 18.8% | +183.0% / 24.6% | 0.803 |
| 2 | +354.3% | 48.7% | +421.1% / 45.7% | 0.816 |
| 3 | **-15.4%** | 38.9% | **-13.2% / 43.0%** | 0.076 |

**VERDICT on the two open questions:**
1. **Fold 3 is REAL, not a data artifact.** On clean data it still loses money
   (-13.2% marked), still has the worst maxDD (43.0%), and the report itself
   flags a top-decile inversion (decile-10 win rate 0.493 vs decile-2 return
   2x decile-10's). The most recent fold does not work. DO NOT finalize until
   this is understood — regime, capacity, or genuine decay.
2. **`prem_spot` remains OPEN.** This ablation report contains no feature-drop
   section (verified in md and json) — the 08-19 finding came from a different
   invocation. Needs its own run before it can be called resolved or refuted.

## 2026-08-20 — dataset rebuild verified IDENTICAL to stage-0 (diff gate, image `493af85`)

**VERDICT: the missing-frames mechanism explains 100% of the 2026-08-19
corruption, and the rebuilt dataset is trustworthy.** The full-scale rebuild
(90 stale symbols redone against the complete cache; job
`marks-build-d64ca9b-010138`, 118/118, 16/16 tasks SUCCEEDED, zero failures,
~21.5h on STANDARD) assembled and passed the new Batch diff gate on its first
run (`v4-diff-493af85-230233`, report `out/diff-20260821T040444Z-43e30/`):

- 489,255 rows aligned, 0 baseline-only, 0 candidate-only
- **IDENTICAL — every shared column matches on every aligned row.** The 13
  differing columns from the void run collapsed to zero, as predicted.
- Candidate carries 3 extra columns (`fill_entry_ts`, `fill_exit_ts`,
  `gross_return`) — the v4 mark-stream additions, which postdate stage-0 and
  are expected.
- Chain of custody: baseline sha256 `353d090c…` (matches the independently
  recorded stage-0 hash); candidate sha256 `155bae9e…` (recorded in the
  report for future comparisons).

Consequence: the 2026-08-19 ledger re-runs (the entry below) were computed on
provably corrupt data and stay VOID; the evaluate legs must be re-run on this
dataset. The stage-0-vs-ledger comparison is now UNCONFOUNDED — dataset held
constant — so the next evaluate runs finally measure the ledger's effect alone.

## 2026-08-19 — v4 Option B ledger re-runs (GCP Batch, image `58c2e5b`)

First evaluation run entirely on cloud hardware, because the home box has proven
single-bit memory corruption (`HANDOFF.md`). Dataset rebuilt 118/118 with the
mark stream; `option_b_blockers` clean; every row tagged 🄻 so the ledger really ran.

**Ablation** (`out/evaluate-20260819T044509Z/`, sha in SHA256SUMS.txt):

| schema | purged | stage-0 | now | marked |
|---|---|---|---|---|
| legacy | no | +136.6% / 15.0% | +64.4% / 13.6% | +66.1% / 20.7% |
| v4 | no | +45.2% / 25.5% | +99.7% / 20.5% | +93.4% / 26.0% |
| legacy | yes | +90.9% / 27.2% | +33.5% / 19.4% | +31.4% / 19.3% |
| **v4 corrected** | yes | **+72.6% / 24.4%** | **+231.3% / 24.7%** | **+240.6% / 29.1%** |

All four cleared the gate; the corrected row has the best deflated Sharpe (0.920).

**Nested 3-fold** (`out/evaluate-20260819T044510Z/`):

| fold | stage-0 | now | marked |
|---|---|---|---|
| 1 | nn/filter/0.55 +754.6% / 25.5% | +394.3% / 18.9% | +418.0% / 27.0% |
| 2 | gbt/filter/0.50 +354.3% / 48.7% | +242.5% / 41.4% | +257.7% / 39.0% |
| 3 | nn/rank/0.50 +117.4% / 25.0% | +78.4% / **53.4%** | +85.6% / 54.9% |

**VERDICT: VOID — the run was computed on a corrupted dataset.**
*(Superseded 2026-08-19 evening. Original verdict was "NOT CLEARED FOR
FINALIZE — three open questions"; question 1 is now ANSWERED and it
invalidates the whole row rather than merely confounding it.)*

**Question 1 RESOLVED: the cache was incomplete, and the error is one-sided.**
44 of 486 flat-file day-frames were missing from the bucket when 90 of the 118
symbols were built (08-18); the 28 built 08-17 used a complete cache and are
unaffected. One mechanism accounts for every one of the 13 differing columns:
**16,617 rows (3.40%) had a different option contract selected**, and
contract/strike/expiration/executed/moneyness differ on exactly those rows,
with premium, fills, returns and labels downstream of them. All 16,500
`executed` 1→0 flips have a changed contract; ZERO flips without one. 86.8% of
changed rows enter on one of the 44 missing days, and the monthly profile
tracks the missing-day histogram.

**The bias has a direction: it FLATTERS.** Dropped trades average +0.017 net
return against +0.114 for survivors, so the incomplete cache removed the losers
and the book read better than the truth. Do not treat +231.3% / 0.920 as a
result to beat — the corrected numbers are expected to be LOWER, and lower is
the fix working.

Confirmed end-to-end on SPY before committing to the rebuild: 230 contract
mismatches vs stage-0 with the incomplete cache, **0** after rebuilding against
the complete one, none newly broken, `executed` restored 0.835859 → 0.893434
(stage-0's value to six decimals). Guard added: `nn_meta/cache_preflight.py`
fails the job closed on an incomplete archive.

**Questions 2 and 3 remain OPEN and are NOT resolved by clean data alone** —
check both explicitly on the re-run:



1. **The stage-0 comparison is CONFOUNDED.** Tracked stage-0 dataset hashes
   `353d090c`, the new one `2ba866dc`. Same 489,255 rows / 118 symbols / date
   span, but 13 of 66 shared columns differ: contract/strike/executed 3.40%,
   entry_premium/prem_spot 4.98%, label 4.31%, net_return 6.89%; `executed`
   mean 0.6440 -> 0.6106. Almost certainly the cache refreshes (universe
   `--live-horizon`, bars_daily compaction) changing contract availability.
   Two variables moved at once, so the +72.6% -> +231.3% jump CANNOT be
   attributed to the ledger. In a fat-tailed book a few percent of trades is
   more than enough to swing 3x.
2. **The ablation's leakage finding INVERTED.** Stage-0's argument was that
   dropping `prem_spot` halves return (+136.6 -> +45.2), proving it leaked. Now
   dropping it RAISES return in both conditions. Partly methodological: `nn`
   wins both legacy rows and `gbt` wins both v4 rows, so it compares
   nn-on-legacy vs gbt-on-v4 rather than one family across schemas.
3. **Fold 3 got worse under honest accounting** — maxDD 25.0% -> 53.4% and a
   flagged top-decile inversion (decile 1 mean return +0.1265 vs decile 10
   +0.0602) while win rate still rises correctly. It is picking frequent small
   winners and missing the rare large ones in that regime.
