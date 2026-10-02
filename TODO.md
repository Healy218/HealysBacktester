# TODO — Phase 7: V7 data, execution and training

**Current gate: 7-3.** 7-1 and 7-2 are complete. This is the selected phase's
checklist; the [ROADMAP](ROADMAP.md#phase-7--v7-data-execution-and-training)
owns its gates and dependencies. [HANDOFF](HANDOFF.md) gives the session's
stopping point. Use [CURRENT_STATE](docs/CURRENT_STATE.md) for exact inputs and
running-job locations; do not choose a different revision from an old review.

## Active gate 7-3 — required option evidence

**October 2 current direction — optimized V7 resumed.** After the user authorized
adoption, both selected controllers resumed at 12:45:08 Central with retained
checkpoints. New selected root: `v7-required-inputs-20261002-perf-r0`.
[Adoption and evidence](docs/reviews/2026-10-02-v7-performance-adoption.md).
- [x] **7-3.performance:** Bounded profiling, versioned optimization, exact
  scientific-table and killed-process recovery parity, and worker scaling tested.
  Six resumed discovery comparisons improved 1.59×; benchmark scaling and limits
  are recorded in [the review](docs/reviews/2026-10-02-v7-performance-benchmark.md).
  This is bounded validation, not full-scope deployment or gate closure.
- [x] **7-3.performance-adoption:** New source-bound controller lineage deployed;
  original checkpoints preserved with verified copy-on-write inheritance. Three
  integrated canaries matched baseline results exactly; 35 focused tests passed.
  Hourly reporting follows the selected successor without resetting totals.
  Observe actual progression/resource waits; full required-input coverage remains open.

**October 1 completed operating task:** CRSP/MTUM repaired; V6 through September
30 finished at 02:32 Central (449 symbols, 40 members, evaluated immutable freeze).
All 447 prior symbol seals preserved. Diagnostic regression recorded; the new
freeze is retained. V7 discovery/migration restored; capture needed an explicit
retry of two retained HTTP 502 failures and was verified advancing after 02:48.
That restoration is historical; the October 2 optimized adoption above owns execution.
Hourly checks here remain active. October 2 reporting now focuses on V6 paper
and cumulative V7-3 work; completed storage and successful idle incubator runs
are omitted. [Completion and restart evidence](docs/reviews/2026-10-01-v6-occurrence-repair.md).

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
  October 2: discovery scheduler ceiling raised to four overnight with dynamic
  memory admission; two during weekday paper/daily-V6 hours. At 08:00 two active,
  checkpoints preserved. Later bounded tests measured four-worker scaling; the
  optimized controller was adopted at 12:45 October 2 (see above).
  [Resource revision](docs/reviews/2026-10-02-v7-discovery-resources.md).
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
  October 1: TLT data-vintage repair published 10:45:53; actual UAL and FLY
  entries subsequently filled. Resource-only v9 yielded five observed 261–286s
  scans with zero detection errors. Late starts and missing fresh option quotes
  still withhold entries; 14:45 FLY quote blocker persists. Broker polling remains
  active; preserve the freshness guard and observe subsequent provider receipts.
  [Recovery and timing evidence](docs/reviews/2026-10-01-v6-paper-vintage-repair.md).
  Do not repeat activation or import old simulator positions.
- [x] **OPS-PAPER.WINDOW:** October 2 user-authorized ten-minute entry window
  deployed across scanner, broker and unfilled-source retention; 101 focused tests
  passed. [Evidence](docs/reviews/2026-10-02-v6-ten-minute-window.md).
- [ ] **OPS-PAPER.RELIABILITY:** October 1 quote-recovery consumer deployed and
  verified after hours at 15:32 Central. Bounded held-quote retries overlap full
  candidate computation; unresolved monitoring still blocks allocation. Verify
  prospective recovery and timely completed scans next market session, plus
  independent broker reconciliation. No guarantee of timing from idle startup.
  [Repair and acceptance](docs/reviews/2026-10-01-v6-paper-quote-recovery.md).
- [x] **OPS-INCUBATOR.DATA:** Complete the frozen-universe V6 initial catch-up.
  September 30 at 22:40:47: all 449 symbols, 40 training members and evaluated
  candidate freeze completed; 122 candidate payload files verified. The candidate
  was rejected by baseline comparisons, retaining the incumbent. Frozen inputs,
  provenance and successful checkpoints preserved. [Evidence](docs/reviews/2026-09-30-v6-dedicated-compute.md).
- [x] **OPS-INCUBATOR.TRAIN:** Implement fixed-family retraining, temporal validation,
  baseline comparisons and immutable candidate freezes; retain the previous
  accepted model on rejection/failure/deadline. Targeted tests and a full-size
  member benchmark passed; full 40-member training/evaluation/freeze completed
  September 30. A subsequent daily update remains under PROOF.
  [Evidence](docs/reviews/2026-09-27-v6-continual-incubator.md). No automatic deployment.
- [ ] **OPS-INCUBATOR.OPS:** Verify daily-input readiness and sustained resource
  coexistence. September 30 initial catch-up and candidate freeze completed;
  rejection retained incumbent. At 22:40:49 automatic timer restoration and
  research starts succeeded, with migration and both V7 successor controllers
  active on readback. October 1 repaired two-session update and restoration
  completed; clean daily timing and sustained coexistence remain.
  [Evidence](docs/reviews/2026-09-30-v6-dedicated-compute.md).
- [ ] **OPS-INCUBATOR.PROOF:** Initial catch-up/full freeze completed September 30;
  a repaired two-session update through September 30 also completed October 1.
  Measure a clean one-session update through freeze before claiming sustained
  next-trading-day readiness. No automatic deployment.
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
