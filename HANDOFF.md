# Handoff — September 30, 2026 — V6 steps deployed; V7 replay complete

## User direction and result

User requested V6 buy steps 1.05/1.10/1.125 and sell steps 0.95/0.90/0.875,
plus V6 update/V7 run status. Explicitly approved one new ladder each for
exhausted AXP/VG exits. Three-step paper policy deployed at 10:33 Central;
both approved retries filled at step 2. Gate **7-3 remains selected/open**.
[Review](docs/reviews/2026-09-30-v6-step-policy-v4.md),
[deployment/fill/research evidence](docs/reviews/2026-09-30-v6-step-policy-v4.json).

## V6 paper runtime

- Code `4f9c02e`: pricing/bridge v4, slice adapter v2, runtime v5, scanner v7.
  Policy `midpoint-step-5-10-12.5pct-v4`; waits 30/30/60 seconds.
  Follow-up `1bbe651`: source cleanup v3/scanner v8, deployed 10:59.
- Old sell steps were working: QCOM filled; AXP/VG exhausted all four old
  prices. New status receipts explicitly surface exhausted exits.
- At 10:40: AXP ×7 filled $9.75; VG ×104 filled $0.70, both second steps.
  77 broker/journal orders match status/filled quantity; no open orders.
  WFC ×26 remains. Retry IDs persist; do not rearm these again.
- Both timers active, order service healthy. The 10:30/10:45 scans failed
  on missing WFC/VG quotes. Cleanup v3 repairs a newer unfilled VG projection
  wrongly protected by older same-contract fills; 11:00 retired that source.
  The 11:00 scan completed in 256.537 seconds, 308 candidates, zero errors.
- State: `/home/healy/Coding/HealysV6/nn_meta/live/v6_alpaca_paper/`.
  Backups: `runtime-revisions/step-policy-v4-20260930/` and
  `runtime-revisions/scanner-contract-reuse-v3-20260930/` below that state.
  Receipt/scripts: `nn_meta/validation/v6-step-policy-v4-20260930/`.
- Frozen model/source lineage preserved; existing chains retain saved policy.
  Policy checks: 82 passed; follow-up cleanup/integration: 61 passed.
  No live account, stop threshold or model changes.

## Research progress

- V6 continual r3: **325/449 symbols**, 124 remaining deadline/timeout entries
  at the 08:00 market-hours cutoff. Training/freeze have not started.
  Next timer 15:45 Central; retained September 28 catch-up stays pinned.
  Receipt `incubator/continual-v6/r3/latest-run.json`.
- V7 completed **93/93 selected securities**, **21,624,449 horizon-target
  evaluations**, at 08:18 Central; no failures, two continuation passes.
  Supervisor `nn_meta/validation/v7-until-complete-20260929-r0/`.
  Campaign `nn_meta/validation/v7-pending-replay-campaign-20260929-20260929T233047Z/`.
- Per-wave receipts total **129,873 pending requests**, not a deduplicated
  capture-window census. Further actual-input acquisition and original full
  discovery remain. No V7 training started; 7-3/7-4 remain open.
- Preserve completed 109,825-window capture and frozen replay; do not rerun
  without new evidence. Selected inputs/exclusions unchanged (10,835 pairs).

## Storage and next actions

MRHA migration remains active: at 10:39, 182.484/229.378 GB logical moved,
175,649/504,516 files, no error, about 198.7 GiB free locally. Service
`healys-v7-mrha-migration-v2-20260929.service`; state
`nn_meta/validation/v7-mrha-payload-migration-20260929-r1/`.
Keep MRHA UUID 62C9-C390 connected. Working databases/models stay local;
Steam unchanged.

1. Observe scheduled scanner and broker receipts; the 11:00 repair scan passed.
2. Reconcile the new actual requests, then continue selected V7 acquisition/
   discovery without reopening completed evidence or assuming full coverage.
3. Observe V6's after-close resume and migration completion; retain October 2
   provider decision and FA schedules. No new model deployment is authorized.

[CURRENT_STATE](docs/CURRENT_STATE.md) owns exact pointers. Preserve unrelated
working changes, checkpoints and all frozen producer versions.
