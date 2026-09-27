# EXPERIMENTS — every generation's verdict in one table

## September 27 — preparation results and running acquisition

The full V7 entry-demand census, storage reclamation, lossless packed capture,
dated hours and finite blackouts are completed preparation. The real entry-data
capture service is now running. These are engineering/data milestones, not a
trained-model result or investment-performance verdict. No new model evaluation
row is claimed. See [current state](V7_CURRENT_STATE.md) and
[completed evidence](../ROADMAP.md#completed-work). Earlier dated verdicts below
retain their original scope and do not define current TODOs.

## 2026-09-25 — V7-2 daily audit and first V7-3 demand run

| Run | Actual scope | Verdict |
|---|---|---|
| Full causal daily/market context | 591 securities; 667,239 session rows; 1,182 prefix replays | PASS; together with the 1,773-store catalog audit, closes V7-2 |
| MTUM entry-demand pilot | 29,843 proposals; 8,451 variants; 3,552 requests; 76 contracts | PASS for pre-decision demand and export; starts V7-3, which remains open |

The demand run retains 75 no-fresh-stock-price target outcomes. No provider
download, execution outcome, training or performance result is claimed.
All 591 securities remain in scope. Full suite: 2,401 tests and 18 subtests.
[Artifacts, audit limits and continuation](reviews/2026-09-25-v7-2-complete-and-v7-3-start.md).


## 2026-09-23 — Daily V5/V6 incubator EV replay smoke

The curated V6 GBT EV bundle ran on the sealed September 22 candidate pass:
40 members loaded, 304 predictions, `executed_pending_outcome`, zero execution
failures. `prediction` now denotes EV; P(win) is retained separately as
`p_win`. The V5 Keras EV bundle loaded 40 magnitude heads and produced 304
predictions in a **compatibility-only** smoke test using V6-origin rows. The
daily campaign correctly marked V5 input-blocked because no genuine V5
candidate feed exists. Verdict: **execution contract passes for both; no V5
paper validation and no V5/V6 performance or readiness verdict.** Earlier
V6 smoke output labeled P(win) as `prediction`; do not reuse it for EV
scoring.

## 2026-09-23 — V6 contract-aligned incubator prediction pass

The live V6 GBT release (40 members, 164 features) was packaged and run against
the 2026-09-22 live candidate matrix. The matrix contained 304 rows, zero
duplicate identity keys, complete identity fields and expected sparse NaN
values. All 40 members loaded and produced 304 read-only predictions. Verdict:
**PREDICTION PASS — pending outcome join; no performance score.** The current
ledger does not yet contain candidate-level realized `net_return` values.

## September 14 — immediate short-DTE pipeline start

On the user's instruction, `v6-short-dte-20260914-now` started at 20:01:57 UTC.
It builds/audits all 449 symbols before automatic training. Resource limits
remain 8GiB/two cores, with an 08:30 UTC cutoff. The earlier queued `-launch`
timers are disabled. No short-DTE model or performance verdict exists yet.


## September 14 — short-DTE campaign scheduled after complete dataset pilot

`v6-short-dte-20260914-launch` has enabled dataset/training and progress timers;
first full execution is scheduled for 22:30 UTC. A fresh 80-row SPY pilot
passed assembly with PIT membership (10 rows, 550 marks), the 164-feature
contract and entry/roll cash/DTE audits. No full training or new performance
verdict exists yet. [Launch](reviews/2026-09-14-v6-short-dte-launch.md).


## 2026-09-14 — Frozen V6 paper alerts active; actual-short-DTE training next

The repaired `v6-cash-repair-20260913` completed September 13 at 19:47 UTC:
40 final GBT members, EV .05/no DD brake, 241 historical positions,
+648.8249% return/12.5673% maxDD. This is inspected final-tail revalidation,
not a fresh holdout. All 32 aggregate execution comparisons matched the
independent ledger. The earlier “finalizing” entry below records interim state.

Frozen experimental paper operation began September 14. By the 16:00 pass:
six paper entries, one strategy exit, five open positions and nine allocation
cycles. All seven entry/exit notices have server sent acknowledgments; watcher
healthy. The first opening pass missed its five-minute deadline and opened
none. Final runtime `d6660af` preserves all 4,722 saved opening candidate rows
byte-for-byte and replayed them in 275.047s. No forward profitability verdict
is drawn from one partial session. [Activation](reviews/2026-09-14-v6-forward-activation.md).

The actual-1–9-DTE experiment is now implemented and prepared as
`v6-short-dte-20260914`, but its full dataset/training run has not started.
It fixes the deployed GBT/Huber EV .05 policy and retains historical aggregate
fills, separate artifacts and an unchanged broad-DTE baseline comparison.
145 tests and a bounded real SPY entry/roll/tick pilot passed. No performance
verdict exists for this new campaign. [Implementation](reviews/2026-09-14-v6-short-dte-campaign.md).
The current model keeps its broad DTE competition. The selection audit found
no +200% return ceiling: short and extreme-return rows were present but lost
at EV, DTE comparison or allocation. [Audit](reviews/2026-09-13-v6-dte-selection-audit.md),
[next-run design](specs/V6_SHORT_DTE_EXPERIMENT.md).

## 2026-09-13 — cash rejection repaired; full rerun finalizing (interim record)

`v6-cash-repair-20260913` started at 18:04 UTC. All three evaluation folds
completed successfully; all 20 NN selection seeds passed finite numerical
checks. The finalizer selected GBT and is fitting the 40-seed ensemble
(14 complete at 19:08 UTC). Final ensemble gates/performance remain pending.
The original cash guard remains strict. Unfundable candidate books now receive
an explicit ineligible result; corrupt data still stops evaluation. Full suite:
1,537 tests +18 subtests passed. The exact failed fold-3 case now completes its
15-policy grid, with one unfundable policy rejected; both ledgers match the
funding rejection under four cost scenarios. This preflight is reused validation
evidence, not a new holdout. [Review](reviews/2026-09-13-v6-cash-repair.md).

## 2026-09-13 — V6 numerical repair and frozen revalidation

Finite neural preprocessing/receipts are implemented. A one-seed/two-epoch
smoke on 8,192/2,048 preserved train/validation rows produced finite,
nonconstant classifier and magnitude predictions across all 164 features;
the two unobserved session columns are explicitly inactive. This is a
numerical check, not a new family-selection or strategy-performance result.
Fresh full-training scope `v6-neural-repair-20260913r2` launched at 16:44 UTC
under `healys-v6-neural-repair-20260913r2.service`: three folds, forty final
seeds, two workers/two threads. The pipeline automatically follows training
with new-model execution revalidation and a readiness inventory. All five
fold-1 NN seeds completed finite classifier/magnitude validation checks.
Update at 17:13 UTC: all 15 NN fold seeds passed numerical validation, but
fold-3 policy evaluation failed on a cash-ledger entry rejection. Family
selection and final performance remain pending; no final ensemble exists.

Final-tail matching marked replay: candidate +648.8% / 12.6% maxDD (241),
frozen-DTE baseline +90.6% / 50.6% (205). With a five-minute entry-delay limit,
only 52 candidate positions remain: +48.2% / 9.5%, versus 120 baseline
positions: −13.8% / 57.6%. A separate cash/event implementation reproduced
all 32 policy/latency/cost curves. These are fixed-selection revalidation
results from the previously inspected final tail, not a new holdout; rejected
fills do not backfill slots. No execution quote campaign replay or forward
collection has run. Scanner promotion remains on hold.
[Implementation and evidence](reviews/2026-09-13-v6-followup-implementation.md).

## 2026-09-12 — v6 complete; hold scanner promotion after review

`v6-train-20260912r2`: 449 symbols, 4,281,562 retained rows,
62,289,803 marks, 164 final features. Three post-freeze folds selected GBT
policies; marked test return/maxDD: +73.3%/23.6%, +205.4%/11.9%,
+61.3%/22.4%. Final GBT×40 EV/0.05 validation: +648.8%, maxDD 12.6%,
241 trades, eligible under the configured risk gate. The final tail is
selection/revalidation, not a new held-out test. Research-only: deferred
external TradingView parity and globally frozen proposal scope remain.

All 20 NN receipts contain non-finite validation loss; two all-missing ICT
columns survived preparation as NaN, inspected weights are non-finite and
final NN predictions are constant. Zero NN trades do not establish a healthy
family comparison. GBT predictions are finite/nonconstant. Matching test
baseline replay under shared accounting shows higher v6 return in 2/3 folds
and lower drawdown in 3/3. Marked baseline/cost stress, realistic option fills,
external feature parity and the expanded live adapter remain promotion work.
PBO 0.178/0.178/0.490 and deflated
Sharpe 0.0017/0.0326/0.4685 limit the strength of the positive-return readout.
Event balancing remained mixed; the baseline training objective was retained.
No scanner deployment. All stage receipts exit 0; source hashes unchanged.
[Full summary](reviews/2026-09-12-v6-training.md) and the private dashboard
Training tab carry the tables, calibration, sources and final gate log.
[Deployment verdict and evidence](reviews/2026-09-12-v6-deployment-review.md).


The scoreboard. One row per evaluated model generation / major run; newest
first. "Ex-outlier" is the ex-top3 check — the difference between a broad
edge and a lottery ticket. Full detail lives in each row's report path.
When the expert panel goes live, the second table tracks realized (paper)
per-expert performance.

## 2026-09-12 — V6 objective comparisons: research metrics, no portfolio verdict

`v6-train-20260912`, reused byte-identically by `v6-train-20260912r2`.
Corrected expanded/unverified contract, immutable dataset hash
`dcf0003dafb8ac200af982cd342a838ea9b1d4ffa3da6405c84de19561a249e3`.
Predeclared temporal split: 1,965,006 training, 430,721 validation and 613,222
test rows, exit-time purge and one-day embargo. Test is April 6–August 24,
2026; it was not used to select hyperparameters. Correlated proposal rows
are not independent observations.

| Excess-label classifier | Test AUC | Test log loss | Test Brier |
|---|---:|---:|---:|
| Existing unweighted GBT | 0.60564 | 0.65283 | 0.230414 |
| Equal total training weight per simultaneous event | 0.60438 | 0.65267 | 0.230388 |

Event balancing is mixed: slightly better probability errors, slightly lower
AUC. Keep the main objective pending portfolio evidence. The separate Q10
return model achieved test pinball loss 0.06757 versus 0.08783 for a constant
training-quantile prediction; empirical outcomes below prediction were 11.09%
against the nominal 10%. This is useful downside-model evidence, not an
established portfolio improvement, calibrated risk guarantee or promotion.

Artifacts: `nn_meta/campaigns/v6-train-20260912r2/v6/reports/objective-comparisons/`;
`plan.json` and `results.json` bind settings/model/data hashes. Main baseline
walk-forward and full-ensemble gates are still pending. See the
[training review](reviews/2026-09-12-v6-training.md).

## 2026-09-05 — LIVE PANEL WAS INTRADAY-BLIND since launch (stale day-keyed bar cache) — FIXED

Found while designing the streamed-feed path. `data/vbt_data_loader.
load_price_data_smart` caches bars per (symbol, interval, start, end) with
no time component; the live scanners never passed `force_download`. Server
logs, 2026-09-03: the 13:30Z pass loaded 17 symbols from Alpaca and cached
files whose last bar was **2026-09-02 23:45**; every later pass that day
(13:45 → 19:45) was **118 cache hits, 0 loads**. Same on 08-25 (2,985 hits /
83 loads) and 09-02 (3,002 / 66). Across the last 14 sessions, alert and
scoring activity clusters at 13:32–13:33Z; days with any activity after
14:00Z are the days the cache happened to be empty. **Consequence: from the
scanner's launch (2026-07-05) through 2026-09-04, every expert — v3, v31,
[v4] real alerts since 08-24, [v5] — effectively scanned the previous
session's closed bars, once, at the first pass.** The free tier's 15-minute
SIP hole compounded it: even the first pass could not see the current
session's opening bar. Paper hit-rates and the watchlist record before
2026-09-08 are therefore first-pass-only and one session late; they must
not be compared with anything scanned after the fix.

**Fix (commit: see HANDOFF):** `_bar_loader` forces the download; the
paid Alpaca plan removes the 15-minute hole; the streamed bar store
(TODO "Live feeds") makes the loader read fresh bars without any REST.
Verified on the server after deploy: the loader returns Friday's last
closed bar. Forward-tracking restarts Monday 2026-09-08 from a clean slate.

## 2026-09-05 — 0.45 P(win) cut REJECTED by the walk-forward: a validation lure

The finalize sweep's best single-window row was `filter/0.45` (+355%, 24%
DD on the May–Aug tail; never in `KEEP_THRESHOLDS`). Re-running the nested
3-fold walk-forward with `--thresholds 0.45,0.5,0.55,0.6` (same seeds/epochs/
embargo; `nn_meta/reports_v5/v4_walkforward_thr045.md`): folds 1–2 unchanged
(the new cut never won validation); **fold 3's validation picked filter/0.45
over ev/0.05, and on test it returned +82.3% at 45.0% maxDD (marked
+91.5% / 50.0%) against ev/0.05's +452.8% / 8.4%** — a cap breach on test
that the standing grid never showed. One window said 0.45 was the best
row; the nested protocol says it is a selection trap. **`KEEP_THRESHOLDS`
stays [0.50, 0.55, 0.60].** (Same evaluate code; `--thresholds` is a new
CLI override that leaves the default grid untouched.)

