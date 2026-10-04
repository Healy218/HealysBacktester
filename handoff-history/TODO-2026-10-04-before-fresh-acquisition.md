# TODO — ETFE scope and data contract

**Selected work: ETFE — Exchange Traded Funds Expert. Current gate: ETFE-0.**
October 3 user direction selects a brand-new ETFE expert: exactly SPY, QQQ, VOO;
V7 strategy/timing specifications; 1/5/15-minute signals; Alpaca's earliest
options history through October 2, 2026, inclusive. No Massive quotes. [Specification](docs/specs/ETFE.md),
[roadmap](ROADMAP.md#etfe--exchange-traded-funds-expert), [handoff](HANDOFF.md).
October 3 follow-up authorized initial setup. Independent configuration/catalog
and bounded Alpaca diagnostics are implemented; input admission and expensive
campaigns remain gated. V7 archival is verified complete.
The October 3 first-run plan now covers the full build, dataset/experiment
freeze, finite training campaign, model freeze and clean-process expert proof.
[Authoritative sequence](ROADMAP.md#etfe-first-run-sequence),
[acceptance contract](docs/specs/ETFE_FIRST_RUN.md). This checklist contains only
the current contract phase; later tasks stay in ROADMAP until selected.

October 3: four component definitions are declared. H1/R1/R2/P1 source evidence
still blocks ETFE-0 closure. [Contract and blockers](docs/specs/ETFE_CONTRACT_20261003.md),
[verification](docs/reviews/2026-10-03-etfe-contract.md). No integrated pilot or
bulk campaign started.
October 3 pull diagnostics: 40 live GETs establish working historical trades/bars,
six-page equivalence and rejected historical-trade `feed` parameters. Dated OCC
and Nasdaq notices explain the adjusted QQQ strike and VOO hours change. Old
zero multipliers and exact history/feed provenance remain unresolved.
[Diagnosis](docs/reviews/2026-10-03-etfe-alpaca-pulls.md).

## Selected checklist — ETFE-0

- [x] **ETFE.setup:** Independent scope/configuration, 20-family 1/5/15-minute
  catalog (25,353 ticker/variant combinations), source-bound setup and integrity
  CLI. New artifacts only; 30 focused tests passed.
- [x] **ETFE.provider-probe:** Bounded read-only Alpaca checks completed; 43 live
  GETs, historical trades/bars observed for all three ETFs, quote endpoint 404.
  [Evidence and limits](docs/reviews/2026-10-03-etfe-setup.md).
- [x] **ETFE.quote-diagnosis:** Historical quote route is unsupported by Alpaca's
  public API. Official staff confirmation and 13 live controls establish working
  OPRA latest quotes for all three ETFs, working historical trades, and persistent
  historical-route 404s. [Diagnosis](docs/reviews/2026-10-03-etfe-quote-404.md).
- [x] **ETFE.pricing-basis:** User authorized trade/bar methodology and delegated
  VWAP versus high/low midpoint. Selected completed one-minute VWAP; implemented
  causal reference component and immutable successor setup. 46 focused tests
  passed. [Amendment](docs/specs/ETFE_VWAP_20261003.md).
- [x] **ETFE.pull-diagnosis:** Trade/bar reconciliation and six-page retrieval
  verified for the opening-minute sample. Historical trades reject `feed` with
  HTTP 400. Older metadata anomalies are isolated; QQQ adjustment and dated VOO
  transition explained. [Evidence](docs/reviews/2026-10-03-etfe-alpaca-pulls.md).

- [x] **ETFE.scope:** Record the accepted universe, timeframes and V7 inheritance;
  preserve later risk amendments and apply the subsequent ETFE VWAP pricing
  amendment; distinguish signal bars from option reference bars.
- [x] **ETFE.dates:** User confirmed Alpaca's earliest historical options
  availability through October 2, 2026, inclusive. This is a fixed window, not
  our recording start or a moving latest-session end.
- [ ] **ETFE.history-boundary:** Verify the exact first Alpaca options timestamp
  and UTC boundaries for the fixed October 2 end; record missing feature/bar/trade
  coverage separately rather than silently shortening the requested window.
  January 18, 2024 observations exist in all three ETFs; sample evidence does
  not establish the global first timestamp. Six new empty controls cover only
  three named contracts; H1 requires provider-global evidence. October 2 stock
  UTC hours and civil end `2026-10-03T04:00:00Z` exclusive are verified.
  Dated option-class hours remain separate under R2.
- [x] **ETFE-0.feature-map:** Inventory every inherited feature and all thirteen
  TV scopes. Declare retained/recomputed/replaced/unresolved fields, formulas,
  sources, available-at timestamps, windows, warmup and missingness. Define the
  new schema without fabricated quote values or silent loss of strategy scope.
  [Declared registry](docs/specs/ETFE_FEATURE_MAP_20261003.json): 221 values plus
  masks, thirteen pinned scopes. ETFE-2 implementation/admission remains open.
- [x] **ETFE-0.execution-contract:** Finish VWAP reference-to-simulated-fill
  semantics: size/participation limits, premium-stop denominator, timing, costs,
  missing held marks/exits, dated expiry/roll/physical delivery and end-boundary
  outcomes. Define pilot reconciliation and cost/lag/liquidity stress cases.
  [Declared execution](docs/specs/ETFE_EXECUTION_20261003.md); validation and
  dated R1/R2 inputs remain open.
- [x] **ETFE-0.experiment-contract:** Declare target definitions, temporal fold
  construction, full-horizon purging/ten-session embargo, train-only processing,
  finite GBT/NN/constant trial design, baselines and model/decision acceptance
  policy. Seal exact dates/parameters before outcome inspection/full fitting.
  [Declaration](docs/specs/ETFE_EXPERIMENT_20261003.json): three folds and 84
  required fits including final refits; dataset freeze comes later.
- [x] **ETFE-0.acquisition-design:** Derive required underlying/context, option
  bar/trade and dated-reference demand from those contracts; specify provenance,
  pagination, missingness/corrections and resumable partition inventory. Prepare
  the bounded ETFE-4.pilot workload and measurement/stop rules before bulk work.
  [Declared design](docs/specs/ETFE_ACQUISITION_20261003.md); source feasibility
  H1/R1/R2/P1 remains open and pilot execution has not begun.
- [ ] **ETFE.provider-contract:** Close ETFE-0.contract with the above versioned
  feature/execution/evaluation/acquisition contracts and feasible Alpaca sources,
  including feed, bar publication/revision assumptions and dated contract inputs.
  Four definitions are complete; **ETFE-0.contract is not closed**. Resolve H1
  (global floor), R1 (dated discovery/contract terms), R2 (class/expiry hours;
  VOO Nasdaq transition now sourced effective February 25, 2026), and P1
  (historical trade provenance; unsupported feed selector diagnosed), then seal an
  immutable contract successor.
  Full coverage is subsequently demonstrated under ETFE-1, not by this plan.
  The user-approved VWAP method supersedes historical bid/ask pricing and quote
  age/size guards; do not retry unsupported quote history. Alpaca-only policy,
  fixed dates and all strategy families remain. No Massive fallback or fabricated
  quote features; current expired-contract records are not historical as-of chains.

Later implementation, coverage, resource and training gates belong to the
[ETFE roadmap](ROADMAP.md#etfe--exchange-traded-funds-expert), not competing queues.
V7's paused scientific checklist is preserved in
[the pre-ETFE snapshot](handoff-history/TODO-2026-10-03-before-etfe.md);
V7 gates remain in ROADMAP with their prior completion boundaries intact.

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
