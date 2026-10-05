# TODO — ETFE fresh Alpaca acquisition

**Selected work: fresh Alpaca-only ETFE setup and acquisition.**
User clarified that ETFE starts with new Alpaca stock/option downloads, then
rebuilds its own features, labels and models. No old project data or metadata is
an input. New entries and rolls use **0–5 calendar DTE**; target 7 is removed.
SPY/QQQ/VOO, 1/5/15-minute signals, all twenty families and completed-minute
option VWAP remain. [Current scope](docs/specs/ETFE_SCOPE_0DTE_20261004.json),
[DTE amendment](docs/specs/ETFE_0DTE_NORMALIZATION_20261004.md),
[fresh acquisition contract](docs/specs/ETFE_FRESH_ACQUISITION_20261003.md).

Raw download setup may proceed while source/coverage validation continues.
Provider-global history proof and repairs to old project metadata are not
collection prerequisites. Establish the earliest available **SPY/QQQ/VOO**
history through the fresh coverage census; preserve the fixed October 2, 2026
end. No fabricated history, point-in-time admission or full coverage claim.
[Authoritative sequence](ROADMAP.md#etfe-first-run-sequence),
[latest evidence](docs/reviews/2026-10-05-etfe-action-replay.md),
[handoff](HANDOFF.md).

The latest user amendment explicitly enables 0DTE when signals qualify.
Selected normalized inputs and bounded January option coverage are complete
within their declared scope. Calendar-level phase-A demand is enumerated;
210 focused tests pass. All 221 registered fields are joined with 221 masks
for every one of the 458,133 pilot events; independent value/lineage audit and
actual resume pass. Real diagnostics and synthetic-only evidence remain
separate. Dated inputs, usable history and scientific admission remain open.
Fresh action evidence now includes 35 records and a bounded mutation replay;
process-date tail queries recovered two September actions omitted by the initial
date filter. Historical publication and complete action coverage remain open.
The four-day replay successor now verifies one pre-effective SPY action witness;
three earlier controls returned no events. This does not establish retention or
complete timing. Freeze still requires admitted inputs/full coverage, execution
and labels, integrated pilot/recovery, and the full dataset build.

## Current checklist — ETFE setup / acquisition

- [x] **ETFE.setup:** Independent strategy catalog remains twenty families and
  25,353 ticker/variant combinations. Current v4 setup has fresh-source policy,
  separate artifact identity and explicit 0–5 DTE guard; old setups preserved.
- [x] **ETFE.provider-probe / quote-diagnosis / pull-diagnosis:** Alpaca stock
  and option bar/trade routes verified. Historical option quotes unsupported;
  historical trades reject `feed`. Earlier diagnostics remain dated evidence,
  not data imported into the new capture roots.
- [x] **ETFE.pricing-basis:** Completed one-minute option VWAP selected; causal
  reference component implemented. Full execution validation remains separate.
- [x] **ETFE-0.feature-map / execution-contract / experiment-contract /
  acquisition-design:** Four definitions declared. Fresh-acquisition and 0–5 DTE
  successors override collection ordering and purchase range, respectively.
  Rebuild the implementation/schema from fresh inputs; do not reuse old arrays.
- [x] **ETFE-1.bootstrap:** Resumable source-bound raw downloader and reader;
  six stock, twelve discovery and twelve option bar/trade partitions captured.
  36 live GETs, 50,106 stock bars, 2,284 option bars, 39,975 option trades and
  2,084 fresh discovery records. Live resume preserved prior committed files.
  This completes bounded download setup, not full acquisition or ETFE-4.pilot.
- [x] **ETFE.purchase-dte:** Current scope and tested guard reject actual DTE
  outside 0–5 at every new entry/roll. Default targets 0/1/5, conditional weekly
  targets 2/4; target 7 removed. Qualifying signals and dated expiry cutoffs
  remain required. `dte_frac` divides by five and permits zero.
- [x] **ETFE-1.normalize:** Typed bounded Parquet, row quality and stock-session
  gap reports complete for 186 selected raw partitions / 1,677,986 rows. Exact
  timestamps, raw JSON and occurrence lineage retained; independent full-row
  reconciliation and actual resume passed. No rows are fabricated or deduplicated.
- [x] **ETFE-1.expand:** Remaining 96 stock-month partitions and 0–5 DTE option
  discovery/transport strata captured and normalized; 254 new live GETs. Stock
  requests span January 2024–October 2, 2026. SPY/QQQ have every expected regular
  minute; 12 VOO gaps remain explicitly unresolved. Full option demand is separate.
- [x] **ETFE-1.demand-calendar:** Full collection-window calendar inventory:
  691 sessions, 2,073 ticker-sessions, 190,716 expiry/status edges factored into
  6,300 discovery queries. Includes every civil expiry at 0–5 DTE for purchases
  and 1–45 DTE for context; 60 exact completed queries reused. Catalog and
  feature/execution definitions bound; no additional context ticker required.
  [Bounded study](docs/specs/ETFE_DEMAND_20261004.md),
  [active-time budget successor](docs/specs/ETFE_DEMAND_CONTINUATION_20261004.md).
- [x] **ETFE-1.expand-january:** 960 successful live GETs; January expiry discovery,
  all-returned-symbol January 1–17 bar check, full January 18/19 surfaces. Added
  200,637 normalized records in 960 partitions; every raw occurrence and all
  34,660 surface symbol/day edges independently reconciled. Empty windows remain
  unresolved. [Evidence](docs/reviews/2026-10-04-etfe-demand-boundary.md).
- [x] **ETFE-2.causal-components / ETFE-1.demand-pilot:** Fresh session grids
  at 1/5/15 minutes and fifteen raw technical diagnostics; all twenty families /
  25,353 ticker variants exercised on January 18–19 with January 2 padding.
  All-variant prefix/batch checks, actual scope resume and logical/physical audit
  pass. 458,133 signal/target links retained; no historical selection or entry
  admitted. [Evidence](docs/reviews/2026-10-04-etfe-causal-pilot.md).
  Full 221-field schema, dated action adjustment, full phase-B demand and the
  integrated ETFE-4.pilot remain separate.
- [x] **ETFE-1.trade-window-capture:** All 225 pilot trade intervals captured
  through 103 exact-window queries / 105 successful GETs. Added 77,057 normalized
  trade occurrences; raw-row, timestamp, edge and 4,626-minute audits pass.
  Actual capture resume preserved prior committed files. Fifty-four empty
  intervals and three trade-without-bar minutes remain unresolved observations.
  [Evidence](docs/reviews/2026-10-04-etfe-trade-windows.md). Capture completion
  does not admit features or execution.
- [x] **ETFE-2.option-trade-bar-components:** All ten registered formulas,
  conditions, availability, missingness and ambiguous-order rules implemented.
  Selected r1 reconciles all 4,739 windows / 458,133 logical memberships; 1,803
  windows have all diagnostic values. Independent numerical/mask/reason audit,
  real future/order checks and actual resume passed. Initial r0 failed a tiny
  VWAP rounding tolerance; preserved and superseded with stable accumulation,
  without relaxing tolerance. [Evidence](docs/reviews/2026-10-04-etfe-option-features.md).
  Model-feature admission remains false; full schema and integrated pilot open.
- [x] **ETFE-2.tv-components:** All 96 registered projections across thirteen
  numerical sources implemented from fresh stock bars. January pilot retains
  2,964 observations / all 458,133 logical event links, with explicit readiness,
  masks and reasons. Independent projection/membership audit, eighteen real
  prefix/future checks, actual resume and 143 focused tests pass.
  [Evidence](docs/reviews/2026-10-05-etfe-tv-features.md). External Pine parity,
  model-feature admission and full schema remain open.
- [x] **ETFE-2.remaining-components:** Implemented the remaining 100 fields
  and variant MA projections. All 8,451 catalog records, 152,711 signals /
  458,133 event links and 2,073 daily-context rows reconciled; full-prefix signal
  age, next-open availability, real prefix/batch checks and actual resume pass.
  157 focused tests pass. Two unimplemented Setup formula errors corrected by
  versioned amendment; predecessors preserved. Dated contract/sector and seven
  option-context fields remain missing on real data, with synthetic API/formula
  tests only. [Evidence](docs/reviews/2026-10-05-etfe-remaining-features.md).
- [x] **ETFE-2.joined-schema:** Registered 221-value/221-mask diagnostic matrix
  complete for all 458,133 original events in 96 bounded chunks. Independent
  natural-key audit checks all values, masks, reasons, modeled availability,
  row identities, variant overrides and provenance. Every chunk passed changed
  batch-boundary checks; actual resume preserved five files. 173 focused tests
  pass. [Evidence](docs/reviews/2026-10-05-etfe-joined-schema.md).
  Dated actions, identities, option surfaces/sessions and publication evidence
  remain unresolved; all diagnostics stay unadmitted.
- [x] **ETFE.provider-actions:** Fresh Alpaca action capture, normalization,
  raw-occurrence audit and actual resume complete in declared scope. Fourteen
  GETs retained 35 dividend records (33 effective in the price window); a bounded
  process-date tail recovered missing SPY/QQQ September actions. Stream inspection
  retains 15 ETF updates from 19,132 complete events before the byte cap.
  Independent audits and 196 tests pass. No original-publication or complete
  history claim. [Evidence](docs/reviews/2026-10-05-etfe-action-evidence.md).
- [x] **ETFE.provider-action-replay:** Four fixed days reached transport EOF in
  selected r1. September 17 has 41,730 unique events / 3,829 exact overlaps and
  five SPY mutations before its September 18 ex-date. Earlier controls are empty,
  with history coverage unknown. Original r0 stopped on submillisecond cursor
  behavior; preserved, superseded by whole-second overlap without relaxing bounds.
  Independent audit, twelve-file actual resume and 210 tests pass.
  [Evidence and freeze gap](docs/reviews/2026-10-05-etfe-action-replay.md).
- [ ] **ETFE-3.execution-components:** Implement and hand-reconcile the bounded
  VWAP execution ledger: funded integer entry, shared participation, partial
  exit/latched stop, settlement and explicit unresolved/boundary outcomes. Use
  synthetic dated references for mechanics where real admission is unresolved;
  integrate real paths only with validated evidence. This supports ETFE-4.pilot
  and does not depend on pretending the current inputs are admitted.
- [ ] **ETFE.provider-action-timing:** Establish mutation-history retention and
  dated original/revision availability for required actions. January's welcome-only
  stream and October's capped replay do not prove coverage. Budget any expanded
  replay using measured volume; do not apply current observations to past inputs.
  The new complete-day transport yields only one matched pre-effective action
  witness among 35 records, not full original/revision availability.
- [ ] **ETFE-1.demand:** Complete symbol/session surfaces after discovery,
  full-window causal signal/feature/trade demand (phase B), and holding/roll/
  physical-stock paths (phase C). Current calendar inventory is not the full
  strategy demand census. Reconcile measured request/storage budgets before
  bulk capture; the stock-month expansion is complete.
- [ ] **ETFE.history-boundary:** January 1–17 returned no bars for all 23,176
  discovered symbols in the January–March 4 expiry grid; January 18 09:30 ET is
  first observed for all three ETFs. Establish usable/complete coverage;
  pre-January intervals, longer expiries and omitted historical listings remain
  outside this proof. January stock padding is not an admitted research start.
- [ ] **ETFE.provider-contract:** Validate remaining route provenance and dated
  eligibility/session/contract terms when needed by feature/execution admission.
  R1/R2/P1 are not permission gates for raw collection. ETFE-0 admission remains
  open; current expired listings are discovery records, not historical features.
- [ ] **ETFE-4.pilot:** Integrate fresh capture → features → execution → dataset
  → training smoke measurement and recovery. Reconcile full demand and resource
  budgets before bulk work; final input/dataset freeze and training stay later.

Preserve all completed setup evidence, including the earlier contract verifier's
historical gate status. [Prior phase checklist](handoff-history/TODO-2026-10-04-before-fresh-acquisition.md).
Later gates remain in ROADMAP; neither raw download completion nor the DTE
component closes full coverage, execution validation or model evaluation.

## Completed storage obligation — V7 preservation

- [x] **7-3.archive:** Completed October 3 at 16:55:50 Central. All 2,847 shards
  verified, matching local/MRHA VERIFIED/COMPLETE receipts, no partial files,
  35,031 eligible local files reclaimed. Independent receipt/census reconciliation
  and four fresh streamed restore samples passed; README and compressed notes
  refreshed. [Completion audit](docs/reviews/2026-10-03-v7-archive-completion-audit.json).
- [x] **7-3.archive-local:** All 35,031 eligible local files removed at 14:54 Central
  October 3 after verification; about 519 GiB internal free at 15:06.
  [Completion audit](docs/reviews/2026-10-03-v7-local-cleanup-complete.json).

Archive notes record completion. Restoration is only on user direction,
using the [README](docs/reference/V7_COLD_ARCHIVE_README.md); do not resume V7
from historical checklist entries. New ETFE artifacts retain their own identity.

## Paused operating obligations — resume only on user direction

Retained requirements and completed evidence below are not ETFE prerequisites or
active parallel assignments. October 3 selects ETFE setup; other campaigns
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