## 2026-09-04 — v5 wide pool WALK-FORWARD: three eligible folds, no negative fold; finalize in flight

Dataset build finished on the box 16:55Z (441/441 rows + marks; cloud
fleets drained to 426, the box built the last 15 in ~4h). Marks audit over
ALL 441 symbols: 100% executed-trade coverage, 0 orphans. Assembled with
`--membership` ON: **2,113,590 rows** (1.62M dropped outside point-in-time
membership), marks 24.7M rows / 1.33M trades, train/val/test
1.37M/306k/442k rows. Determinism check on the box PASSED (2× smoke,
byte-identical). Everything below ran ON THE HOME BOX (DECISIONS
2026-09-03); the full 3-fold walk-forward took ~21 min, and a second run
reproduced it bit-for-bit.

**Walk-forward** (`v4_evaluate --folds 3 --marks`, seeds 0–4, 60 ep, gbt
600, embargo 1D; `out/v5/evaluate-20260904T173053Z-box/` and the
PBO-bearing rerun `…-box-pbo/`): **nn wins all three folds, all three
gate-eligible through the ledger.**

| fold | winner | test return / maxDD | marked return / maxDD | DSR | PBO |
|---|---|---|---|---|---|
| 1 | nn filter/0.55 | +74.1% / 36.7% | +71.5% / 34.5% | 0.06 | 0.36 |
| 2 | nn ev/0.05 | +320.8% / 37.3% | +321.1% / 39.6% | 0.92 | 0.26 |
| 3 | nn ev/0.05 | +452.8% / 8.4% | +500.6% / 10.7% | 0.98 | 0.24 |

