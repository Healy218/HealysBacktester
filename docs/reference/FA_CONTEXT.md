# FA technical context

Reference requirements, reconciled September 27, 2026. Priorities and milestone
status belong exclusively to [ROADMAP](../../ROADMAP.md#fa-milestones--research-deferred-collection-continues);
selected actions belong to [TODO](../../TODO.md). This file is not a separate
queue or handoff. Current artifact locations and dated observations belong to
[CURRENT_STATE](../CURRENT_STATE.md#fa-collection-and-evaluation).

## Purpose and existing components

FA collects social attention, news, filings and fundamental/positioning data.
Discovery rankings and forward tracking are existing capabilities. Daily
immutable enrichment snapshots and an experimental purged evaluator also
exist. The broader intended output is causal context for future researchers:
an auxiliary signal, a regime score or an embedding, rather than a price series.
FA evidence is not automatically admitted to V7 or operational trading.

The [original discovery design](../specs/FA_SPEC.md) is historical design
context. Its provider prices, deployment instructions and old stage labels are
not current operational authority. The main roadmap owns the evolved scope.

## Data contract and quality requirements

Declare raw-event and context-bar grain, row identity, timestamp types/timezone,
publication/event time, first capture, model availability, revision semantics,
retention and versioning. Inventory raw archives, snapshots, rankings, prices,
labels and receipts. Profile source/date coverage, duplicates, nulls, ticker
resolution and joins; record missing-label reasons and effective sample size.
Preserve historical artifacts when producing the dated baseline quality report.

Each required capture must support stable event keys, idempotent partition
writes, immutable manifests/hashes and provider-failure receipts. Keep source
and capture time separate. Version aliases and effective dates; do not silently
apply revised identities to earlier observations. Verify restart behavior,
freshness/schema/partition completeness and bounded cadence/resource use.
Existing enrichment manifests and automation satisfy parts of this work;
a full per-source audit is still a distinct deliverable.

## Context bars and features

Use per-security 5/15/30-minute bars, and daily features where justified.
As-of joins must respect availability and include explicit source age/decay.
Attention velocity, sentiment normalization, news/EDGAR filing evidence,
fundamental changes and supported insider/positioning/liquidity features must
retain their source lineage. Reuse existing market data for options-flow
research instead of duplicating V7 acquisition. Optional sources need their
own access and quality evidence before admission.

Required checks include causal-prefix invariance, declared grain, duplicate
handling, join coverage and historical/incremental equivalence. Publication
before a bar is not sufficient if the system first captured the item later.

## Evaluation and promotion

Keep forward-return, excess-return, direction, volatility or event-impact
labels separate from features with named horizons. Use chronological folds,
purging/embargo, effective sample size and source/feature-family ablations on
comparable rows. Current experimental evaluation policy is inspectable through
the report/code pointers in CURRENT_STATE; do not replace it with an old TODO.

Start with source-only rules and regularized/simple tree baselines. Compare
price/options-only, FA-only and combined inputs; assess calibration and symbol,
regime, horizon and source stability, after costs and realistic availability.
Freeze accepted model artifacts, manifests and inference receipts; explicit
rejection is an acceptable research result.

Future sidecars require versioned joins, offline/near-live parity, resource and
restart feasibility, prospective evidence and an explicit promotion decision.
Three clean forward-tracked monthly cohorts are required before graduation
claims. Ongoing drift/freshness monitoring, retention and rollback follow
admission. No stacked blend, live panel or universe graduation precedes its gate.

## Collection is different from evaluation maturity

Raw collection, immutable feature snapshots, completed forward labels and
monthly cohorts measure different things. Calendar days of collection do not
translate one-for-one into eligible trading dates. Future outcomes need time
to mature, and missing price/feature coverage can exclude individual rows.

The September audit found future-captured information in the old August
ranking. That ranking is historical evidence, not a clean forward benchmark;
the finding does not imply that all July/August raw archives were lost or
unusable. Any reuse still requires capture-time and provenance verification.

## Operating boundary

Existing collectors continue independently of research prioritization. Extra
FA work is selected in the main TODO and recorded in the main HANDOFF. Do not
change V7 inputs, launchers, shared contracts or resource allocation for an FA
experiment. Bulk FA acquisition needs an explicit FA budget; a V7 allocation
change is not that budget. Operational locations are in CURRENT_STATE.
