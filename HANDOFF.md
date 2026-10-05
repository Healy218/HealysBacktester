# Handoff — October 5, 2026 — Measured frontier and March discovery

## Focus and completed result

User asked to keep going. Completed **ETFE-1.demand-frontier** within measured
acquisition-envelope and bounded discovery scope. Full **ETFE-1.demand**, input
admission and freeze/train remain open. [Review](docs/reviews/2026-10-05-etfe-demand-frontier.md),
[machine receipt](docs/reviews/2026-10-05-etfe-demand-frontier.json).

- New frontier verifies all selected fresh page chains, measures payloads by
  route, and counts returned symbols / unknown queries across 2,073 ticker-days.
- March 5–25 civil expiries: 126 successful GETs, 8,462 new discovery records,
  126 normalized partitions. Both statuses, all three ETFs, both rights/strikes.
  Ninety-five empty queries remain unknown historical coverage. One sandbox
  transport failure is separate; successful live capture took 125.14 seconds.
- Discovery now completes 558 / 6,300 calendar queries; 5,742 remain. Six
  January 1 padding queries are outside that denominator. 38,126 symbols known.
- Gross known-symbol envelope: 963,898 symbol/session edges, 156,122 at 0–5 DTE,
  9,888 grouped requests before reuse/pagination. This is not exact causal demand.
- Phase-C requirements explicitly include roll-retry quotes, official exercise
  references, dated deliverables, settlement calendars and sized stock quotes.
  Full phase-B/C request/storage budgets remain null, pending actual inputs.
- Both frontier inventories independently reconcile; all raw-to-normalized
  occurrences pass. Separate-process restart made zero GETs, preserving 510 files.
  All 294 focused ETFE tests pass, including five new frontier/budget tests.

## Evidence boundary and stopping point

Selected normalized data: 1,375 partitions / 1,964,142 rows. Discovery records
are not historical eligibility or option market observations. Usable history,
dated terms/actions and all real-feature admission remain unresolved. Original
January market coverage and synthetic scheduler evidence are unchanged.
No process remains running. No training, orders or deployment occurred.

## Next selected work

1. Continue **ETFE-1.demand**: selected r1 lists the next 126 missing discovery
   queries. Measure missing quote/exercise sources and derive exact full-window
   signal/feature/trade and holding/roll/physical-stock demand. Reconcile full
   resource budgets before bulk acquisition; envelopes do not close this gate.
2. **ETFE.provider-contract / provider-action-timing / history-boundary**:
   establish dated eligibility, terms/hours/actions and scoped usable coverage.
   Do not repeat empty action controls without a budgeted new question.
3. **ETFE-4.pilot**: real capture/features/execution/isolated-label/dataset/training
   smoke and recovery, then full build and independent freeze before training.

## Artifacts and constraints

Frontier: `nn_meta/validation/etfe-demand-frontier-20261005-r1/` (r0 preserved).
Raw: `nn_meta/data_cache_etfe/alpaca-fresh-20261005-discovery-r0/`.
Typed: `nn_meta/data_cache_etfe/normalized-20261005-discovery-r0/`.
[State](docs/CURRENT_STATE.md#october-4-etfe-fresh-alpaca-setup),
[commands](docs/reference/ETFE_SETUP.md#measured-demand-frontier-and-bounded-discovery),
[contract](docs/specs/ETFE_DEMAND_FRONTIER_20261005.md).
Evidence ZIP preserves metadata/source snapshots and hashes all 793 local files.
The finite capture caps attempts at 128/run, 256/study, with durable reservations
before networking, 512 MiB/root and existing reserve guards. No automatic loop.
Fresh Alpaca only, actual 0–5 DTE entries/rolls. Bound sources stay immutable;
use successors. Preserve unrelated dirty work, including DECISIONS/EXPERIMENTS.
[Previous handoff](handoff-history/HANDOFF-2026-10-05-before-demand-frontier.md).
