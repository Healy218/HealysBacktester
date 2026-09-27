# FA Handoff — 2026-09-27 — collection healthy; evaluation awaits history

## Objective

Turn FA from a live exploratory ticker-discovery dataset into a causal,
per-security context-bar and model layer that future strategy versions can join
to price and options bars. The desired outputs are an auxiliary signal, regime
score and/or learned embedding—not a synthetic price series.

## Current state

- Collectors exist for Reddit, StockTwits, news and EDGAR.
- Archive, entity resolution, scoring, ranking and forward tracking exist.
- Operational data lives in `/home/healy/Coding/HealysAutomation`; scheduled
  collection, enrichment and evaluation are healthy as checked September 27.
- Latest 300-symbol snapshot: `fa/artifacts/enrichment/20260927T014037632061Z`.
  Financials cover 232 symbols, float 228, short interest/volume 300 each;
  price-history features cover 120. The full causal overlay is still pending.
- Latest evaluation: `fa/artifacts/enrichment_reports/20260927T020036287757Z.json`,
  960 labeled rows / six days, zero folds, `insufficient-purged-history`. Policy
  requires 40 training days and 10 test days plus purging.
- First clean prospective monthly run is scheduled September 30 at 20:15 Chicago.
  No clean monthly cohort exists yet. The waiting status is expected.
- Read-only audit, existing artifact/hash checks and authenticated account GET
  only; no FA code or runtime changes, no tests or training rerun. Full findings:
  [operational review](../../docs/reviews/2026-09-27-incubator-fa-alpaca-readiness.md).
- FA is exploratory only; it is not admitted to V7 training, live alerts or
  broker state.
- August 2026 ranking evidence is contaminated by the old capture-time path
  and remains historical only.

## First session to execute

1. Audit the current FA artifacts and receipts by source, partition and date.
2. Produce row/column/type, grain, duplicate, missingness, freshness,
   entity-resolution and join-coverage findings.
3. Track growth from the verified six labeled days toward the existing
   40-training/10-test-day policy; do not rerun unchanged history as a repair.
4. Write the FA data contract and baseline quality report.
5. Add only bounded tests or contract repairs that do not compete with the
   running V7 catalog.

## After the baseline

Build immutable PIT archives, then causal context bars with explicit as-of
semantics, age and decay. Define labels and purged folds, accumulate three
clean prospective monthlies, train boring baselines, and require incremental
out-of-sample value over price/options-only features before integration.

## Parallelism decision

Bounded FA documentation/quality work may proceed while V7-3 downloads. Do not
change V7 artifacts, launchers, shared contracts or worker settings. The user
replaced the old reserve with 10 GB local free plus MRHA overflow for V7; that
does not authorize bulk FA acquisition without an explicit FA storage budget.

## Handoff rule

At the end of each FA session, update this file with the exact artifact paths,
quality findings, tests, decisions and next unchecked FA TODO. Do not rewrite
the root `HANDOFF.md`; that file remains the authoritative handoff for the
active V7 sequence.
