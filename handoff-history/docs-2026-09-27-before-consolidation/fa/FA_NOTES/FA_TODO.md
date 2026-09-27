# FA TODO — current work queue

This queue is independent of the active V7 checklist. Work may proceed while
V7-2 compiles, subject to the resource boundary in `FA_ROADMAP.md`.

## FA-0: baseline and contract

- [ ] Write the FA data contract: event grain, context-bar grain, timestamps,
  availability, timezone, identity, retention and versioning.
- [ ] Inventory current raw archives, feature snapshots, ranking artifacts,
  labels and evaluation receipts.
- [ ] Profile row counts, date ranges, duplicates, nulls, source mix, ticker
  resolution and join coverage by source and month.
- [ ] Identify the exact cause and evidence behind
  `insufficient-purged-history`.
- [ ] Freeze a dated baseline report without rewriting August 2026 artifacts.

## FA-1: durable collection and PIT archives

- [ ] Add immutable manifests, hashes and provider-failure receipts to each
  collector output.
- [ ] Verify idempotent event keys and restart-safe monthly partition writes.
- [ ] Separate provider publication time, capture time and model availability
  time everywhere.
- [ ] Version the alias/entity map and add reviewed effective-date handling.
- [ ] Add automated freshness, duplicate, schema and partition-completeness
  checks.
- [ ] Establish bounded collection cadence and storage/resource budgets.

## FA-2: causal context bars

- [ ] Define the canonical per-security 5/15/30-minute and daily bar schemas.
- [ ] Implement as-of joins with explicit source age and decay fields.
- [ ] Add attention velocity and sentiment features with source-specific
  normalization.
- [ ] Add news and EDGAR/filing features using availability time, not only
  filing date.
- [ ] Complete the fundamental overlay scaffold where data quality supports it.
- [ ] Add options-flow and liquidity/crowding context from existing project
  data without duplicating V7 acquisition.
- [ ] Add causal-prefix, batch/incremental-equivalence and grain tests.

## FA-3: labels and evaluation

- [ ] Define forward return, excess return, direction, volatility and/or event
  impact labels with named horizons.
- [ ] Build chronological folds with purging and embargo.
- [ ] Track effective sample size, label balance and missing-label reasons.
- [ ] Add source and feature-family ablations against price/options baselines.
- [ ] Accumulate and freeze three clean prospective monthly cohorts.
- [ ] Replace the current exploratory evaluation with an inspectable quality
  and evaluation report.

## FA-4: first model

- [ ] Train source-only and simple regularized baselines.
- [ ] Train a first tree/boosted model only after the baselines and joins pass.
- [ ] Calibrate predictions and test symbol, regime, horizon and source
  stability.
- [ ] Measure incremental value after costs and under realistic availability.
- [ ] Freeze accepted candidates with manifests, hashes and inference receipts.

## FA-5/6: future integration

- [ ] Define the versioned FA sidecar/embedding interface for future V7+/V8
  feature builders.
- [ ] Run offline shadow integration against price/options-only baselines.
- [ ] Verify resource use, restart behavior and live/offline parity.
- [ ] Record a promotion or rejection decision before any stacked blend,
  training-universe graduation or live-panel use.
- [ ] Add ongoing drift, freshness, cohort and artifact-retention monitoring.

## Current stop conditions

- Do not call the FA model predictive while evaluation reports
  `insufficient-purged-history`.
- Do not count contaminated August 2026 as a clean prospective cohort.
- Do not use future publication or revised identity information in historical
  features.
- Do not spend the V7 disk reserve or alter V7 contracts for FA experiments.
- Do not connect FA to live alerts or broker state before its gates pass.