**Against v31** (the 2026-08-21 verdict, same protocol: +485%/23%,
**−11%/75%**, +159%/32%; DSR 0.02 on fold 2): the wide pool has NO losing
fold and no fold above the 40% cap; fold 2 — the Oct–Mar shock window
that broke v31 — is +321% at 37% DD instead of −11% at 75%. Fold 1 is
the weak seat (DSR 0.06, filter mode won, ex-top3 test only +7.7%).
Caveats on the record: fold windows differ from v31's (v5's train starts
2024-12-02, membership-filtered); score-decile top-decile inversion
flagged on folds 2–3 (the EV head's deciles are noisier than v31's);
n_kept is small everywhere (142–169 test trades per fold), so the
percentages are lottery-shaped by construction — ex-top3 test: +7.7% /
+250% / +339%.

**PBO was never in any prior report.** `choose_policy` computed it since
2026-08-24 but `evaluate_window`'s per-fold summary dropped it; fixed
today (`nn_meta/v4_evaluate.py`, regression test in
`tests/test_v4_evaluate.py`). Values above are the first ever surfaced:
0.24–0.36 over a 15-candidate grid (12,870 CSCV combinations).

**Finalize** (`v4_finalize --marks`, 60 ep, gbt 600, bundle redirected to
`nn_meta/model_final_v5/` so the tracked V118 bundle is untouched):
cheap-seed selection picked **nn ev/0.05, val +421.8%, eligible** — then
**the full 40-seed ensemble FLIPPED to ineligible: ev/0.05 val +201.3%,
n_kept 154, maxDD 16.4%. FINALIZE REFUSED; nothing persisted.** The
binding gate term is *beat the frozen baseline ex-top3*: on finalize's
validation tail (last 15% of days, **2026-05-21 → 2026-08-21**, 193,549
executed proposals, mean net_return +6.7%/trade, single trades up to
+6978%) the take-everything baseline returns **+2781%** through the
ledger and its ex-top3 bar is **+381.9%**. No candidate came close (best:
ev/0.05 +201%, filter/0.5 +197%, ev/0.0 +141%; every row under the 40%
cap, every row above 10 kept). Log + grid:
`out/v5/finalize-20260904T183947Z-box-REFUSED/`.

**FINALIZE ELIGIBLE under the adopted gate (a) — first v5 bundle
(2026-09-05 00:47Z, `out/v5/finalize-20260905T004700Z-box-risk-ELIGIBLE/`,
163 files hashed).** DECISIONS 2026-09-04: the beat-baseline term is
return per unit of drawdown vs the ex-top3 book (`GATE_BAR=risk`). Same
deterministic training, third reproduction to the digit: **nn × 40 seeds,
`ev/0.05`, dd_brake=None, val +201.3%, n_kept 154, maxDD 16.4%,
ratio 12.2 vs bar 6.64, selection_basis=ledger, eligible=True.** Bundle at
`nn_meta/model_final_v5/` (48 features, `ensemble_config.json` records
`gate_bar: risk`); V118 in `model_final_v4/` untouched. NOT deployed —
the live scanner reads `model_final_v4/`; promotion is a separate user
decision (deploy runbook: DOCUMENTATION.md; server pulls by `git pull`,
bundle dir would need to be tracked or synced).

