# TODO — Phase 7: V7 data, execution and training

**Current gate: 7-3.** 7-1 and 7-2 are complete. This is the selected phase's
checklist; the [ROADMAP](ROADMAP.md#phase-7--v7-data-execution-and-training)
owns its gates and dependencies. [HANDOFF](HANDOFF.md) gives the session's
stopping point. Use [CURRENT_STATE](docs/CURRENT_STATE.md) for exact inputs and
running-job locations; do not choose a different revision from an old review.

## Active gate 7-3 — required option evidence

Reuse the [verified completed preparation](docs/reviews/2026-09-27-v7-3-remaining-input-verification.md).
The following scope is unchanged by the documentation consolidation.

- [x] **7-3.entry:** Full-universe entry quote/trade capture completed September 28
  at 04:58 Central. The final queue count reconciles with prior capture subtraction.
  [Completion evidence](docs/reviews/2026-09-28-overnight-entry-completion.md).
  Preserve completed packs; do not launch another entry campaign.
- [ ] **7-3.references:** Acquire remaining dated references from the completed
  demand plan, reuse captured coverage and apply the existing five exact
  blackouts. Actual held paths may add dates; account for new missing references.
  Full-plan capture and independent census completed at 16:48 September 28.
  A verified exact overlay resolves 22 rename mismatches; nine cash-deliverable
  rows and 10,817 unapproved missing references remain unresolved.
  [Completion/admission evidence](docs/reviews/2026-09-28-v7-reference-completion.md).
- [ ] **7-3.paths:** Complete only actual held-mark, exit, roll and applicable
  stock-delivery gaps requested by the existing replay frontier. Preserve
  partial ledgers and count held blackout crossings. Potential first-leg
  envelopes are not blanket download orders.
- [ ] **7-3.reconcile:** Reconcile required requests, captures, references,
  provider failures and measured storage for execution/assembly/recovery.
  Use the already-authorized allocation in the current-state index.
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

- [ ] **OPS-PAPER:** Observe the first prospective Alpaca session and actual
  order/fill reconciliation. Activation is complete; use the current deployment
  receipt. September 28: timely full scan and accepted/canceled order reconciled;
  first actual fill remains pending. Independent orders remain enabled; V3's
  user-requested four-step limits deployed at 14:52 Central, finalized at 15:08, with 76 focused tests
  and authenticated polling passed. Observe prospective ladder fills/reconciliation.
  [Step policy and deployment](docs/reviews/2026-09-28-v6-step-orders.md).
  Scanner v4 deployed at 14:21 after a never-filled ANF projection blocked scans;
  14:30 full scan passed and two new orders were submitted at 14:34, canceled
  unfilled, then archived automatically at 14:45. The current scanner protects active ladders.
  [source reconciliation repair](docs/reviews/2026-09-28-v6-unfilled-source-repair.md).
  [Execution policy](docs/reviews/2026-09-28-v6-independent-orders.md).
  [Readiness repair](docs/reviews/2026-09-28-v6-paper-readiness.md).
  Do not repeat activation or import old simulator positions.
- [ ] **OPS-INCUBATOR.DATA:** Implement and validate V6-only continual candidate
  features and matured simulated labels across the frozen universe, independent
  of actual trades. Implementation and SPY pilot passed; finish the 449-symbol
  catch-up. Repaired r2 lineage started September 28 at 18:17 Central against
  verified restated inputs, with per-entry cache release and worker recycling.
  [Recovery evidence](docs/reviews/2026-09-28-v6-continual-recovery.md).
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
  September 28: repaired r2 is running with 11/12-GiB limits. Retries retain an
  unfinished catch-up date; verify full completion and sustained resource use.
- [ ] **OPS-INCUBATOR.PROOF:** Complete the initial catch-up and measure a full
  daily update through freeze before claiming next-trading-day readiness.
  [Current contract](docs/specs/AI_INCUBATOR.md). V5 paper scoring is superseded.
- [ ] **OPS-PROVIDER, by October 2:** Give the user a source-backed Massive
  keep/cancel recommendation using pre-February-2024 V7 captures, representative
  SPX/NDX Alpaca history and V6 adapter/decision parity. If evidence is incomplete,
  recommend retaining another month. The user decides cancellation.
  [Decision gate](docs/reviews/2026-09-24-v6-alpaca-paper-start.md).

FA collection continues under its existing schedules. Additional FA research,
SPX0, volatility, stacking, RL and panel expansion remain in the roadmap until
selected; they do not get independent active TODOs or handoffs.
