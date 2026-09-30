# TODO — Phase 7: V7 data, execution and training

**Current gate: 7-3.** 7-1 and 7-2 are complete. This is the selected phase's
checklist; the [ROADMAP](ROADMAP.md#phase-7--v7-data-execution-and-training)
owns its gates and dependencies. [HANDOFF](HANDOFF.md) gives the session's
stopping point. Use [CURRENT_STATE](docs/CURRENT_STATE.md) for exact inputs and
running-job locations; do not choose a different revision from an old review.

## Active gate 7-3 — required option evidence

Reuse the [verified completed preparation](docs/reviews/2026-09-27-v7-3-remaining-input-verification.md).
The following scope is unchanged by the documentation consolidation.

**September 30 revised direction:** At **15:01 Central**, pause competing local
batch jobs and dedicate compute to **OPS-INCUBATOR.DATA/PROOF**. Until the handover,
V7 continues normally. After a verified V6 candidate freeze/evaluation, restore
paused jobs automatically with maximum supported memory-aware concurrency.
Gate 7-3 remains open with its completed evidence preserved; no recapture of
completed batches. The one-time handover supersedes the 15:45 V6 start and the
previous uninterrupted-V7 instruction for this interval.
[Scheduled handover and completion boundary](docs/reviews/2026-09-30-v6-dedicated-compute.md).

- [x] **7-3.entry:** Full-universe entry quote/trade capture completed September 28
  at 04:58 Central. The final queue count reconciles with prior capture subtraction.
  [Completion evidence](docs/reviews/2026-09-28-overnight-entry-completion.md).
  Preserve completed packs; do not launch another entry campaign.
- [ ] **7-3.references:** Acquire remaining dated references from the completed
  demand plan, reuse captured coverage and apply the approved finite
  contract/date exclusions (including the original five). Actual held paths may add dates; account for new missing references.
  Full-plan capture and independent census completed at 16:48 September 28.
  The 22 rename corrections are wired into discovery. Both exact alternate
  queries failed for all 10,817 missing pairs; the user approved those plus nine
  cash-deliverable exclusions. The compiled finite policy preserves the old five.
  Known entry exceptions are adjudicated; actual held-date coverage remains open.
  September 29: captured/audited 1,985 actual held references (1,979 standard, six
  detail 404s). Evening review admitted two exact list responses; the user approved
  four remaining exact exclusions, preserving prior pairs (10,835 total). New
  reference epoch is sealed; future actual held-date coverage remains open.
  September 30: 573 additional actual held-date pairs captured and independently
  audited, all standard; epoch `v7-reference-epoch-20260930-r0` sealed with
  2,226,402 original responses and unchanged finite exclusions.
  [Evening evidence](docs/reviews/2026-09-29-v7-evening-continuation.md).
  [Recovery, approval and full discovery](docs/reviews/2026-09-28-v7-full-execution-discovery.md).
  [Completion/admission evidence](docs/reviews/2026-09-28-v7-reference-completion.md).
- [ ] **7-3.paths:** Complete only actual held-mark, exit, roll and applicable
  stock-delivery gaps requested by the existing replay frontier. Preserve
  partial ledgers and count held blackout crossings. Potential first-leg
  envelopes are not blanket download orders. Full-universe queue/discovery is
  implemented; 3,535-path cohort parity passed. September 29: planner completed
  all 591 securities. Repaired controller/storage handling and verified empty
  cases; resumed unchanged wave checkpoints and captured a frozen actual frontier.
  September 30 at 08:18 Central: all 93 selected pending-replay securities
  completed, 21,624,449 horizon-target evaluations and no worker failures.
  Per-wave receipts total 129,873 pending input requests; deduplication/capture
  census and further discovery remain. The 109,825-window capture and frozen
  replay queue are complete; neither closes full required-input coverage.
  September 30 11:32: continuous controllers selected for full discovery and
  successive actual capture/reference/replay epochs; no overall cutoff. The next
  sealed pending plan covers 20,729,596 horizon-targets. Do not infer completion
  from a controller launch; inspect exact receipts in CURRENT_STATE.
  [Overnight completion](docs/reviews/2026-09-30-v6-step-policy-v4.md).
  [No-cutoff continuation](docs/reviews/2026-09-29-v7-overnight-resume.md).
  [Recovery census and storage](docs/reviews/2026-09-29-power-surge-recovery.md).
  [Recovery and active services](docs/reviews/2026-09-29-v7-resumed-discovery-and-capture.md).
- [ ] **7-3.reconcile:** Reconcile required requests, captures, references,
  provider failures and measured storage for execution/assembly/recovery.
  Use the already-authorized allocation in the current-state index. September 29:
  user-authorized MRHA migration of sealed raw payloads is in progress; verify
  completion, reader continuity and measured space before marking storage reconciled.
  [Migration evidence](docs/reviews/2026-09-29-mrha-payload-migration.md).
- [ ] **7-3.close:** Record full completion against the roadmap gate and actual
  evidence. Entry capture alone does not close 7-3.

## Remaining steps in the selected phase

- [ ] **7-4:** Complete integrated full-scope execution coverage from the selected
  retained ledger. Reconcile actual expiry, settlement and stock liquidation
  where applicable. Preserve completed components and existing integration.
- [ ] **7-5:** Connect existing inputs to assembly/folds/trials; reconcile the
  full agreed dataset, label horizons and predeclared purged folds.
- [ ] **7-6:** Establish measured integrated build/training resources, restart
  behavior and coexistence with operational experts. Reuse unchanged evidence.
- [ ] **7-7:** Make readiness consume the current contracts and completion
  receipts, then launch the predeclared training campaign after its gates pass.

Dependencies may be connected while acquisition runs when selected by the user;
this does not change the active gate or authorize reopening completed stages.
Exact scope remains in the [V7 specification](docs/specs/MULTITIMEFRAME_RESEARCH.md)
and its accepted amendments, indexed by [CURRENT_STATE](docs/CURRENT_STATE.md).

## Separate operating obligations

These are explicit parallel obligations, not extra V7-3 completion conditions.

- [x] **OPS-PAPER:** First prospective actual-order/fill reconciliation observed.
  September 29 at 17:30 Central: all 48 broker orders match the journal, eight
  filled orders, four matching positions and zero open orders. No outage-recovery
  orders submitted. [Evidence](docs/reviews/2026-09-29-paper-reconciliation-v6-resume.md).
  September 30: three-step policy deployed; user-approved one-time AXP/VG
  retries filled at step 2. All 77 orders reconciled at 10:40; zero open orders.
  Follow-up source cleanup v3 fixes a stale, unfilled VG projection protected
  by earlier same-contract fills. Deployed 10:59; 11:00 scan retired that source.
  The 11:00 scan completed in 256.537 seconds, 308 candidates, zero errors. [Policy and fills](docs/reviews/2026-09-30-v6-step-policy-v4.md).
  Do not repeat activation or import old simulator positions.
- [ ] **OPS-INCUBATOR.DATA:** Implement and validate V6-only continual candidate
  features and matured simulated labels across the frozen universe, independent
  of actual trades. Implementation and SPY pilot passed; finish the 449-symbol
  catch-up. Corrected r3 resumed September 28 at 23:07 Central, preserving
  38 completed r2 symbols and partial feature/label seals. All 17 original error
  cases passed targeted checks: six identity collisions and eleven transient tick
  failures. September 30: 325/449 completed; all 124 remaining entries report
  timeout/deadline at the 08:00 market-hours cutoff. Checkpoints are retained.
  Dedicated handover is scheduled September 30 at **15:01 Central**. Verify
  `healys-v6-focus-20260930.service` and its actual receipts; preserve the pinned
  catch-up and checkpoints. Training/freeze have not started. This one-time
  user-requested close-time exception leaves the normal market guard unchanged. [Observation](docs/reviews/2026-09-30-v6-step-policy-v4.md).
  [Overnight observation](docs/reviews/2026-09-29-overnight-checkpoints.md).
  [Repair and current observation](docs/reviews/2026-09-28-v6-continual-error-repair.md).
  Preserve the base freeze and resumable daily extensions.
- [x] **OPS-INCUBATOR.TRAIN:** Implement fixed-family retraining, temporal validation,
  baseline comparisons and immutable candidate freezes; retain the previous
  accepted model on rejection/failure/deadline. Targeted tests and a full-size
  member benchmark passed; the full ensemble freeze remains under PROOF.
  [Evidence](docs/reviews/2026-09-27-v6-continual-incubator.md). No automatic deployment.
- [ ] **OPS-INCUBATOR.OPS:** Replace replay-only scheduling with bounded continual
  research and verify restart, daily-input readiness and resource coexistence.
  Completion gate and automatic 05:00 restart verified September 28. Initial
  catch-up remains incomplete; full update/recovery/coexistence proof remains.
  September 29: installed up to four autosized data workers, CPU 400%,
  19/20-GiB limits for the next permitted run; the calendar cutoff remains.
  September 30: dedicated 26-GiB allocation, autosized data workers and all
  available training CPU threads prepared for the 15:01 handover; measured
  full-run results remain pending. [Dedicated schedule](docs/reviews/2026-09-30-v6-dedicated-compute.md).
  [Prior sizing and verification](docs/reviews/2026-09-29-v6-worker-sizing.md). Post-outage
  restart and forward progress verified; full run/coexistence proof remains open.
  [Restart evidence](docs/reviews/2026-09-29-paper-reconciliation-v6-resume.md). Retries retain an
  unfinished catch-up date; verify full completion and sustained resource use.
- [ ] **OPS-INCUBATOR.PROOF:** Complete the initial catch-up and measure a full
  daily update through freeze before claiming next-trading-day readiness.
  [Current contract](docs/specs/AI_INCUBATOR.md). V5 paper scoring is superseded.
- [ ] **OPS-PROVIDER, by October 2:** Give the user a source-backed Massive
  keep/cancel recommendation using pre-February-2024 V7 captures, representative
  SPX/NDX Alpaca history and V6 adapter/decision parity. If evidence is incomplete,
  recommend retaining another month. The user decides cancellation.
  [Decision gate](docs/reviews/2026-09-24-v6-alpaca-paper-start.md).

FA collection is included in the temporary local 15:01 compute pause and
automatic post-V6 restoration; its normal schedules otherwise remain selected. Additional FA research,
SPX0, volatility, stacking, RL and panel expansion remain in the roadmap until
selected; they do not get independent active TODOs or handoffs.
