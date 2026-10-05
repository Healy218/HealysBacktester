# Handoff — October 5, 2026 — Action replay / freeze gap

## Focus and completed result

User asked how close ETFE is to freeze/train and to keep going. Feature assembly
is implemented, but input admission/full coverage, execution/labels, integrated
pilot and full dataset build remain. Completed **ETFE.provider-action-replay**
within four-day transport scope, without closing action timing or training gates.
[Review / critical path](docs/reviews/2026-10-05-etfe-action-replay.md),
[machine receipt](docs/reviews/2026-10-05-etfe-action-replay.json).

- Four fixed UTC days reached EOF in selected r1. March 14, 2024 / March 20,
  2025 / March 19, 2026 returned welcome-only responses; retention stays unknown.
- September 17, 2026: 41,730 unique events, 45,559 occurrences, 3,829 exact overlaps.
- Five SPY mutations match its September 18 dividend. First provider insert at
  September 17 21:59:24.391802 UTC, rate 1.888834, before ex-date.
- One of 35 fresh action records has a matching pre-effective witness. Original
  announcement and complete latest-as-of revision history remain unverified.
- R0 rejected provider events before a submillisecond continuation cursor.
  Preserve its source/partial data/REJECTION. R1 rounds continuation down to the
  whole second and keeps strict request bounds, all overlaps and raw fragments.
- Independent line-oriented event/witness audit and actual twelve-file resume
  pass. All 210 focused ETFE tests pass. Existing predecessors still verify.
- Selected capture 13 GETs / 15.63s / 20,043,029 bytes; 20 GETs including r0.

## Evidence boundary and stopping point

Transport EOF is not a retention or no-action certificate. One timing witness
cannot admit all action-adjusted historical inputs. No new feature arrays,
market-price dates, labels, training or deployment. Model admission stays false.
No replay process remains running. Usable history remains null.

## Next work

1. **ETFE-3.execution-components:** implement the bounded VWAP ledger supporting
   ETFE-4.pilot: funded integer entry, shared participation, partial sells/latched
   stop, settlement and explicit unresolved/boundary outcomes. Synthetic dated
   fixtures can test mechanics; real path admission still needs real evidence.
2. **ETFE.provider-action-timing / provider-contract:** retain unresolved action
   revision/retention and option terms/sector/session/trade-source facts. Do not
   repeat the same empty controls or broaden replay without a measured plan.
3. **ETFE-1.demand / ETFE-4.pilot:** full phase-B/C acquisition demand and budgets,
   then integrated capture/features/execution/dataset/training smoke and recovery.
   Full build and independently verified dataset freeze must precede training.

## Artifacts and constraints

Selected: `nn_meta/data_cache_etfe/alpaca-fresh-action-replay-20261005-r1/`.
Plan: `50655f2359307cf90f5f087d66021fac139ba774724578e90ab20825dbdc65e2`.
PLAN/COMPLETE, day pages, ETF_MUTATIONS/RECONCILED, independent/resume receipts.
Original rejected r0 retained alongside. Evidence ZIP: 68 metadata/source/audit
members and 20 raw payload hashes. Joined diagnostic and other inputs unchanged.
[State](docs/CURRENT_STATE.md#october-4-etfe-fresh-alpaca-setup),
[commands](docs/reference/ETFE_SETUP.md#bounded-historical-action-replay),
[successor contract](docs/specs/ETFE_ACTION_REPLAY_V2_20261005.md).

Source-bound consumers remain immutable; use successors for behavioral changes.
Preserve unrelated dirty work, including DECISIONS/EXPERIMENTS additions.
[Previous handoff](handoff-history/HANDOFF-2026-10-05-before-action-replay.md).
