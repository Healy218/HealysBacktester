# Handoff — October 5, 2026 — Fresh action evidence

## Focus and completed result

Continued fresh Alpaca-only ETFE with actual 0–5 DTE including qualifying 0DTE.
Completed **ETFE.provider-actions** within bounded capture/inspection scope.
[Review](docs/reviews/2026-10-05-etfe-action-evidence.md),
[machine receipt](docs/reviews/2026-10-05-etfe-action-evidence.json).

- Fourteen live GETs: twelve REST pages, two finite corporate-action stream probes.
- Captured 35 cash-dividend records; 33 effective inside the fixed price window,
  two earlier records retained explicitly. Original capture had 33 records.
- Found process-date filtering misses September SPY/QQQ actions processed in
  October. A separate October 3–December 31 reference tail recovered both.
- Fixed stock/option price cutoff remains October 2; no later prices requested.
- October stream contains 19,132 complete US mutations before the 8 MiB cap;
  retained 15 ETF updates for two IDs matching tail records. Unparsed tail 292 bytes.
- January 18–19 stream returned only a welcome comment. Both probes HTTP 200;
  neither establishes historical completeness, absence or original publication.
- Independent raw normalization and separate tail/SSE audits pass. Actual
  one-page stop/resume preserved three files. All 196 focused ETFE tests pass.
- Capture elapsed 12.26s; roots 8,470,004 / 83,277 bytes. No training/deployment.

## Evidence boundary and stopping point

Current REST actions contain process/ex/record/payable dates but no verified
historical availability. October update clocks are later than the September
ex-dates; do not backdate them as original announcements. Every normalized
availability remains unknown (-1) and model admission false. No historical
price adjustment was applied. A finite process-date tail is not full coverage.

No ETFE capture remains running. Existing market partitions and joined feature
artifacts are unchanged and still verify. Usable history remains null.

## Next work

1. **ETFE.provider-action-timing:** establish mutation-history retention and
   original/revision availability around required actions. The all-US replay is
   large; use measured volume and a separate bounded plan before expansion.
2. **ETFE.provider-contract / ETFE.history-boundary:** continue dated option
   terms/sector/sessions and trade-source evidence; preserve unresolved coverage.
3. **ETFE-1.demand:** finish full phase-B/C demand and resource budgets, then
   integrated **ETFE-4.pilot** execution/dataset/training smoke and recovery.

## Artifacts and constraints

Selected under `nn_meta/data_cache_etfe/`:
`alpaca-fresh-actions-20261005-r0/` and `alpaca-fresh-actions-tail-20261005-r0/`.
Plans, respectively:
`688be0b5d23f66c02ee437caabc82542a4a206ce905dfb0b0b0a069f8d70680c`,
`daaa5b54f1fa1e5d3a5ebe8dc6ef6a41e6cb51c09e23c53d5ff8225775dbb78d`.
Main ACTIONS/NORMALIZED/independent/resume receipts; tail OBSERVATIONS/INSPECTION/
independent receipts. Evidence ZIP: 54 metadata/source members, 15 payload hashes.
Market census remains 1,249 partitions / 1,955,680 rows; action evidence is separate.
[State](docs/CURRENT_STATE.md#october-4-etfe-fresh-alpaca-setup),
[commands](docs/reference/ETFE_SETUP.md#fresh-corporate-action-evidence).

All source-bound consumers/roots remain immutable; use successors for changes.
Preserve unrelated dirty work, including DECISIONS/EXPERIMENTS additions.
[Previous handoff](handoff-history/HANDOFF-2026-10-05-before-action-evidence.md).
