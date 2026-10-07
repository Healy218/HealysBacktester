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
[latest evidence](docs/reviews/2026-10-06-etfe-full-coverage.md),
[handoff](HANDOFF.md).

The latest user amendment explicitly enables 0DTE when signals qualify.
Selected normalized inputs and bounded January option coverage are complete
within their declared scope. Calendar-level phase-A demand is enumerated;
320 focused tests pass. All 221 registered fields are joined with 221 masks
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
The bounded synthetic option ledger now reconciles cash, integer participation,
partial stops and T+1 cash settlement, including a separate-process restart.
The synthetic lifecycle continuation now covers expiry classification, settled
roll budgets, exercise reservations, physical call delivery and stock liquidation.
Four hand cases, thirteen saved prefixes and separate-process restart reconcile.
The bounded shared scheduler now integrates ordinary entries and lifecycle
clocks, settlement-extended diagnostic horizons and all 27 declared synthetic
stress profiles across six tapes. All 162 combinations / 189 proposal outcomes
reconcile; three stressed paths retain missing quote/exercise inputs explicitly.
Scientific labels, full-history execution and real admission remain open.
Full-range discovery now covers **6,300 / 6,300** calendar expiry/status queries:
452,347 unique contracts, all 45,470 prior symbols reconciled, and 2,073
symbol/session surfaces counted. This is complete discovery transport, not full
market-window coverage or historical listing completeness. Dated-input checks
flag 43,720 invalid/zero multipliers and 53,634 pre-transition expiries reporting
T+1. Full-window announcements supply 33 declaration dates, but original/revision
availability remains unresolved. Invesco's official 2024 QQQ tax file
retrospectively resolves the March 18 payable date to April 30; it does not
establish what was available before the event. **Continue ETFE-0/ETFE-1:** exact
windows are enumerated over the computable signal scope; unresolved dated
selection and execution prevent realized holding paths and complete strategy
demand. Resolve the history boundary and dated-input failures before admission.
Freeze/train remain later in the first-run sequence.

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
- [x] **ETFE-3.execution-components:** Bounded synthetic VWAP ledger implemented:
  funded integer entry, shared participation, partial exit/latched stop, option
  cash settlement and explicit unresolved/boundary outcomes. Hand arithmetic,
  independent Decimal audit, five-prefix replay and separate-process restart
  pass; 234 focused tests. [Evidence](docs/reviews/2026-10-05-etfe-execution-components.md).
  No real-data execution, label admission or full ETFE-3 closure implied.
- [x] **ETFE-3.expiry-components:** Synthetic lifecycle continuation implements
  quote-based expiry, OTM roll reservations/settled budgets, exercise funding,
  call delivery and partial stock liquidation. Funded call, unfunded put,
  competing calls and roll hand cases reconcile; transition/holiday, missing
  inputs, adjusted integer deliverables and boundary tests pass. Thirteen-prefix
  independent audit and actual resume pass; 265 focused tests.
  [Evidence](docs/reviews/2026-10-05-etfe-expiry-components.md). Full execution,
  real admission and funded-put inventory integration remain separate.
- [x] **ETFE-3.integration-components:** Bounded synthetic shared scheduler
  connects ordinary entries, expiry/roll/delivery and cash settlement; generates
  observation/retry clocks and diagnostic terminal horizons. All 162 combinations
  across six tapes / 27 profiles reconcile independently, including 189 outcome
  records and three unresolved stressed paths. Actual restart, input/source
  binding and 289 focused tests pass. [Evidence](docs/reviews/2026-10-05-etfe-integration-components.md).
  Scientific isolated labels, full-history scheduling/resource validation,
  real-source integration and full ETFE-3 acceptance remain open.
- [x] **ETFE-1.demand-frontier:** Full-calendar known-symbol envelope, explicit
  hold/roll/exercise input requirements and measured route payload scenarios.
  One bounded March 5–25 discovery batch added 8,462 records / 126 partitions;
  raw-row audits and zero-request restart pass. Both frontier inventories
  reconcile independently across 2,073 ticker-sessions; 294 focused tests pass.
  Exact phase-B/C counts, missing-source measurements and full budgets remain
  open. [Evidence](docs/reviews/2026-10-05-etfe-demand-frontier.md).
