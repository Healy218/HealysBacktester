# Handoff — October 4, 2026 — Calendar demand and January options coverage

## Focus and completed result

Continued fresh Alpaca-only ETFE acquisition. Current v4 scope stays **0–5 DTE**,
including signal-qualified 0DTE; context-only 1–45 DTE remains separate.
No old project data/features/labels/models; no training or deployment.
[Latest review](docs/reviews/2026-10-04-etfe-demand-boundary.md),
[machine receipt](docs/reviews/2026-10-04-etfe-demand-boundary.json).

- Phase-A calendar inventory: 691 sessions, 2,073 ticker-sessions, 190,716 logical
  expiry/status edges factored into 6,300 physical discovery queries. Every civil
  expiry retained, including non-session and post-observation-boundary dates.
- 960 successful new GETs: discovery 378, earlier bars 233, daily bars 349.
  One sandbox failure retained. Every requested page chain completed.
- January discovery plus reused listings yields 23,176 symbols, all returned
  strikes/rights. January 1–17 returns zero bars for all those symbols.
- January 18/19 adds 178,671 bars. First observed is January 18 at 09:30 Eastern
  for all three ETFs. This is an observed boundary, not a verified usable floor.
- All 34,660 surface symbol/day edges reconcile to new/reused requests: 6,865
  observed, 27,795 unresolved absence. Six reused windows add 571 prior bars to
  the two-day census without recapture or double normalization.
- Added 960 normalized partitions / 200,637 rows; independent complete raw-row
  sequence audits passed. Total selected inputs: 1,146 partitions / 1,878,623 rows.
  No implemented quality flags fired. 95 focused tests and v4 setup verification pass.
- 432 of the full inventory's discovery queries now have receipts; 5,868 remain.
  Six extra January 1 padding queries are outside the calendar inventory.

## Stopping point and next work

No ETFE capture or normalization job remains running. Calendar demand and this
bounded January expansion are complete; ETFE-1.demand as a whole remains open.

1. Consume fresh normalized stock inputs in causal session-aligned 1/5/15-minute
   components, then registered signal/feature demand (phase B). Preserve native
   warmup, missingness and all twenty families; no old feature arrays.
2. Expand symbol/session context discovery and coverage under measured budgets;
   derive exact trade/entry demand, then holding/roll/physical-stock paths (C).
   Calendar queries alone are not the complete strategy demand inventory.
3. Resolve scoped usable history, pre-January/longer-expiry coverage, omitted
   historical listings and dated terms/session/provenance at consumer admission.
4. Complete integrated ETFE-4.pilot before bulk acquisition/build/freezes/training
   in ROADMAP order. Earlier stock capture is complete with twelve VOO minute gaps.

## Pointers and exceptional constraints

Current setup unchanged: `nn_meta/validation/etfe-setup-20261004-0dte-r0/`.
Demand: `nn_meta/validation/etfe-demand-20261004-r0/DEMAND.json`; SHA256
`f98a92ce1454e9a05f444f3abf1df93b1cb0da6cd38c0a3cd805d4f327302ee0`.
New raw roots under `nn_meta/data_cache_etfe/`:
`alpaca-fresh-20261004-january-{discovery,boundary,surfaces}-r0/`.
New normalized roots: `normalized-20261004-january-{discovery,boundary,surfaces}-r0/`.
Each normalized root has PLAN/NORMALIZED/INDEPENDENT_AUDIT receipts.
Surface raw root also has EDGE_AUDIT; exact hashes in the current-state index.

The initial one-hour wall budget elapsed during approval waits, and the second
live discovery invocation started after its deadline. This deviation is recorded.
The explicit [successor](docs/specs/ETFE_DEMAND_CONTINUATION_20261004.md) permits
one hour of accumulated active capture time, excluding idle/approval waits;
actual total was 959.3 seconds. Request/storage/invocation caps stayed unchanged.
Original plans/receipts are preserved; do not relabel or silently extend ceilings.

[Current state](docs/CURRENT_STATE.md#october-4-etfe-fresh-alpaca-setup),
[commands](docs/reference/ETFE_SETUP.md). ZIP contains metadata/reports and local
payload hashes, not the raw/Parquet payloads. Preserve unrelated dirty work.
[Previous handoff](handoff-history/HANDOFF-2026-10-04-before-demand-boundary.md).
