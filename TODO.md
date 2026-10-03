# TODO — ETFE scope and data contract

**Selected work: ETFE — Exchange Traded Funds Expert. Current gate: ETFE-0.**
October 3 user direction selects a brand-new ETFE expert: exactly SPY, QQQ, VOO;
V7 strategy/timing specifications; 1/5/15-minute signals; Alpaca's earliest
options history through October 2, 2026, inclusive. No Massive quotes. [Specification](docs/specs/ETFE.md),
[roadmap](ROADMAP.md#etfe--exchange-traded-funds-expert), [handoff](HANDOFF.md).
This selection is documentation work; implementation and campaigns remain future
milestones. V7 archival continues as the existing storage obligation below.

## Selected checklist — ETFE-0

- [x] **ETFE.scope:** Record the accepted universe, timeframes and V7 inheritance;
  preserve later midpoint/risk amendments and distinguish signal bars from quotes.
- [x] **ETFE.dates:** User confirmed Alpaca's earliest historical options
  availability through October 2, 2026, inclusive. This is a fixed window, not
  our recording start or a moving latest-session end.
- [ ] **ETFE.history-boundary:** Verify the exact first Alpaca options timestamp
  and UTC boundaries for the fixed October 2 end; record missing feature/quote
  coverage separately rather than silently shortening the requested window.
- [ ] **ETFE.provider-contract:** Establish how required historical bid/ask windows,
  dated contracts and feature inputs will be supplied. Historical trades/bars
  alone do not satisfy inherited execution/quote features. Alpaca is the options
  provider; Massive quotes, including archived V7 copies, are excluded. Resolve
  any necessary methodology decision before freezing the executable ETFE plan.

Later implementation, coverage, resource and training gates belong to the
[ETFE roadmap](ROADMAP.md#etfe--exchange-traded-funds-expert), not competing queues.
V7's paused scientific checklist is preserved in
[the pre-ETFE snapshot](handoff-history/TODO-2026-10-03-before-etfe.md);
V7 gates remain in ROADMAP with their prior completion boundaries intact.

## Existing storage obligation — finish V7 preservation

- [ ] **7-3.archive:** Complete all MRHA shards, full verification and final
  reclamation bookkeeping; require `VERIFIED.json` and `COMPLETE.json`.
  [Archive scope](docs/reviews/2026-10-02-v7-cold-archive.md).
- [x] **7-3.archive-local:** All 35,031 eligible local files removed at 14:54 Central
  October 3 after verification; about 519 GiB internal free at 15:06.
  [Completion audit](docs/reviews/2026-10-03-v7-local-cleanup-complete.json).

Refresh archive notes at its completion. Restoration is only on user direction,
using the [README](docs/reference/V7_COLD_ARCHIVE_README.md); do not resume V7
from historical checklist entries. New ETFE artifacts retain their own identity.

## Paused operating obligations — resume only on user direction

Retained requirements and completed evidence below are not ETFE prerequisites or
active parallel assignments. October 3 selects ETFE documentation; other campaigns
remain paused unless the user selects them.

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
- [x] **OPS-PROVIDER.DECISION:** October 2 user cancelled Massive options and
  chose preserving V6 features and the full universe. The former keep/cancel
  recommendation is superseded; provider equivalence is not established.
- [x] **OPS-PAPER.ALPACA-QUOTES:** Scanner v12 deployed at 14:20:49 Central;
  Alpaca held monitoring completed at 14:23:50 with zero errors. Massive option
  requests removed from the paper scanner; broker policy unchanged.
- [ ] **OPS-PAPER.ALPACA-COVERAGE:** Full-universe entries explicitly blocked,
  as selected by the user. Read-only census already needs 2,434 contracts for
  414 securities versus the documented 1,000-quote limit; 35 catalogues and
  intraday strike headroom are additional. Actual capacity probe returned 405
  (symbol limit exceeded). Resolve feed capacity, prospective
  catalogues, complete preceding windows and feature/decision admission.
  Bounded recorder transport tested; no full-universe recording/admission claim.
  [Transition and remaining work](docs/reviews/2026-10-02-v6-alpaca-provider.md).

FA and other unselected work remain deferred. Their retained
roadmap requirements do not authorize parallel campaigns or automatic resumption.
The verified runtime pause is scoped in CURRENT_STATE; this work-selection note
does not assert that unrelated installed services were stopped.