- [x] **ETFE-1.stock-quote-pilot:** Captured/normalized/audited 54 bounded SIP
  quote windows for SPY/QQQ/VOO only: 216 successful pages / 1,943,472 occurrences.
  Ten new tests and actual capture restarts pass; raw sizes stay unconverted,
  1,991 crossed quotes stay flagged. A second discovery batch adds 7,344 records
  and frontier r2 reconciles independently. Exact path/window demand, dated
  size representation and official exercise references remain open.
  [Evidence](docs/reviews/2026-10-05-etfe-stock-quotes.md).
- [x] **ETFE-1.full-discovery:** All six range queries / 455 successful pages
  normalized and independently audited; 452,347 unique symbols, all 6,300
  calendar partitions and 2,073 ticker-sessions reconciled. Actual raw/typed
  restarts preserve hashes. Full-window action announcements: 36 successful
  queries, 33 records matched to previous in-window actions; one payable conflict.
  Dated validation records missing clocks and contradictory current terms;
  historical/full-market admission remains open. 320 tests pass.
  [Evidence](docs/reviews/2026-10-06-etfe-full-coverage.md).
- [ ] **ETFE.provider-action-timing:** Establish mutation-history retention and
  dated original/revision availability for required actions. January's welcome-only
  stream and October's capped replay do not prove coverage. Budget any expanded
  replay using measured volume; do not apply current observations to past inputs.
  The new complete-day transport yields only one matched pre-effective action
  witness among 35 records, not full original/revision availability. The complete
  announcement snapshot adds declaration dates for 33 in-window actions, but
  no revision timeline. Official Invesco evidence resolves QQQ's March 2024
  payable date retrospectively to April 30; prior decision availability stays
  unknown. [Window review](docs/reviews/2026-10-06-etfe-window-demand.md).
- [x] **ETFE-1.exact-window-demand:** Full collected-history signal census:
  180 checkpoints / 25,353 variants, with 137,080 context batches / 13,609,133
  contract-session memberships. Factored 4,311,060 decision clocks across
  151,005,384 logical 0/1/5-DTE links; exact known-candidate physical union has
  2,857 option-bar and 3,446 trade intervals before subtracting verified captures.
  Independent timing/count audit and zero-GET computational restart pass.
  [Review](docs/reviews/2026-10-06-etfe-window-demand.md). No dated selection,
  execution, or realized holding paths are admitted.
- [ ] **ETFE-1.path-demand:** Continue from dated eligible selection and actual
  execution receipts through holding, exits, rolls, exercise and settlement.
  Current exact windows depend on today's observed symbol inventory and
  computable stock states. A 24-window density pilot returned 513 option bars
  and 8,409 trades, including two empty trade windows; full-campaign sizing and
  resource admission remain open.
- [x] **ETFE-1.exact-window-capture:** Source-bound grouped plan: 3,036 requests
  (1,369 option bars / 1,667 option trades), all terminal across 3,116 committed
  pages (80 pagination). 2,275,130 normalized occurrences (70,354 bars /
  2,204,776 trades); 194 bar and 112 trade windows returned no rows. Independent
  full audit reconciles every raw occurrence to Parquet and proves the captured
  windows equal the pending physical union minus the density pilot.
  `FULL_CAPTURE_INDEPENDENT_AUDIT.json` in the normalized root. Captured known-
  candidate windows, not realized paths or admitted inputs.
- [x] **ETFE-0.dated-policy:** User-selected v1 policy applied to fresh inputs:
  deliverable economics (452,342 admitted, 43,720 zero-multiplier overrides,
  5 adjusted excluded), first-seen availability, provider-calendar settlement
  with SEC-rule cross-check (one declared exception), next-session action
  knowledge, QQQ payable from Invesco, 2024-01-18 start and VOO re-warm. All
  227,529 exact-window candidate rows are available by entry start. Independent
  audit and 7 tests pass. [Policy](docs/specs/ETFE_DATED_INPUT_POLICY_20261006.md).
- [x] **ETFE-0.exercise-reference / quote-size:** User-selected closing-auction
  reference captured fresh (1,487 expiry sessions, three yearly roots); v2
  extraction resolves 1,486 (QQQ 2026-08-20 unresolved), strict $0.01 rule with
  330 reported pins, independent recomputation matches. Quote sizes ×100 before
  2025-11-03, shares after (verified step change).
  [Policy](docs/specs/ETFE_DATED_INPUT_POLICY_20261006.md).
