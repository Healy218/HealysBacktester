# v4 Outline — Causal Validation and Research Reproducibility

Status: implementation in progress. Created from commit `5474335` on
2026-07-20; causal-validation infrastructure was added on
`codex/v4-causal-validation` the same day. Empirical results remain blocked
until the remote v31 dataset/artifacts are available.

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

### 0. V31 reconciliation

Use the completed remote v31 artifacts to run:

- Existing v31 configuration.
- Existing data with `prem_spot` removed.
- Existing data with exit-time purging.
- Existing data with both corrections.
- Corrected LightGBM baseline.
- Corrected NN ensemble.

This stage should distinguish pipeline success from strategy validity without requiring a fresh raw-data download.

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

- `prem_spot` is removed or replaced with a truly pre-decision value.
- Exit-time purging and embargoes are tested.
- Walk-forward selection is nested.
- GBT and NN are compared with the same costed portfolio simulator.
- The live scorer passes an offline/online feature-parity test.

## First remote v31 run

Once v31 training has completed and its `meta_dataset.parquet` plus baseline
specification are copied or made accessible to this branch's environment, run
the following from the project root (start with the smoke run to confirm the
remote dependencies):

```bash
NN_META_POOL=v31 ./venv/bin/python -m nn_meta.v4_evaluate --ablation --smoke
NN_META_POOL=v31 ./venv/bin/python -m nn_meta.v4_preflight --require-gbt
NN_META_POOL=v31 ./venv/bin/python -m nn_meta.v4_evaluate --ablation \
  --seeds 0,1,2,3,4 --epochs 60 --gbt-estimators 600 --embargo 1D
NN_META_POOL=v31 ./venv/bin/python -m nn_meta.v4_evaluate \
  --folds 3 --seeds 0,1,2,3,4 --epochs 60 --gbt-estimators 600 --embargo 1D
```

The ablation writes `v4_ablation_report.md` and JSON beside the configured
reports directory; the expanding-fold run writes `v4_walkforward_report.md`
and JSON. The four ablation treatments distinguish schema leakage
(`prem_spot`) from split leakage (entry-only assignment) without re-downloading
raw options data. LightGBM must be installed in the remote environment for
the GBT comparison; the local tests intentionally do not require it.

## Branch strategy

This outline lives on `codex/v4-causal-validation`. Keep `main` as the v3/v31 operational line until v4 passes the gates. Do not copy the entire project into a second repository; refactor shared providers and execution contracts incrementally.
