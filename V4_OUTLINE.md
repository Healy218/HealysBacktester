# v4 Outline — Causal Validation and Research Reproducibility

Status: Stage 0 empirical results are in (2026-07-21 night, see below) —
v4's causal fixes (`prem_spot` removed, purged nested selection) confirmed
real: the corrected ablation is still solidly positive (not zeroed out by
the leakage fix), and the nested 3-fold walk-forward's winners are
broadly-diversified across symbols/strategies rather than outlier-dependent
the way the uncorrected v3.1 walk-forward was. A deployable candidate
(`model_final_v4/`, GBT/filter/thr=0.5, 40-seed ensemble) is trained and
persisted — Option A of the finalize plan. Option B (route evaluation
through the stage-2 mark-to-market ledger before trusting this further) is
scoped below and not yet started. Created from commit `5474335` on
2026-07-20; causal-validation infrastructure was added on
`codex/v4-causal-validation` the same day.

## Purpose

V4 is the next research generation of HealysBacktester. It preserves the v3/v31 proposal, options execution, and FA work while making the evaluation contract causal, reproducible, and directly compatible with the live scorer.

The v31 run may finish under the existing contract. Its outputs are useful for scaling and ablation diagnostics, but they are not promoted as final evidence until the gates below pass.

## Constraints

- Options history is approximately two years.
- Options bars are 15-minute aggregates.
- Underlying history is materially longer and may support longer feature windows.
- The present-day symbol universe is survivorship-biased until a point-in-time constituent source is available.
- V4 must not assume that historical option quotes, spreads, or delisted contracts can be reconstructed more precisely than the provider supports.

## Non-negotiable research rules

1. Every feature has an explicit `available_at` timestamp and must be available before the decision timestamp.
2. Initial option entries occur after the signal bar; exits use a separately specified actionable bar.
3. Splits are purged by both entry and exit timestamps, with an explicit embargo.
4. Model architecture, feature set, thresholds, DTE policy, and portfolio policy are selected inside temporal training folds.
5. Open positions are marked to market; returns, drawdown, exposure, turnover, and capacity are reported at portfolio level.
6. NN, GBT, baseline, and buy-and-hold comparisons use the same universe, folds, slots, costs, and exposure convention.
7. Every dataset, model, report, and cache is tied to a manifest containing code revision, config hash, feature schema, universe, coverage, and provider metadata.

## Stages

### 0. V31 reconciliation — DONE 2026-07-21 night

Ran on the Windows/WSL box against the real 118-symbol `meta_dataset.parquet`
(committed to `main` at `65c635c`, pulled via `codex/v4-causal-validation`).

**Ablation** (4 treatments, static window) — distinguishes schema leakage
from split leakage:

| schema | purged | test return | maxDD |
|---|---|---|---|
| legacy (`prem_spot`) | no | +136.6% | 15.0% |
| v4 (no `prem_spot`) | no | +45.2% | 25.5% |
| legacy | yes | +90.9% | 27.2% |
| v4 (fully corrected) | yes | **+72.6%** | 24.4% |

Removing `prem_spot` alone roughly halves the return (136.6%→45.2%) —
confirms it was genuinely leaking. The fully-corrected row is still solidly
positive: real signal survives, smaller than the leakage made it look, which
is the desired outcome (pipeline bug ruled out, strategy validity partially
confirmed).

**Nested 3-fold walk-forward** (v4 schema, purged, per-fold independent
family/mode/threshold selection — no single reused config):

| fold | winner | return | ex-top3 | % retained | maxDD |
|---|---|---|---|---|---|
| 1 | nn/filter/0.55 | +754.6% | +340.7% | 45% | 25.5% |
| 2 | gbt/filter/0.50 | +354.3% | +287.3% | **81%** | 48.7% |
| 3 | nn/rank/0.50 | +117.4% | +36.9% | 31% | 25.0% |

Trade-level dig (retrained + reproduced exactly, matched official numbers to
4 decimals) on all three folds' top trades: no repeat symbols within any
fold's top 5–8, no leveraged ETFs, max single-trade return +754% (fold 1) vs.
v3.1's uncorrected walk-forward where fold 2's +1136% was ~98% one 31x
overnight TQQQ trade (ex-top3 collapsed to +18%, 1.6% retained). v4's
worst-case retention (fold 3, 31%) is still far more broadly-based than
v3.1 ever showed. **This stage distinguished pipeline success from strategy
validity as intended: not a bug, and not just leakage — a real, smaller,
more broadly-distributed edge.**

### 1. Causal feature and split contract

Implement shared utilities for:

- Feature availability assertions.
- Exit-time purging and embargoes.
- Fold-local scaling and feature selection.
- Nested temporal model/threshold selection.
- Regression tests that construct deliberately leaking rows and fail if they cross a split.

Current implementation:

- [x] `nn_meta/feature_contract.py` records feature availability; the v4
  schema (`V4_META_FEATURES`) deliberately excludes `prem_spot` while the
  legacy schema remains intact for existing v3/v31 artifacts.