**Runs (a)/(b)/(c) + the confidence axis — ONE training, every policy
(2026-09-04 evening; `out/v5/finalize-20260904T232143Z-box-allgates-REFUSED/`,
`nn_meta/reports_v5/policy_gate_sweep.md`, `scripts/policy_gate_sweep.py`).**
The 40-seed ensemble is deterministic (this run reproduced +201.3% / 154
kept to the digit), so thresholds, modes and every gate parameter are
post-hoc policies on its saved validation predictions
(`finalize_val_predictions.parquet`, written by finalize since today).
Bars on the 2026-05-21→08-21 tail: standing ex-top3 **+381.9%**; (a) risk
= return/maxDD > **6.64** (the ex-top3 book: +382% at 57.5% DD); (b) median
ex-top3 over 8 / 16 tie-shuffled draws **−26.3% / −38.8%**; (c) ex-top-k at
2% / 5% / 10% of the book (k=5/11/21) **+129% / −55% / −90%**.

| policy | kept | return | maxDD | ret/DD | ex-top3 | standing | (a) risk | (b) med-8/16 | (c) 2% / 5% |
|---|---|---|---|---|---|---|---|---|---|
| filter/0.20–0.40 (identical) | 162 | +237.5% | 25.7% | 9.2 | +105.5% | · | ✓ | ✓ ✓ | ✓ ✓ |
| **filter/0.45** | 150 | **+355.2%** | 24.0% | **14.8** | +144.9% | · | ✓ | ✓ ✓ | ✓ ✓ |
| filter/0.50 | 164 | +196.9% | 31.6% | 6.2 | +49.9% | · | · | ✓ ✓ | ✓ ✓ |
| filter/0.55 | 114 | +107.1% | 31.4% | 3.4 | +42.9% | · | · | ✓ ✓ | · ✓ |
| filter/0.60 | 32 | −12.6% | 24.5% | −0.5 | −22.7% | · | · | ✓ ✓ | · ✓ |
| filter/0.65–0.90 | 0 | — | — | — | — | · | · | · | · |
| rank/0.20–0.45 (identical) | 153 | +106.5% | 18.4% | 5.8 | +58.7% | · | · | ✓ ✓ | · ✓ |
| rank/0.50 / 0.55 / 0.60 | 144 / 128 / 75 | +75.6% / +41.7% / +10.1% | 21% / 16% / 18% | 3.5 / 2.6 / 0.6 | | · | · | ✓ ✓ | · ✓ |
| rank/0.65+ | ≤1 | — | — | — | — | · | · | · | · |
| ev/0.0 (brakes 0.2/0.3) | 171 | +141% (+119% / +126%) | 26% (22% / 23%) | 5.4 | +80.4% | · | · | ✓ ✓ | ✓/· ✓ |
| **ev/0.05** | 154 | +201.3% | **16.4%** | 12.2 | +88.6% | · | ✓ | ✓ ✓ | ✓ ✓ |
| ev/0.05 brake 0.2 / 0.3 | 154 | +192.5% / +195.5% | **14.3%** / 15.0% | **13.4** / 13.0 | +86% / +87% | · | ✓ | ✓ ✓ | ✓ ✓ |
| ev/0.10 (any brake) | 6 | +3.3% | 12% | 0.3 | | · | · | · | · |

**What the sweep says.** (1) *The "70% confidence" run is empty by
construction*: the ensemble's P(win) scores sit in a narrow band (p50
0.41, p90 0.50, p99 0.56, max 0.65 — the label base rate is 40%), so
filter ≥ 0.65 and rank ≥ 0.65 keep 0–1 trades. "Confidence" above ~0.6
does not exist in this model's output; rank mode (top-X%) or the EV head is
how conviction is expressed. (2) *The standing grid never tried 0.45*:
filter/0.45 is the best row on every axis (+355%, 24% DD, ret/DD 14.8,
ex-top3 +145%) and thresholds ≤ 0.40 are identical (the cut stops binding;
the 5-slot portfolio limits kept trades). Adding 0.45 to
`KEEP_THRESHOLDS` is a grid change — re-run the walk-forward before
believing it; it is one window here. (3) *Gate verdicts*: the standing bar
rejects everything. **(a) risk-aware** is the discriminating one — it
passes exactly filter ≤ 0.45 and the ev/0.05 family and rejects
filter/0.5+ and rank (higher DD per unit return). **(b) median-draws** and
**(c) ex-top-k at 5–10%** land their bars BELOW ZERO on this window, so
they pass 24 of 39 candidates including a −12.6% loser — too lenient as
parameterised (a bar of "don't lose more than 26%" is not a skill test).
(c) at 2% (k=5, +129%) behaves like (a). Recommendation on the record:
**adopt (a)** (or (c) at 2%) as the beat-baseline term; keep MIN_KEPT and
the 40% cap. Under (a) the refused run's own operating point (nn ev/0.05,
+201%, 16.4% DD) is eligible and finalize would persist it as-is.

**The bar itself, dissected (user challenge, same day; reproducible with
`scripts/gate_bar_sensitivity.py`).** The "baseline" is NOT every proposal:
it is the frozen per-symbol best strategy's proposals fed first-come
first-served into the same 5-slot ledger portfolio — **203 trades drawn
from 41,820 executed proposals**, win rate 37%, median trade −7%, maxDD
**46.6%**, and its +2781% is carried by a handful of tickets: ex-top1
+992%, ex-top3 +382% (the bar), ex-top5 +129%, **ex-top10 −44%**, ex-top25
−93%. Which 203 it holds depends on row order — proposals sharing an entry
timestamp enter in dataset order — so re-drawing with ONLY the
equal-timestamp ties shuffled (8 draws) gives ex-top3 bars of **−66%,
−53%, −48%, −45%, −34%, +13%, +66%, +283%** (median −39%; baseline maxDD
47–77%, median 65%). The +381.9% finalize was judged against is the
luckiest of nine draws. Against seven of the eight re-draws the refused
ensemble (**ev/0.05 +201%, maxDD 16.4%, 154 kept**) clears the bar; its
drawdown is a quarter of the baseline's under every draw. The gate's
beat-baseline term (DECISIONS 2026-08-24) compares raw return only — no
risk term on the baseline side, and ex-top3 does not de-lottery a
5-slot book of this size. **So the refusal is a property of one arbitrary
tie order, not of the model.**

