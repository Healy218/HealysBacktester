# EXPERIMENTS — every generation's verdict in one table

The scoreboard. One row per evaluated model generation / major run; newest
first. "Ex-outlier" is the ex-top3 check — the difference between a broad
edge and a lottery ticket. Full detail lives in each row's report path.
When the expert panel goes live, the second table tracks realized (paper)
per-expert performance.

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
