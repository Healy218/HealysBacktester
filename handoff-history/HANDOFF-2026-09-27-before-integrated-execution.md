# Handoff — September 27, 2026 — remaining V7-3 inputs checked against receipts

**Read TODO, then this file.** The user is clearing the session. Continue the
running V7-3 download and finish its actual remaining inputs, then advance to
training. Do not rebuild work completed yesterday or start another broad test
campaign. The user explicitly authorized the needed downloads and MRHA use.

## User correction and receipt check — September 27, 11:31 CDT

The user challenged repeated unfinished-work claims. Read the
[receipt-level verification](docs/reviews/2026-09-27-v7-3-remaining-input-verification.md).
Preparation and execution/physical components are already complete and must be
reused. The current dated-reference stores cover 720 planned pairs (715 valid,
five blackouts); 2,223,124 planned pairs lack receipts in those stores. The older
516 dated receipts add no current entry-plan coverage. The three r12 held-mark
gaps are absent from both the r12 index and 362 completed new entry packs checked.
Entry acquisition continues: 358 new + four reused batches at 16:31:39 UTC.

Earlier wording about remaining exit/roll/stock data was too broad: capture only
exact gaps encountered by existing replay after subtracting retained coverage.
Do not restart completed plans, machinery or pilots. 7-4 integration may proceed
alongside downloads; do not serialize all work behind repeated setup checks.
No producer edits, tests, new downloads or replay campaigns ran in this check.
TODO remains open only for actual unfinished acquisition/integration.

## Previous health check — September 27, 11:26 CDT

The entry service is active with all four workers. Two live meter reads advanced
from 264 to 266 completed batches in this run (plus four reused batches), reaching
8,512 ranges and 696,411,106 retained campaign bytes. Latest receipt at
16:26:49 UTC had no error; status running, stop_reason null. Service memory was
1.4 GiB (1.5 GiB peak), with 266 GiB filesystem space available. No restart or
producer change was needed. This is a point-in-time check, not full coverage.

The user asked for download health and a reminder of 7-4. That stage connects
existing option execution, funded physical handling and shared-capital replay
against real inputs, reconciling entries, stops, exits, rolls, expiry, settlement
and stock liquidation. Full 7-3 still requires the reference and actual path
captures below. No task was newly completed; no tests or campaigns were rerun.

## First actions in the next session

1. Read [current state/downloads](docs/V7_CURRENT_STATE.md) and the live meter
   `nn_meta/validation/v7-entry-campaign-20260927/progress.json`.
2. Check `healys-v7-capture-20260927.service` and its journal before launching
   anything. It was running successfully at this handoff, with completed packs
   and four initial batches reused. No second downloader for the same queue.
3. Let the entry download continue. If stopped, inspect the exact provider,
   capacity or source failure; preserve completed packs and partial receipts.
   The controller/launcher and exact guarded resume are in the
   [launch review](docs/reviews/2026-09-27-v7-entry-campaign-started.md).
4. Work only on TODO's remaining reference and actual execution-path inputs,
   using existing demand plans, replay/physical code and captured packs. Connect
   existing assembly/fold/trial components. Do not call them absent merely
   because an old entrypoint or declaration says pilot/pending.

## Completed — do not restart

V7-1 identity/actions, dividend/settlement/boundary treatments; V7-2 full causal
catalog and daily context; all 591 entry-demand checkpoints; exact request union;
storage reclamation/MRHA archival; joined-range forecast; lossless v2 pack writer
and indexed reader; dated reference demand plan; dated entry-hours reconstruction;
the five exact reference blackouts; first-leg envelope census; actual replay
frontier, capture/resume and its r0–r12 evidence.

The [ROADMAP completed section](ROADMAP.md#completed-work) records results and
links. **It is the completed-work ledger. TODO contains unfinished work only.**
Do not revive older “492 dividend cases,” “catalog building,” “scheduler next,”
“IVV unresolved,” or “packing unimplemented” statements from historical files.

## Current data job and remaining boundary

Service: `healys-v7-capture-20260927.service`.
Controller: `scripts/run_v7_capture_campaign.py`; launcher:
`bash scripts/start_v7_capture_campaign.sh`.
Frozen declaration: `nn_meta/validation/v7-entry-campaign-20260927/declaration/`.
New packs: `nn_meta/data_v7/entry-campaign-20260927/`.
Source demand: `v7-3-scheduler-20260925/demand/`; existing coverage index:
`v7-execution-sample-index-20260927-r12` (validation roots).

This is **entry quote/trade acquisition, not model training**. It does not yet
run full dated-reference acquisition, all held/exit/roll/stock inputs, assembly,
or automatic model fitting. Full V7-3 remains open until that actual coverage
is reconciled. The next session must finish those steps, not mark the entry
service as the entire V7-3 pipeline. Pending actual five-path reads are in
`v7-execution-discovery-20260927-r12/report.json`; new outputs start at r13.

Caps remain 250 GB shared acquisition / 640 GB project / 20 GiB free reserve.
The running job's initial new-data allocation is 100 GB, with a conservative
490 GB project baseline allowance. This is a guard, not a final required-size
estimate. Monitor measured growth and reconcile downstream needs before the
cap pauses dispatch. MRHA has additional usable capacity if needed. Do not
claim the earlier ~1 TB all-possible-holds sensitivity is required storage.

Four autosized workers, one compute thread each; service MemoryHigh 10 GiB,
MemoryMax 14 GiB, MemorySwapMax 0, CPUQuota 400%, Nice 10. Failed captures never
become coverage. Exact completed batches are reusable; remaining gaps stay
explicit. A live run binds its producer hashes: do not edit that producer in
place. Use versioned changes when behavior needs repair.

## Validation and repository handling

Prior broad suite: 2,457 tests + 18 subtests. New controller: two focused tests
pass; real first 128 ranges downloaded, and service resume reused all four
completed packs before continuing. Reuse these results. Check new behavior and
actual launch failures rather than rerunning completed checks by default.

Work on main, commit/push scoped changes. Preserve the large unrelated dirty/
untracked backlog, especially existing assembly.py/dataset_inputs.py. No live
V6/broker changes. Preserve all existing freeze/source/evidence bytes. Strict
legacy source/runtime readers need the existing compatibility proofs; do not
relabel frozen stores. The current V7-2 gate uses `gate.json`, not `report.json`.

## Documentation precedence and history

Current instructions: TODO → HANDOFF → docs/V7_CURRENT_STATE.md.
Completed work/future direction: ROADMAP. Durable traps: DOCUMENTATION.
Design specs, old dated reviews, archived TODO/ROADMAP/HANDOFF files are evidence,
not competing live queues. This session archived their pre-reconciliation
versions in `handoff-history/*-2026-09-27-before-live-doc-reconciliation.md`.
Old snapshots can correctly describe an earlier incomplete state; later
completion receipts supersede those status statements without rewriting freezes.

The October 2 Massive recommendation, Alpaca prospective integration and
incubator health/outcome joins remain separate TODO items. They do not authorize
changing existing live policy or reopening abandoned local V6 research.
