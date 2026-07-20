# v4 Outline — Causal Validation and Research Reproducibility

Status: initial outline, created from commit `5474335` on 2026-07-20.

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

### 3. Baseline bake-off

Evaluate GBT, NN, mechanical baseline, and underlying basket using identical portfolio construction. Prefer the simplest model that survives the same corrected out-of-fold gates.

### 4. Reproducible artifacts

Add:

- Locked dependencies and CI.
- Artifact manifests and fail-closed cache validation.
- Portable launchers and preflight checks.
- Coverage and entitlement reports.
- A small metadata bundle that can be transferred independently of multi-gigabyte raw data.

### 5. Live parity

Make the deployed scanner consume the same candidate batch and policy as the backtest:

- Same strategy and DTE competition.
- Same available-at feature construction.
- Fresh data/cache controls.
- Atomic alert state and acknowledged notification outbox.
- Paper-trade ledger and drift/health metrics.

### 6. FA-to-universe loop

After the corrected trading evaluation is stable:

- Preserve raw social/news/filing snapshots.
- Complete entity resolution and alias fixtures.
- Add source-normalized attention velocity and corroboration rules.
- Freeze monthly rankings.
- Track forward returns.
- Graduate names into future universes only using their historical ranking date.

## First implementation gate

V4 is not considered validated until:

- `prem_spot` is removed or replaced with a truly pre-decision value.
- Exit-time purging and embargoes are tested.
- Walk-forward selection is nested.
- GBT and NN are compared with the same costed portfolio simulator.
- The live scorer passes an offline/online feature-parity test.

## Branch strategy

This outline lives on `codex/v4-causal-validation`. Keep `main` as the v3/v31 operational line until v4 passes the gates. Do not copy the entire project into a second repository; refactor shared providers and execution contracts incrementally.