- [x] `nn_meta/temporal_validation.py` assigns splits using both `entry_ts`
  and `exit_ts`, purges cross-boundary labels, applies an explicit embargo,
  and records a split audit table.
- [x] `nn_meta/v4_evaluate.py` makes architecture/model-family, evaluation
  mode, and threshold selections inside each temporal fold. It can run both a
  corrected expanding-fold evaluation and a four-way legacy/v4 × unpurged/purged
  ablation against a completed v31 dataset.
- [x] Regression tests cover the feature-time contract, cross-boundary
  labels, embargo behavior, fold ordering, and shared policy selection.
- [ ] Refit the selected fold-local model on train+validation before its OOS
  test, if we choose that convention; the current conservative runner keeps
  validation separate through testing.
- [x] `nn_meta/v4_finalize.py` (Option A, 2026-07-21 night): the 3-fold
  walk-forward's nested selection means each fold independently picks its
  own winning family/mode/threshold (see stage 0 results — folds 1/2/3
  didn't agree), so there's no single "the config" to just retrain. This
  script runs one more nested-selection pass on the full dataset (all data
  as train, a validation tail for early-stopping/threshold choice, no
  held-out test — this pass exists to pick+train the deployable config, not
  measure OOS performance) and persists a `config.SEEDS`-size ensemble of
  the winner to `model_final_v4/`. Still uses the stage-2-pending shared
  portfolio simulator, not the mark-to-market ledger — see Option B below.

### 2. Execution and accounting

Define one evaluation contract for:

- Signal timestamp.
- Option contract selection timestamp.
- Entry fill timestamp and price.
- Exit signal timestamp.
- Exit fill timestamp and price.
- Roll behavior.
- Missing bars and fill failures.
- Mark-to-market option valuation.
- Conservative cost and spread scenarios.

Current implementation:

- [x] `nn_meta/v4_accounting.py` defines a fail-closed execution schema,
  explicit per-side cost scenarios, and an event-level cash/position ledger.
  True V4 reports require observed entry and exit contract marks and use any
  observed interim marks; the ledger never manufactures a mark from a final
  trade return.
- [x] The execution engine now retains gross return plus actual entry/exit fill
  timestamps, and future meta-datasets retain those execution-provenance
  fields.
- [ ] Persist the per-contract 15-minute mark stream (including roll fills)
  alongside future V4 labels, then route the v4 evaluator through this ledger.
- [ ] Specify fill-failure reason codes and conservative behavior for missing
  option bars/spreads before producing a live-readiness report.

**Option B plan (scoped 2026-07-21 night, not started)** — `v4_accounting.py`
was built the same night as `v4_evaluate.py`/`v4_finalize.py` but is not
imported by either; every stage-0 result and `model_final_v4` above still
went through the same shared `select_meta.py` portfolio simulator v3.1 used
(the one a single TQQQ trade could dominate — stage 0's trade-level digs
suggest v4's config isn't fragile to that in the same way, but it hasn't
been re-checked through the stricter ledger). Sequencing:

1. Wire `v4_accounting.py`'s event-level ledger into `evaluate_window()`
   (`nn_meta/v4_evaluate.py`) in place of `select_meta.portfolio_metrics`/
   `_portfolio_sim`, so fold/policy selection itself uses mark-to-market
   accounting, not just the final reported number.
2. Re-run the ablation (`--ablation`) and nested walk-forward (`--folds 3`)
   through the new ledger. Numbers are expected to move — that's the point;
   compare against the stage-0 table above rather than assuming it repeats.
3. Only after that: re-run `v4_finalize.py` for a new `model_final_v4/`,
   since Option A's persisted ensemble was selected and trained under the
   old simulator.
4. Then, and only then, stage 5's live candidate-batch constructor — no
   point building live parity against a model likely to be superseded.

### 3. Baseline bake-off

Evaluate GBT, NN, mechanical baseline, and underlying basket using identical portfolio construction. Prefer the simplest model that survives the same corrected out-of-fold gates.

Current implementation:

- [x] The v4 runner evaluates NN and LightGBM through the existing shared
  slot-portfolio evaluator, with the same frozen baseline, policy candidates,
  threshold set, and drawdown gate. A candidate must exceed its validation
  baseline to be eligible.
- [ ] Replace/extend that shared evaluator with the stage-2 mark-to-market,
  cost, and capacity accounting contract before treating outputs as live-ready.

### 4. Reproducible artifacts

Add:

- Locked dependencies and CI.
- Artifact manifests and fail-closed cache validation.
- Portable launchers and preflight checks.
- Coverage and entitlement reports.
- A small metadata bundle that can be transferred independently of multi-gigabyte raw data.

Current implementation:

- [x] `nn_meta/v4_artifacts.py` creates and validates fail-closed manifests
  containing file hashes, code revision, config hash, coverage, feature
  provenance, and provider metadata. The v4 evaluator writes one beside each
  report and can create a small transfer-ready metadata ZIP.
- [x] The manifest regression tests prove that changed dataset/spec inputs and
  changed ordered feature schemas are rejected.
- [ ] Add a pinned, platform-tested lockfile and CI matrix. `requirements.txt`
  is version-pinned for the most brittle core packages, but it is not yet a
  fully reproducible lockfile.
- [x] `python -m nn_meta.v4_preflight --require-gbt` is a remote-safe
  preflight command for the actual v31 runtime. It validates local files,
  causal schema, baseline spec, and LightGBM availability before the ablation.
  Provider entitlement and cache coverage remain run-specific operational
  checks because this machine cannot inspect the separate remote environment.

### 5. Live parity

Make the deployed scanner consume the same candidate batch and policy as the backtest:

- Same strategy and DTE competition.
- Same available-at feature construction.
- Fresh data/cache controls.
- Atomic alert state and acknowledged notification outbox.
- Paper-trade ledger and drift/health metrics.

Current implementation:

- [x] `nn_meta.live.v4_parity.assert_feature_parity` makes the feature gate
  executable: it rejects post-decision fields, missing columns, row-count
  differences, and numerical mismatches (while handling matching NaNs).
- [ ] Build the v4 live candidate-batch constructor, run it against archived
  closed bars, and use this comparator against the matching offline row.
  The current deployed scorer intentionally remains the legacy v3/v31 scorer
  and still depends on `prem_spot`; it must not be relabeled as v4 parity.
- [ ] Add atomic alert/outbox state, paper-trade ledger, and drift metrics.

### 6. FA-to-universe loop

After the corrected trading evaluation is stable:

- Preserve raw social/news/filing snapshots.
- Complete entity resolution and alias fixtures.
- Add source-normalized attention velocity and corroboration rules.
- Freeze monthly rankings.
- Track forward returns.
- Graduate names into future universes only using their historical ranking date.

Current implementation:

- [x] `fa/universe_loop.py` ranks only score rows observed by the ranking
  timestamp, requires independent-source corroboration, freezes a dated JSON
  ranking without overwrite, and allows graduation only after a point-in-time
  probation/forward-return check.
- [ ] Feed the existing raw collectors and entity-resolution fixtures into
  the normalized score table, then begin accumulating enough dated rankings
  to evaluate the discovery signal. Historic social/filing snapshots cannot
  be reconstructed retroactively.

## First implementation gate

V4 is not considered validated until:

- [x] `prem_spot` is removed or replaced with a truly pre-decision value.
- [x] Exit-time purging and embargoes are tested.
- [x] Walk-forward selection is nested.
- [x] GBT and NN are compared with the same costed portfolio simulator.
  (Same shared simulator as v3.1 — Option B above upgrades this to the
  mark-to-market ledger; that's a strengthening, not a redo of this item.)
- [ ] The live scorer passes an offline/online feature-parity test.

4/5 as of 2026-07-21 night. The remaining gate item is the reason
`model_final_v4/` (Option A) is a validated *candidate*, not a live
deployment — do not swap the scanner over to it until stage 5 closes this
out and Option B has been through at least one re-finalize pass.

## First remote v31 run — DONE 2026-07-21 night (results in stage 0 above)

All four commands below were run on the Windows/WSL box in sequence
(smoke test on a 10-symbol/~1y subset first, per `V4_SMOKE_TEST.md`, then
the real thing against the full 118-symbol dataset). Total wall time for
the ablation + nested walk-forward: ~17 minutes. `v4_finalize.py` (Option A,
not part of the original plan when this section was first written) then
trained + persisted `model_final_v4/` in another ~4.5 minutes.

```bash
NN_META_POOL=v31 ./venv/bin/python -m nn_meta.v4_evaluate --ablation --smoke
NN_META_POOL=v31 ./venv/bin/python -m nn_meta.v4_preflight --require-gbt
NN_META_POOL=v31 ./venv/bin/python -m nn_meta.v4_evaluate --ablation \
  --seeds 0,1,2,3,4 --epochs 60 --gbt-estimators 600 --embargo 1D
NN_META_POOL=v31 ./venv/bin/python -m nn_meta.v4_evaluate \
  --folds 3 --seeds 0,1,2,3,4 --epochs 60 --gbt-estimators 600 --embargo 1D
NN_META_POOL=v31 ./venv/bin/python -m nn_meta.v4_finalize \
  --select-seeds 0,1,2,3,4 --final-seeds 0,1,...,39 \
  --epochs 60 --gbt-estimators 600 --embargo 1D
```

The ablation writes `v4_ablation_report.md` and JSON beside the configured
reports directory; the expanding-fold run writes `v4_walkforward_report.md`
and JSON. The four ablation treatments distinguish schema leakage
(`prem_spot`) from split leakage (entry-only assignment) without re-downloading
raw options data. LightGBM must be installed in the remote environment for
the GBT comparison; the local tests intentionally do not require it — it was
missing on the Windows/WSL box and had to be installed before the real run.

## Branch strategy

This outline lives on `codex/v4-causal-validation`. Keep `main` as the v3/v31 operational line until v4 passes the gates. Do not copy the entire project into a second repository; refactor shared providers and execution contracts incrementally.
