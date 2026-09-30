# Handoff — September 29, 2026 — V7 evening recovery running

## Focus and result

User selected steps 3–4 after completed paper reconciliation/V6 restart.
V7 capture resumed; reference review and a new replay pilot passed. Bounded
continuation is running, waiting for capture. Gate **7-3 remains selected/open**.
[Review](docs/reviews/2026-09-29-v7-evening-continuation.md),
[observation/hashes](docs/reviews/2026-09-29-v7-evening-continuation.json).

## Active work and exact pointers

- Capture: `healys-v7-frontier-evening-20260929.service`, started 18:12:24 Central;
  `nn_meta/validation/v7-frontier-capture-20260929-r0/progress.json`.
  At 18:42: 86,424/109,825 windows, no failures in the resumed pass.
- Supervisor: `healys-v7-evening-continuation-20260929.service`, started 18:30:47;
  `nn_meta/validation/v7-evening-continuation-20260929-r0/progress.json`.
  Waits for capture, retries missing batches, binds sealed index, runs pending
  replay and then original discovery if budget remains. Five-hour total budget.
  Read its `selected-replay.json` once published for exact selected outputs.
- New references: `v7-reference-epoch-20260929-r0`; selected admission
  `v7-held-reference-admission-20260929-r1`, under `nn_meta/validation/`.
- User approved four exact missing held-reference exclusions; selected policy
  `v7-contract-blackouts-20260929-held-approved` totals 10,835 pairs.
  Two other missing records recovered via exact dated list responses.
- Frozen pending replay plan: `v7-pending-replay-plan-20260929-r0`:
  93 securities, 251,983 cohorts, 21,624,449 horizon-targets.
- Pilot/parity: `v7-evening-replay-pilot-20260929-r0`,
  `v7-evening-replay-parity-20260929-r0`; all 20 independent comparisons match.
  All pilot outcomes still capture-incomplete. 37 focused tests passed.

## Recovery and constraints

Both interrupted original SQLite databases recovered under locks after preserving
physical preimages/journals. Empty/stale progress files archived; ledgers retained.
New code uses separate immutable epochs. Original bound capture/discovery/V6
producers remain unchanged. Do not edit new bound producers in place either.
User-authorized evening continuation supersedes the earlier daytime-only run
for this bounded invocation. Capture: two autosized workers, max 2 GiB/CPU 100%.
Supervisor/replay: one autosized worker, max 4 GiB/CPU 100%, no swap; reserve guards.
Internal free ~86 GiB; MRHA ~693 GiB. No Steam files or bulk data moved.

## V6 and paper

V6 remains running from 17:31:19 Central, three data workers/two training threads.
At 18:42: 114/449 complete, zero reported errors, training not started.
Calendar cutoff and 12-hour budget unchanged. Read current receipts for later health.
Paper reconciliation remains complete: 48 matching orders, eight fills, four
matching positions, no open orders at 17:30. Observe next-session AXP stop handling;
existing fresh-quote/risk policy governs. No orders submitted by recovery work.
[Paper/V6 evidence](docs/reviews/2026-09-29-paper-reconciliation-v6-resume.md).

## Next actions

1. Observe capture/supervisor terminal receipts, selected index and replay progress;
   inspect actual failures/resources before any retry. Do not restart active jobs.
2. Reconcile new actual requests and reference/provider/storage coverage; no full
   gate closure follows from this pilot or bounded replay.
3. Observe V6 completion and next-session paper risk; preserve October 2 provider
   decision and FA schedules. No training/freeze completion claim yet.

[CURRENT_STATE](docs/CURRENT_STATE.md) owns exact runtime pointers. Preserve all
unrelated dirty work and completed gates. Previous handoff archived before replacement.
