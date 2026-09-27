# Handoff — 2026-09-27 — dated hours and execution frontier milestone

Read TODO first. V7-1/V7-2 remain complete; V7-3 remains active. Work on main,
preserve unrelated dirty/untracked work and all source-bound producers. No full
capture campaign or training is running. Previous handoff is archived at
`handoff-history/HANDOFF-2026-09-27-before-dated-hours-execution.md`.

## Completed this session

Review: `docs/reviews/2026-09-27-v7-dated-hours-and-execution-paths.md`.

- Compact source-backed dated hours: 576 roots, all 301,213 frozen entry
  root/dates, 2,370 early-close pairs, 18 dated transition checks. Thirteen
  earlier Nasdaq captures plus sixteen follow-up exchange sources retained.
  IVV contradiction resolved as April 21, 2026 (no selected IVV root).
  Declaration assumes the reviewed baseline/change history is complete for its
  finite scope; it is not a daily historical symbol-directory capture.
- Full first-leg envelope census: all 591 securities, 1,057,177 contracts,
  98,349,826 selected clock/target outcomes after exact blackout entries,
  5,867,251 possible contract/dates. Additional 32.13 million quote hours after
  subtracting original pre-entry quote demand. Potential earlier-held blackout
  crossings for VFC/MSTR/RH/FANG; actual held-path counts still pending.
- Sensitivity only: transferring measured entry quote byte rates to all those
  possible holds adds ~1.03 TB. Not realized demand, a confidence bound, or a
  launch forecast; rolls/stock/metadata/assembly/training are still excluded.
- Real replay frontier adapter, exact uncovered capture/resume, bounded
  ten-minute same-session prefetch, and immutable prefix audit implemented.
  Five original source-bound proposal paths (DIS/ABBV/NVDA/VKTX/FUTU), r0–r12.
  DIS and ABBV completed midpoint-stop labels; others have partial buys/marks
  and next exact held-mark requests. All 60 fill/mark prefix comparisons and
  21 completed-label comparisons pass. No synthetic inputs or reranking.
- Twelve new completed packs total 527,812 bytes. Transport-failure attempts
  remain receipted/charged. Quota: 69,019,919,439 / 250,000,000,000 bytes,
  zero reservations. Internal free ~267 GiB, MRHA free ~693 GiB at last check.
- Full suite: 2,457 passed, 18 subtests passed, one skipped, 20 warnings,
  116.92s. Nine new focused tests. New tests avoid importing the untracked
  assembly fixture. Earlier frozen replay/blackout/packed producers unchanged.

## Artifacts and exact continuation

Under `nn_meta/validation/`:
`v7-dated-hours-20260927`, `v7-dated-hours-audit-20260927`,
`v7-execution-envelopes-20260927` plus 591 sibling `.checkpoints`,
`v7-execution-volume-sensitivity-20260927`,
`v7-execution-discovery-20260927-r0` through `-r12`,
`v7-execution-sample-index-20260927` and `-r1` through `-r12`,
`v7-execution-prefetch-20260927-r3` through `-r12`,
`v7-execution-pilot-audit-20260927`.
Packs are `nn_meta/data_v7/execution-frontier-20260927-r1` through `-r12`.

The pilot is stopped normally at its bounded round limit. To continue, use r12
as the parent and new r13 outputs. `report.json` holds actual pending reads;
`capture-requests.json` subtracts existing coverage. Optional
`scripts/plan_v7_frontier_lookahead.py` creates bounded same-session acquisition
prefetch. `scripts/advance_v7_execution_frontier.py` captures that sealed plan
and publishes a new index. `scripts/discover_v7_execution_paths.py` then reads
the new index with the same hours/blackouts and original cases. These tools
remain bounded pilot tools, not the full-scope production scheduler. Never
classify prefetch coverage as actual demand. Missing reference/stock inputs
need their own real acquisition adapters; new 404s are not automatic blackouts.

Hours scope ends 2026-09-23. Later-expiring contracts fail cutoff lookup until
an explicitly sourced finite extension is supplied; entry-hours completion
does not certify every future cutoff. Frozen producers now include
`dated_hours.py`, `execution_frontier.py`, the compile/envelope/forecast/pilot
scripts and the prefetch/prefix-audit scripts. Preserve source hashes and use
new versions when changing behavior. Do not mutate existing receipts.

## Still required before training

Finish full-scope dated references and realized execution/roll/stock demand,
including held blackout counts. Establish a representative complete-path
forecast and the acquisition/assembly/training/recovery budget. Complete a
resumable packed campaign under reviewed limits. Then physical/shared-capital
execution, full assembly/folds, resource/recovery feasibility and the inspected
final readiness gate. Existing untracked assembly.py/dataset_inputs.py remain
untouched; their packed/physical integration is not certified by this pilot.
Legacy readiness still needs migration to completed 7-1/7-2 and current scope;
stale checks are not a reason to rewrite freezes or revoke passed milestones.

## Preserved decisions and storage context

MRHA use is authorized if necessary. Numerical caps remain 250 GB acquisition,
640 GB total project, and 20 GiB local reserve. The five exact retrospective
contract/date blackouts are unchanged: CMA230630C00041000 2023-06-22,
FANG220520P00130000 2022-05-18, MSTR230630P00320000 2023-06-27,
RH230630P00290000 2023-06-22, and VFC230630C00019000 2023-06-28.
They retain census and partial ledgers without calendar changes or reranking.
Entry impact: 12,970 proposal/target outcomes, 294 selected clock/targets,
192 original requests. All 720 sampled references have treatment: 715 standard
and five blackouts. Full references remain open.

Prior joined/packed forecast: 1,440 sampled captures, 376 securities,
1,168,551 records. Entry+routing mean 142.39 GB; mean+3SE 173.95 GB; with
reference allowance 175.693 GB, leaving little acquisition headroom for paths.
Project stress 613.524 GB local / 648.631 GB including MRHA historical archive,
before execution/assembly/training/recovery. Three SE is not a hard bound.
Cleanup freezes remain unchanged. October 2 subscription decision, Alpaca
bridge and nightly incubator are separate ongoing workstreams.
