# v3 Spec — Big-Universe Meta-Labeling

**Status (2026-08-15):** SHIPPED — v3 is the live scanner model and the
at-scale variant (v3.1) ran and was shelved; see `ROADMAP.md` ✅ Done and
`docs/v31_run_history.md`. Kept as the design record; the original draft
header follows unedited.

**Original status:** draft for review — not started.
**Prerequisites:** (1) v2.2 walk-forward verdict is in (`nn_meta/reports/meta_report.md`),
(2) the live alert scanner is deployed on a server and texting reliably
(research mode, alert-only). v3 work begins after both.

**One-line goal:** scale the v2 meta-labeling pipeline from 56 symbols / ~2 years
to 200+ symbols / 2017→present, with a modern indicator library, and let the
data decide between gradient-boosted trees and the NN ensemble.

---

## What carries over from v2 (proven, keep)

- **Meta-labeling frame**: base strategies propose trades; the model scores
  trade quality; portfolio construction turns scores into PnL. We do NOT train
  a model to emit raw PnL-maximizing positions — that memorizes the window's
  monster trades (the reason v2 reports `ex-top3`).
- **Leak-free freezing**: everything re-derived from fold-train only.
- **On-demand option fills** (`HybridCachedProvider`): fetch option bars only
  for contracts/windows that proposals actually touch.
- **Per-stage checkpointing** (v2.2 `artifacts/wf/` pattern): every long stage
  resumes; enables spot/preemptible compute.
- **Seed ensembles + honest evaluation**: multi-seed, majority gates,
  portfolio-level metrics with costs, outlier-dependence stats.

## Design decisions (course corrections from the first sketch)

1. **One underlying feed, not five.** Download 1m bars only; derive 5m / 15m /
   1H / 1D by resampling. One quota spend, zero cross-feed misalignment.
2. **No bulk option crawl.** 200 tickers × 9.5 years × 15m option bars would
   dwarf everything else in quota/disk and mostly never be read. Signals are
   generated from underlying data first; option bars are fetched on demand for
   proposed trades only (v2's hybrid provider, scaled up).
3. **Objective = trade-quality classification/ranking, not PnL regression.**
   Evaluation is portfolio-level, out-of-fold, with costs, judged on
   median-fold and PnL-ex-outliers.

## Data

| Item | Spec |
|---|---|
| Window | 2017-01-20 → present (Trump 1st inauguration) |
| Universe | 200+ names, **point-in-time** liquidity selection as of 2017, annual reconstitution; include delisted names if data permits |
| Underlying | 1m bars (Alpaca SIP reaches ~2016) → resample stack 5m/15m/1H/1D |
| Options | 15m bars, on-demand per proposal via Massive; cache forever |
| Storage | Parquet partitioned by symbol/year (underlying) and symbol/month (option bars). Hard rule: no directories with 100k+ tiny files (the v2 cache transfer lesson) |
| Est. size | ~200M rows 1m underlying (few GB compressed); option cache grows with proposal count, not universe × years |

**Data audit is Stage 0 and gates the window choice.** Unknowns to resolve
empirically before anything else is built:
- Massive option-bar history depth by year and liquidity tier (sample a few
  contracts per year for SPY, a mid-cap, and a high-IV name; record coverage).
- Alpaca 1m depth/quality for illiquid and delisted names.
- If 2017 coverage is thin for options, fall back window (e.g. 2019/2020→) is
  decided here, not discovered mid-build.

## Indicator library

- TradingView can't be pulled programmatically (Pine is closed), but the
  popular "modern" indicators have public Pine source. Port a curated set
  in-house, vectorized (numpy/numba): Squeeze Momentum, SuperTrend, anchored
  VWAP, Keltner squeeze, ADX regime filter, Ichimoku, OBV/volume profile
  features, RSI/MACD divergences — final list decided during Stage 2.
- **Correctness harness**: each indicator unit-tested against TradingView's
  plotted values on a pinned SPY window (export TV values once, freeze as
  test fixtures). No indicator enters the feature set without passing.
- All features computed strictly from past bars (same leak discipline as v2).

## Build order (each stage gates the next)

0. **Data audit** — availability/depth script + written findings. Decides the
   window and any universe trims. ~days, cheap, kills bad assumptions early.
1. **Universe selection** — point-in-time constituent list with annual
   reconstitution rules, committed as data (not code).
2. **Underlying layer** — 1m crawl → resample stack → partitioned parquet with
   checksums. Boring, done once.
3. **Indicator library + TV validation harness** (the "SPY mini-tests").
4. **SPY end-to-end pilot** — full pipeline on one symbol: signals → proposals
   → on-demand fills → labels → GBT + small NN → mini walk-forward.
   Validates plumbing and label economics. **No tuning decisions here.**
5. **Diverse-basket calibration (~10 names)** — index ETF, mega-caps, high-IV
   retail, rate-sensitive. This is where design decisions get made; SPY alone
   lies about generalization.
6. **Full-universe dataset build** — parallelized per-symbol (v2's loop is
   sequential; parallelizing it is the #1 code change), run on a rented
   many-core **spot** VM. Checkpointing makes preemption a non-event.
7. **Model bake-off** — LightGBM baseline first (fast, feature importances
   rank the new indicators), NN ensemble second, sequence model (temporal CNN /
   small transformer on raw multi-timeframe bars) only if tabular models
   plateau. Winner = best out-of-fold portfolio metrics, not val loss.
8. **Walk-forward + regime report** — purged/embargoed folds, AND per-regime
   slices: 2018 volmageddon, 2020 crash, 2021 meme mania, 2022 bear,
   2023-25 recovery. "Only works post-2021" is a finding, not a failure.

## Compute

- **Dataset build (the real cost): CPU, not accelerators.** Many-core spot VM
  (32–64 cores); per-symbol parallelism scales linearly. The v2 box
  (i5-11400F, 6C/12T, 16GB, Pop!_OS) stays useful for pilots and reruns —
  shard counts are auto-sized from free memory by `scripts/lib/autosize.sh`.
- **Training**: GBT and the small MLP train in minutes on CPU. A single rented
  consumer GPU (RunPod/Lambda/vast, ~$0.30–0.80/hr) only if Stage 7 goes
  sequence-model. **No TPUs** — a tabular MLP leaves them >99% idle; they earn
  their keep only for large matmul-bound models, which this is not.

## Risk register

| Risk | Mitigation |
|---|---|
| Massive option history doesn't reach 2017 | Stage 0 audit; fallback window decided up front |
| Survivorship bias in universe | Point-in-time selection; include delisted names |
| 1m data quality on illiquid names | Stage 0 audit; per-symbol quality gates before inclusion |
| Overfitting via indicator proliferation | GBT feature importances prune; indicators must survive the diverse basket, not just SPY |
| Quota/cost blowout on option fetches | On-demand only; cache is append-only and permanent; monitor spend per 1k proposals during pilot |
| Big-run fragility | v2.2 checkpoint pattern everywhere; spot-safe by construction |

## Open questions (decide during Stages 0–4)

- Signal base: keep v2's 4-strategy pool, or expand with the new indicators as
  entry generators (not just features)?
- Label horizon(s): v2's DTE grid, or add multi-horizon labels?
- Universe reconstitution cadence: annual vs quarterly.
- Does 1m granularity earn its cost vs 5m for signal generation (options fills
  stay 15m either way)?