- [x] **ETFE-1.existence-census / selection-v2:** Fresh daily-bar existence for
  439,606 contracts (5,162 GETs, 3.5M rows); selection v2 picks a contract for
  6,650,729 of 6,993,352 decision clocks (95.1%; VOO about 21%), with weekly
  targets 2/4 admitted for SPY/QQQ.
  [Census](docs/specs/ETFE_EXISTENCE_CENSUS_20261006.md).
- [x] **ETFE-1.envelope-capture:** Bars-only envelope. 1,381 option minute-bar
  jobs / 40,646,087 bars and 2,712 SIP quote windows / 45,954,878 quotes
  (expiry ITM checks and liquidation opens) captured, normalized and
  independently reconciled. 13,580 roll legs included. Option trades not captured
  (user). [Envelope](docs/specs/ETFE_ENVELOPE_CAPTURE_20261006.md).
- [x] **ETFE-3.label-kernel (baseline):** `nn_meta/etfe/label_kernel.py` labels
  all 6,650,729 decision-clock rows in ~2 min (15 µs/row): 2,624,443 settled,
  3,257,346 size-ineligible (1% participation), 756,738 unfilled, 5,598 input,
  2,825 funding, 3,779 censored. Exact parity with the per-second `Scheduler` on
  all six fixture tapes; the independent audit reconciles 2,099,457 filled
  entries against raw bars. r0 was rejected (fused cost factor rounded
  differently on half-cent boundaries); r1 mirrors the reference operation order.
  VOO yields only 18 settled rows. r2 adds the OCC Jan 9, 2025 expiry override,
  post-end censoring and a liquidation completion fix: 2,625,092 settled, 147
  input-unresolved. Training scope: SPY/QQQ (user).
- [x] **ETFE-3.label-stress:** All 27 declared profiles
  (`etfe-label-stress-20261007-r1`). The baseline profile equals r2 row for row
  (6,650,729 rows, 0 mismatches). Pooled settled R: baseline SPY +0.30% / QQQ
  +0.11%; cost x2 about 0 to −0.2%; x3 −0.3 to −0.5%; participation 0.1% −1.1% /
  −2.6%; combined −3.8% / −7.0%; bar-removal profiles robust. r0 was rejected:
  an exit at the entry clock did not block the entry (the reference latches
  strategy_off first), which distorted the lag-60 profile.
- [x] **ETFE-2.features (v1):** 221 values + 221 masks for all 6,589,460
  SPY/QQQ decision-clock rows (`etfe-features-v1-20261007-r0`, 723 MB), per the
  [feature amendment](docs/specs/ETFE_FEATURE_AMENDMENT_20261007.md). 147 fields
  are >= 95% filled; declared masks: 54 param, 5 trade-only; structural: 6 ICT
  overnight-session fields. Option context comes from census daily bars (the
  ETFE-1.context capture is no longer needed for run one). The independent audit
  passes: census, masks, prefix causality at two cuts per scope, and sampled
  recomputation. Peak RSS 8.3–8.5 GiB per ticker process; 1-minute scopes about
  12.5 min.
- [x] **ETFE-3.freeze / experiment v2:** Dataset v1 sealed (6,589,460 rows,
  2,625,074 labeled; manifest e09e564a…; verification passes) and experiment v2
  frozen (ecca0499…; 84 fits unchanged).
- [ ] **ETFE-4.pilot (training smoke):** one fold of GBT/NN fits to measure peak
  RAM and time, plus interrupted-restart recovery; then size workers.
- [ ] **ETFE-1.context:** Superseded for run one by census daily-bar context; Size and decide option-context (1–45 DTE) acquisition
  for the seven context fields; use a successor engine with a cached root-size
  counter (the current per-request guard slows large roots about 4×).
- [ ] **ETFE.history-boundary:** January 1–17 returned no bars for all 23,176
  discovered symbols in the January–March 4 expiry grid; January 18 09:30 ET is
  first observed for all three ETFs. Establish usable/complete coverage;
  pre-January intervals, longer expiries and omitted historical listings remain
  outside this proof. January stock padding is not an admitted research start.
- [ ] **ETFE-1.VOO-gaps:** Rechecked all twelve missing VOO SIP minutes with
  neighboring-minute controls; none of the requested minutes were returned.
  Keep the affected VOO recursive signal suffix explicitly unresolved pending
  valid evidence that restores state under the declared indicator contract.
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