Still true and still on the record: the same policy went +422% (5 seeds)
→ +201% (40 seeds) on the same window, and ~150 kept trades is
lottery-shaped for the candidate too (walk-forward ex-top3 test: +7.7% /
+250% / +339%). **VERDICT: the wide pool beats v31 on the nested
walk-forward (no losing fold, no cap breach, PBO 0.24–0.36). Finalize
REFUSED under the standing gate, but the bar it failed is shown to be
tie-order noise. V118 stays live; the v5 bundle was not persisted.
USER DECISION: how the beat-baseline term should be defined** — options
on the record: (a) a risk-aware bar (e.g. candidate must beat the
baseline's return AND not exceed its maxDD, or compare return/maxDD);
(b) an order-robust bar (median ex-top3 over N tie-shuffled draws);
(c) a heavier outlier trim scaled to book size (ex-top-k with k ≈ 5% of
n); (d) keep the gate and re-finalize on another `--val-fraction`. Any of
these is a DECISIONS entry, then one finalize re-run (~1h on the box).

## 2026-08-29 — v5 baseline freeze COMPLETE: the wide pool is genuinely wide

Fleet `v5-freeze-0f132b6-013536` (GCP Batch, image `0f132b6`, 453 tasks,
n2-highmem-8 spot): **453/453 symbols, zero task failures, zero
preemptions, ~75h wall, ~$40**. Merged spec published to
`gs://healys-backtester/artifacts_v5_in/baseline_spec.json`.

**441 symbols frozen, 12 skipped-thin** (BKNG, DRAM, KLAC, leveraged
micro-ETFs — a RESULT, not a failure; `freeze_all` skips names with no
freezable baseline).

**The finding that justifies the wide pool: every one of the 10 families
wins somewhere.** best_strategy distribution across the 441:

| family | rsi | stoch | bbands | volume | squeeze | supertrend | ma | elliott | macd | tv_rating |
|---|---|---|---|---|---|---|---|---|---|---|
| symbols | 182 | 49 | 46 | 42 | 40 | 39 | 28 | 11 | 3 | 1 |

v31's five families (ma, macd, rsi, squeeze, tv_rating) would have been
the best available choice for only 254 of 441 names; the five families v5
added take 187. That is the raw-material case for the generation — NOT
yet an edge claim: the pruning discipline (activity guards, GBT gain) and
the verdict come after the dataset build and the evaluate ladder, with
PBO + deflated Sharpe attached.

Provenance note: rows for the dataset build come from three producers
(two cloud fleets + the home box), so BLAS-level float differences are
possible across symbols. Accepted — v5 has no identity-diff gate.

## 2026-08-21 (evening) — DD-aware gross brake on EV sizing: walk-forward unchanged, finalize REFUSED again

`0c74274` (brake `max(0.25, 1 − dd_now/dd_brake)` on realized drawdown at
entry, brakes {None, 0.20, 0.30} in the ev grid). Batch, `e2-standard-8`.
**Walk-forward** (`out/evaluate-20260821T221528Z-4ae40/`): every fold chose
`brake=None` and the table is IDENTICAL to the unbraked run (fold 2 still
−11.4% / 75.1% DD). Structural, not noise: unbraked EV's VALIDATION DD was
already under the cap in every fold (31.7 / 36.8 / 19.9%), so it was
eligible with the higher return and the rank rule (eligibility, then
return) never trades return for risk where the cap isn't binding. The brake
can only win where unbraked is ineligible — the full-ensemble validation.
**Finalize** (`v4-finalize-0c74274-171307`): `ensemble winner: ev/0.05
val +605% n_kept 219 eligible=False` — unchanged, so NO braked candidate
cleared the gate either. Why is not visible (the refusal printed only the
winner); `2e6c434` adds the full candidate grid to the finalize log and a
finalize-only re-run is in flight. Hypothesis: the brake keys off realized
(closed-trade) drawdown, but a shock drawdown is MARKED — open positions
crater together before any close, so the brake sees dd≈0 and never fires.
**GRID VERDICT (`v4-finalize-2e6c434-182208`, same numbers): the DD cap was
NEVER the binding gate.** Full-ensemble validation: baseline (take
everything, ledger) **+1853.6%**; `ev/0.05` +604.8% / maxDD **21.9%**;
`ev/0.05 brake=0.2` +224.9% / 20.3%; `ev/0.05 brake=0.3` +340.8% / 21.2%;
`filter/0.5` +22.5% / 29.5%; `ev/0.0` +73.1% / 32.2%; `ev/0.1` −50.9% /
69.0%. Every candidate fails **beat-baseline**, not the cap. The baseline is
outlier-driven (raw max trade return 1526×; one such ticket at a 10% slot is
+15,000% alone) and, taking every proposal, always holds it — a selective
policy that skips that ticket cannot "beat" it. Both earlier "refused on the
DD cap" readings (2026-08-21 morning + this entry's first half) were
inferences from a log that printed only the winner; retracted. The brake
works as designed (DD 21.9→20.3%, return cost) and was aimed at the wrong
term. **Open decision (user): make the beat-baseline term robust — compare
against the baseline's `total_ex_top3` (option 1, recommended), winsorize
both sides, or leave it.** No V118 bundle.

## 2026-08-21 — EV head wired; v4 evaluate×2 + finalize relaunched on Batch; spx0 seat wired

**v4 magnitude/EV head** (`c17193c`): regression head per family (Huber on
signed `net_return` winsorized at train 1/99% — raw max is 1526×), `ev`
policy mode through shared sim AND ledger (per-trade `size_fraction` ≤ slot),
persisted per seed, loader/scanner threshold on the bundle's own decision
score. Gate unchanged. Local `--smoke` (untrusted box, code path only): both
heads trained; `ev/0.05` won the GBT family on validation; EV-head deciles
monotone with top decile best. Batch jobs (STANDARD, `e2-standard-8` after
`n2` and `n2d` pools were exhausted in us-central1): `v4-evaluate-c17193c-113654`
(folds 3), `-113658` (ablation), `v4-finalize-c17193c-113702`. **WALK-FORWARD VERDICT** (`out/evaluate-20260821T163913Z-40c60/`): the
`ev` mode won ALL THREE folds, every fold gate-eligible through the ledger,
top-decile inversion GONE in every fold (top EV decile +12/+15/+8% vs
bottom −10/−3/+1%). Test: fold 1 +485% (DD 23%, marked +552%/26%); fold 2
**−11% (DD 75%, marked −1.5%/69%, DSR 0.02** — val +1689% collapsed on the
Oct-Mar shock window); fold 3 +159% (DD 32%, marked +135%/**45%**).
**FINALIZE REFUSED** (`v4-finalize-c17193c-113702`): ensemble ev/0.05,
val +605%, n_kept 219, eligible=False → by elimination the **40% ledger
drawdown cap**. Conclusion: the EV head fixes SELECTION (the inversion and
the fold-3 refusal); DRAWDOWN is now the binding constraint on three
independent measurements. No V118 bundle; nothing persisted. Next lever, if
pursued: a drawdown/vol-aware gross scaler on EV sizing, fold-selectable.
**ABLATION** (`out/evaluate-20260821T163916Z-477c0/`): UNCHANGED by the EV
head — nn/rank/0.55 wins all four runs; run 1 reproduces stage-0 (+141%,
marked +141%/19%); run 2 v4-unpurged +52%; purged rows still ⚠ (legacy
−44%/63% DD, v4 +82%/25%). `ev` candidates were in every grid and lost on
the ablation's earlier validation window. EV deciles not inverted anywhere.
Reading: EV's win is regime-dependent (later folds); drawdown binds everywhere.

**spx0 seat** (`27adf68`): builder + fills + costs + evaluate, see HANDOFF
and `docs/specs/SPX0_SPEC.md`. 80-session local smoke: 55% fill rate, win
rate ~18-27%, baseline ≈ −85%.
**VERDICT — NO EDGE AFTER COSTS** (`spx0-run-27adf68-115405`,
`out/spx0-20260821T165653Z-4b630/`): 500 sessions, 16,964 proposals,
10,380 filled (61%). Baseline (take everything) −99..−100%. Winners: fold 1
nn/filter/0.4 val −8% n13 → test −22% (DD 34%, marked +10%/25%); fold 2
nn/filter/0.4 val −1% n27 → test −33% (DD 42%, marked −18%/37%); fold 3
nn/ev/0.05 val n=1 → ⚠. Folds 1-2 "eligible" only by beating a −100%
baseline — not a pass in spirit. The model RANKS (top P(win) decile −12% vs
bottom −45% every fold) but the top decile is still negative: no subset
clears ~40% round-trip cost on a 0.30 premium. Cost modeling was named the
make-or-break (ROADMAP) and it broke. Different designs, not tuning, if
revisited: sell premium; liquid OTM strikes; re-sweep params for 5m bars.

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
| v4 | **2026-08-16** (paper) → **2026-08-24 REAL** | v31 causal, **V118: gbt×40 ev/0.05, no brake** (first gate-eligible bundle, ex-top3 gate) | `.v4_paper_ledger.json` on server | **live — real alerts** since 2026-08-24; scan self-enforces verified+eligible |
| v31 | **2026-08-16** | v31 legacy nn, rank thr 0.55 (40 seeds) | server alerts (`[v31]` label; no ledger yet) | **live — paper expert**; settles the outlier-fragility question with forward tracking |

## 2026-08-24 — PIT universe BUILT + FROZEN: 21 survivorship-free monthlies, v5 unblocked

All four spec steps landed in one day (`PIT_UNIVERSE_SPEC.md`; commits
`9b212df`→`e77f510`). Stage A: 496-day OPRA day_aggs backfill on the home
box — the rolling entitlement starts **2024-08-26** exactly (probed), ~4.6k
option roots/day, 42 MB of daily rows. Stage B: monthly reconstitution
2024-11→2026-07, ~300 members/month (270–309), ~10/month churn each way —
the hysteresis defaults (270/330, 63d median, ≥50 active days) held on the
churn report, no retune. Gates: delisting canary PASSED — **X** (US Steel),
**SWTX**, **WBA** enter while alive and exit after death; a churn-free
history would have refused to freeze. Found in the data: FI→FISV (2025-11)
and BITF→DRAM (2026-04) renames — next-day handoffs matching the SQ→XYZ
seam — added to `TICKER_ALIASES`. Stage C: `NN_META_POOL=v5` now derives
453 UNDERLYINGS from the frozen artifacts; `--membership` (default ON for
v5) filters every (symbol, month) dataset row through `members_asof`.
**The v5 generation's last blocker is gone.**

## 2026-08-24 — spx0 round 4 (concentrated grid): sharper highs, unstable folds — no seat

`spx0-run-f5294d8-144212` (~2h20m, image `f5294d8`, ma/orb_15/rsi ×
verticals + gap_fill_50 × longs, 20× less flow than round 3):

| fold | winner | test / maxDD | marked | defl. Sharpe | vs round 3 |
|---|---|---|---|---|---|
| 1 | nn ev/0.00 brake .30 | −25.9% / 35.9% | −10.3% / 34.1% | 0.00 | better (was −50.6%) |
| 2 | gbt ev/0.10 brake .30 | **+48.5% / 31.0%** | +90.6% / **40.5%** | 0.17 | much better (was +2.7%) |
| 3 | nn rank/0.35 **⚠ none cleared** | −26.3% / 76.2% | +188% / 67.0% | 0.08 | worse (was +10.2% ✓) |

Concentration amplified fold 2 dramatically but BROKE fold 3 (validation
refused every candidate; round 3's fold-3 winner had cleared) and fold 2's
marked DD (40.5%) still breaches the 25% cap. The pool's story is now
regime instability, not toll: each fold's edge lives in a different
regime slice and ~2 years of 0DTE data gives each fold too little of each
regime to select reliably. That is precisely the case for lever 5 (2022
bear data — blocked on the Massive Advanced upgrade, user deciding) or an
honest park with the best exit-note the pool has had. Four rounds run
2026-08-21..24; the machinery (bounded verticals, seat mapping, package
fills) is durable regardless.
Report: `out/spx0-20260824T194433Z-45fc0/artifacts_spx0/`.

## 2026-08-24 — vol track stages 1–2 DONE at scale: HAR-RV is the bar to beat

`vol-build-d8e5416-161740` (16 spot shards, ~25 min, <$1): 289/289 symbols'
per-session intraday RV features (2017→, `available_at`-stamped) published
to `out/vol_features/`; 288 evaluated (864 symbol-folds, expanding OOS):

| model | mean QLIKE | HAR wins per symbol-fold |
|---|---|---|
| **HAR-RV** | **0.1174** | — |
| GARCH(1,1) | 0.2588 | 98.7% |
| naive | 0.2928 | 99.2% |

Per regime tercile HAR wins 93% (calm) / 96% (mid) / 98% (stressed) of
folds — the boring baseline is strong and UNIFORM. The track-1 seat gate
is now a number: a sequence model ships only if it beats HAR-RV's QLIKE
in every tercile; otherwise the features ship without it (they are usable
by every expert as-is via `out/vol_features/<SYM>.parquet`).

## 2026-08-24 — spx0 round 3 (verticals + intraday): first signs of life, not yet a seat

`spx0-run-48db82e-095520` (~5h, image `48db82e`, 6 variants × 11 strategy
seats, 3-fold nested walk-forward, ledger-selected):

| fold | winner | test return / maxDD | marked | deflated Sharpe |
|---|---|---|---|---|
| 1 | gbt ev/0.10 | −50.6% / 50.6% | −18.1% / 36.2% | 0.00 |
| 2 | gbt filter/0.55 | **+2.7% / 16.1%** | **+11.6% / 21.3%** | **0.20** |
| 3 | nn ev/0.05 brake 0.20 | **+10.2% / 29.2%** | +26.2% / 28.6% | 0.01 |

**The structural fix worked**: no fold blew up — worst marked DD 36% vs
round 2's 1126%; the vertical's −1×margin floor held in production-scale
data. Two of three folds positive after costs for the first time in this
pool (round 1: all negative; round 2: catastrophic). Still NOT a seat:
fold 1 is bad, deflated Sharpes are weak (0.20 best), and fold 3's marked
DD (28.6%) breaches the 25% cap. Trajectory is real, edge is not proven.
**Composition diagnosis (same day, dataset-level per fold-test window):**
1. NO variant is profitable take-everything anywhere — every fold-2/3 win
   came from model selection carving a subset out of a negative pool; the
   friction toll stands.
2. Verticals are structurally better raw material than longs everywhere:
   means −0.05..−0.16 vs −0.23..−0.36 per margin, win 54–64% vs 15–26%.
   The bounded-loss redesign moved the pool from hopeless to selectable.
3. The intraday sweep mostly added toll, not edge: vwap_rev alone
   generated ~24k of ~35k intraday trades at −0.15 mean (it sells into
   moves that keep going); `orb_15` is the best intraday seat on
   verticals (−0.016, near breakeven). gap_fill is tiny-n and works on
   the LONG side (+0.05..+0.13 at 50bp), not verticals.
4. POSITIVE take-everything cells exist and are consistent across the
   whole variant axis, not one outlier: `ma`-signal verticals (+0.08..
   +0.12 across all three widths, n≈150 each) and `gap_fill_50` longs
   (+0.05..+0.13 across all three stops, n=86).
Round-4 shape the data suggests: concentrate the grid on seat×structure
pairs that work (ma/orb_15/rsi × verticals; gap_fill × longs), drop the
vwap_rev flood, fewer trials. Alternatives: lever 5 (2022 data — Massive
upgrade) for regime depth, or park. USER DECISION.
Report: `out/spx0-20260824T145751Z-41a00/artifacts_spx0/`.

## 2026-08-24 — FA discovery: FIRST frozen monthly Top-10 (August 2026)

`fa/artifacts/top10_2026-08.json` + `.md`, frozen 2026-08-24 (cutoff same
day; write-once). 275 tickers scored from ~7 weeks of archive across
social (reddit posts/comments + StockTwits) and news (Finnhub/AV);
velocity z vs each name's own 90d baseline; corroboration ≥ 2 families;
liquidity floor = universe_300. Top-10: IBIT, HTZ*, BMNR*, NKE, TEM*,
CIFR*, SLS, B*, GDX, RBLX (* = NEW vs the training pool). Forward
tracking starts now (`fa.tracker`); the exit metric (≥3 monthlies
tracking) is 1/3 with the September freeze cron'd for Oct 1.

## 2026-08-24 — prem_spot leakage question CLOSED: it leaks, in both families

The 2026-08-20 confound (the ablation compared nn-on-legacy vs gbt-on-v4,
so schema and family moved together) is resolved by two single-family
ablations on image `a300830`, seeds 0-4, ledger-selected:

| family | schema (purged) | test return / maxDD |
|---|---|---|
| gbt | legacy (with prem_spot) | **−23.3%** / 25.8% |
| gbt | v4 (causal) | **+68.8%** / 39.1% |
| nn | legacy (with prem_spot) | **−44.4%** / 62.7% |
| nn | v4 (causal) | **+82.0%** / 17.3% |

Unpurged, legacy "wins" in both families (gbt +65.2 vs +26.6; nn +140.7
vs +52.5) — the signature of a leak: `prem_spot` helps exactly when the
evaluation is allowed to cheat and hurts when it can't. Same verdict from
two independent model families. Dropping it from the v4 schema was
correct; the standing warning is retired. Reports:
`out/evaluate-20260824T{143124Z-41040,143226Z-4eaf0}/`.

## 2026-08-24 — spx0 round 2 (sell-premium variants) REJECTED: test blowup

`spx0-run-6ab5120-010113` (image `6ab5120`, 500 sessions × 6 variants,
3-fold nested walk-forward, ~3h13m): **no seat.** Fold 1's winner
(rank/0.50, gbt) CLEARED the gate on validation, then returned **−1862.9%
on test with maxDD 1126%** — equity went negative: short-variant returns
are per unit margin, margin = (stop−1)×entry is small, and gap-through-stop
losses (smoke avg −1.5 to −2.1× margin) can exceed the posted margin, so a
cluster of 0DTE tail losses took the slot portfolio through zero. Fold 2
(filter/0.40, nn) −37.6% test; fold 3 nothing cleared (best ev/0.10 brake
0.30, −65.7%). Deflated Sharpe ≈ 0 on all three. Report:
`gs://healys-backtester/out/spx0-20260824T060344Z-47110/artifacts_spx0/`.

**Post-verdict caveat (2026-08-24 review):** this run's dataset carried a
~1-minute decision-side lookahead (spot/rv/premium features read the
forming 1m bar; fixed in `a300830`), which FLATTERED results — the
rejection therefore stands a fortiori. Any future spx0 run builds on the
fixed code.

**The structural lesson, on the record:** a validation-window DD cap does
not bound a short-premium seat's tail — the risk simply hadn't printed in
sample (fold 1 val passed a 25% cap, test hit 1126%). Any future short
design needs the loss bounded by CONSTRUCTION (margin sized to the true
worst case — e.g. margin = strike distance for spreads, or size scaled so
a settlement-at-intrinsic loss ≤ margin), not by a stop that assumes the
next print is near the last. The long-variant folds stayed merely
unprofitable, as in round 1. Next levers per SPX0_SPEC: item 3
(intraday-native strategies swept in-fold) for the long book, and/or a
defined-risk redesign of the short (verticals, not naked) — user decision.

## 2026-08-24 — v4_finalize ELIGIBLE under the ex-top3 gate: first V118 bundle

`v4-finalize-6ab5120-023421` (image `6ab5120`, e2-standard-8 after the n2
pool stocked out ~90 min; same verified dataset+marks as the 08-21 runs):
**eligible=True.** Winner **gbt × 40 seeds, mode `ev/0.05`, dd_brake=None**
— val +604.8%, n_kept 219, maxDD 21.9%, selection_basis=ledger, magnitude
head persisted. The gate's new bar (DECISIONS 2026-08-24) is the baseline's
`total_ex_top3` = **+31.4%**; the raw baseline (+1853.6%, one 1526× ticket)
is recorded but no longer the bar. Same candidate that won all three
walk-forward folds on 08-21 and was refused three times on the outlier bar.
Bundle: `gs://healys-backtester/out/finalize-20260824T073639Z-44b60/model_final_v4/`
→ rsynced local, `v4_scan --selftest` OK (40/40, verified=True
eligible=True, score median 0.433 deterministic), force-added on the
branch. Before dropping `--paper`: candidate-parity re-validation against
THIS bundle (Option B step 4) + the `/ultrareview` → merge-to-main path
(main is still deliberately behind the branch).

## 2026-08-21 — v4_finalize REFUSED: no eligible config on the recent tail

`v4-finalize-493af85-010321` (verified dataset, image `493af85`, e2-standard-8):
all 40 GBT seeds trained (AUC ~0.598 each), the operating point was re-validated
on the full ensemble, and the gate refused to persist:

    ensemble winner: filter/thr=0.5  val_return=+22.5%  n_kept=78  eligible=False
    NO ELIGIBLE CONFIG — (kept >= 10, beat baseline, maxDD <= 40%).
    Nothing persisted; any existing model_final_v4 is untouched.

n_kept=78 passes, so it failed on **beat-baseline or the 40% maxDD cap** (the
log does not print which; no report file is written on the refusal path — only
SHA256SUMS landed in `out/finalize-20260821T061654Z-48940/`). Note finalize
validates on the MOST RECENT TAIL of all data (`_final_split`) — i.e. exactly
the fold-3 regime — so this is the fold-3 weakness caught by the last line of
defense, consistent with both purged ablation rows failing validation gates.
Two attempts, same result (RETRIES=1 → two output stamps).

**VERDICT: there is no V118 bundle to deploy.** The gate working as designed.
Paths forward: (a) fix the payoff-size inversion (magnitude-aware labels,
approved backlog 2026-07-19) and re-finalize; (b) explicitly loosen the gate
(`MIN_KEPT_TRADES`/`MAX_DRAWDOWN_CAP`/baseline rule in nn_meta/config.py) — a
deliberate override of a designed safety, user's call only; (c) proceed to
VSPNDX and revisit v4 after the label work. Deploy-alongside doctrine cannot
apply: finalize refuses to even produce the artifact.

## 2026-08-21 — fold-3 dig: March shock + failure to re-engage, NOT decay

Anatomy of the fold-3 loss (test window 2026-03-06 → 2026-07-02), from the
walkforward JSON + the verified dataset. Three findings:

1. **The frozen baseline ALSO lost: -9.2%** (fold baselines: +14.7% / +108.8%
   / -9.2%). The whole opportunity set turned: 2026-03 is the WORST month in
   the two-year sample (win rate 33.7%, median net_return -10.1%), and
   2026-02 was already negative. The fold OPENS with the worst regime in the
   data. Primary driver: market, not model.
2. **The model's real failure is not the crash but the recovery.** From April
   the opportunity set turned strongly positive (+16.0% / +6.8% / +8.5% mean
   monthly), yet the model finished -15.4% vs the baseline's -9.2% — it did
   not re-engage. Win rate stayed FINE (52.8%, higher than fold 1's 51.4%
   which made +177%); the payoff SIZE inverted — consistent with the known
   v3.1 top-decile size inversion (score ranks win probability, not win size),
   which the report's decile table shows directly (decile-10 win 0.493, mean
   return half of decile 2's).
3. Composition in the window: calls +12.1% vs puts +2.7% mean; `tv_rating`
   strongest (+15.3%), `squeeze`/`ma` weakest (+2.5%/+3.0%).

**Verdict: fold 3 is a regime shock the model rode down and then under-traded
on the way back — not monotonic alpha decay, and not a data artifact.** The
promotion gates are the correct guard for exactly this failure mode, so
deploying alongside as a gated expert is defensible; promoting to capital on
fold-3-like regimes is not, until the size-inversion is addressed
(magnitude-aware labels are already an approved backlog item, 2026-07-19).

User decision 2026-08-21: finalize and deploy alongside as **V118**; next
workstream **VSPNDX** (spx0).

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
