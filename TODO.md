## September 16 user correction: finish the build, stop expanding acquisition

- [x] Complete existing full listed-identity capture and build the identity/security-history panels; 1,912 tests +18 subtests pass.
- [x] End broad acquisition expansion. All jobs are terminal; quota reservations are empty. 250 GB is a cap, never a target.
- [ ] Connect captured history, actions, sectors and context to the full causal feature/proposal build; preserve unresolved cases explicitly.
- [ ] Generate actual proposal-driven quote/trade demand and obtain only specifically missing required inputs.
- [ ] Finish execution/labels, bounded assembly and the full training runner; validate integrated correctness, memory and recovery.
- [ ] Pass training readiness and alert the user. No training launched yet.

## September 14–15: V7, March 15, 2022 through September 14, 2026

User superseded the earlier dates: V7 starts March 15, 2022 (birthday) and
ends September 14, 2026. March 8–14 are removed from active working inputs.
Alpaca stocks and Massive options remain the sources. Full feature suite retained. New
chronological train/evaluation splits must be frozen before training. The old
15-minute short-DTE campaign is paused; its main timer is disabled. See
[scope and readiness requirements](docs/specs/MULTITIMEFRAME_RESEARCH.md) and
[session review](docs/reviews/2026-09-14-v6-dashboard-and-multitimeframe-preparation.md).

- [x] Add separate V7 plan and completed-session cutoff; do not inherit V6 training dates.
- [ ] Rebuild full-history PIT universe/calendar and audit every feature dependency from March 2022.
- [x] Enumerate all registered parameters across 1/5/15/30 minutes with stable identities; planning catalog only.
- [x] Inventory stock backups by year against the 449-symbol scope; presence is not coverage.
- [ ] Restore/repair and validate minute stock data, raw/adjusted basis, PIT aliases and session coverage.
- [ ] Implement bounded full-variant vectorization and causal per-timeframe features/context; verify each strategy.
- [ ] Freeze complete MASSIVE quote coverage for entries, minute marks, exits and rolls.
- [ ] Implement/audit quote execution, costs, timing, expiry and shared portfolio accounting.
- [ ] Bind all dates, parameters, source/runtime/data hashes and evaluation rules in a new version.
- [ ] Profile stages and benchmark Arrow IPC/Polars against existing Parquet/NumPy maps; prioritize shared computation, bounded assembly and thread limits.
- [ ] Pass representative end-to-end/resource pilots and the complete-universe readiness gate.
- [ ] Only then launch the new full build with four bounded processes, audit and train.

Current pre-freeze audit ([full inventory and ordered gates](docs/reviews/2026-09-15-v7-feature-and-freeze-audit.md)):

- [x] Reconcile roadmap, training notes and all 222 columns; preserve all 13 TradingView scopes and all 10 tick features. Separate explicitly deferred research from this run.
- [ ] Rebuild PIT membership with explicit March 8–14 exclusion/lookback policy, retaining the full exchange calendar; validate lifecycle/session aliases and frozen dated sectors.
- [ ] Integrate the tested causal-price prototype with evidence for splits, dividends, combined actions and spin-offs, contemporaneous tick units and cross-action stops.
- [ ] Build daily/market context for every eligible security; record initial warmup missingness and first eligible observations after March 15.
- [x] Bind selected-contract semantics: actual calendar DTE / 9 and log(strike/raw spot), with fresh causal raw spot and versioned factorized stores.
- [ ] Connect bounded full-history rows/labels/marks to V7 training; measure binned-dataset memory and recovery alongside V6.
- [ ] Declare V7 model/objective/seed/weight/calibration trials before outcomes; retain baseline comparisons, finite NN/GBT checks and multiple-testing diagnostics.
- [ ] Implement one executable full-universe launch gate and rerun new-window integrated pilots, including sparse markets, actions, rolls and funded expiry.

The completed items below describe historical component evidence. Older dated
checkboxes later in this file do not substitute for these current V7 gates.

September 15 implementation progress ([evidence](docs/reviews/2026-09-15-v7-readiness-implementation.md)):

- [x] Audit all 2,712 base raw/adjusted stock pairs and 1,429 option daily files; preserve unresolved listing/vintage gaps.
- [x] Capture 69 monthly security masters; identify ticker reuse and replace static-alias ranking with explicit security identities.
- [x] Implement all 20 strategy-family adapters and run all 11,268 variants in the real SPY four-timeframe warmup pilot.
- [x] Implement 13-source V7 projections, minute opening-range/VWAP context and bounded observed-quote archive/cash ledger.
- [x] Declare chronological folds and quote policy; pass initial real observed-fill/minute-mark/cash replay.
- [x] Complete the 167-root historical supplement and hardened through-cutoff base audit.
- [x] Complete SPY quote/contract capture, 222-column rows, observed rolls and shared-portfolio pilots.
- [x] Pass all-variant integrated pilots and full-chain no-swap/equality checks; bind source/runtime/input manifests.
- [x] Capture both providers' corporate-action histories and audit all 3,714 price pairs; repair GS/NOW/USO inconsistencies.
- [x] Resolve the seven reviewed identity dates without changing membership/ranks/scores; reconcile 67 rename sessions and capture GAP.
- [x] Implement bounded factorized rows and fold-indexed LightGBM Sequence; verify exact reconstruction and prediction equivalence.
- [x] Complete the 598-name quote-demand planning envelope with the verified vectorized selector.
- [x] Move V7 start to March 15, 2022; remove March 8–14 from active working inputs and retire the March 8 repair task.
- [x] Create the new plan/evaluation amendment and filtered stock/options inputs; rebuild the observed contract catalog and rerun the dated coverage inventory.
- [ ] Rebuild PIT membership and downstream features/demand/pilots for the new scope; complete lifecycle/alias/sector and causal adjustment admission.
- [x] Record latest expiry choice: funded physical exercise and stock delivery with observed liquidation prices; supersedes unresolved-only.
- [ ] Implement and validate the physical-exercise/stock ledger, shared funding and share-delivery checks, dated settlement and Alpaca stock quote liquidation; retain unresolved fallback when prerequisites fail.
- [x] Confirm source split: existing Alpaca Pro for underlying stocks, Massive for options; stock-upgrade investigation superseded by user clarification.
- [ ] Finish dated option hours, enforce expiry admission in the full build, establish actual quote-demand feasibility and full capture under 250 GB.
- [ ] Complete full-history assembly/resource pilots and pass complete-universe readiness gates before freeze/build/training.

# TODO — TradingView expansion and corrected research

[GOALS](GOALS.md) records the September 10 baseline and year-end ≥7/10 targets.

- [ ] After v6 has run for one week and more current TODOs are completed, review
  the scorecard with operational and research evidence and choose the next priorities.

Reconciled September 6, 2026. The user authorized starting all six workstreams
below with multiple agents. Work on `main` in the primary checkout;
[HANDOFF](HANDOFF.md) records completed milestones. Dependencies control when
each later stage can run.

**User scope confirmed September 6:** the full v6 freeze/build must include
all thirteen selected TradingView indicator scopes and quote/trade features.
**Latest instruction:** defer the external TradingView comparison, keeping all
thirteen groups. The implemented opt-in unverified research contract records
that choice. Actual per-symbol context and complete historical tick coverage
remain required. The user selected Option 1, authorizing explicit local
calendar/VWAP research assumptions. Context is now sealed for all 453 symbols;
the request inventory and tick captures resumed after the user's reboot on
September 6 at 17:04 UTC. Active PIDs/logs and durable checkpoints are in
HANDOFF.md. All 453 tick stores and freeze shards are verified; the merged baseline has
449 eligible symbols and four skips. Build+assembly launched September 9 with
a four-worker target. All 449 eligible symbol builds completed; monolithic
assembly was OOM-killed September 12. Separately pinned continuation
`v6-train-20260912` completed assembly and objective comparisons. Replacement
`v6-train-20260912r2` reused those verified outputs and completed evaluation plus the 40-seed
GBT final ensemble on September 12. The configured research gate passed;
TradingView parity and model promotion remain outstanding. See the
[training review](docs/reviews/2026-09-12-v6-training.md).
The existing-family SPY/IBKR pilot is now stopped and preserved. Do not launch a full
universe freeze while those additions are still missing; complete their
historical coverage and feature integration first. External comparison is
deferred for this research run.

The audit repairs are implemented and merged: **51 main findings and four
additional concerns**. The final expanded integration suite passed **1,390 tests and
18 subtests**, including the planner and strict gate integration. All thirteen scoped TradingView ports and the full stock/context
repair are implemented; external Pine fixtures, corrected model results and a
new production rollout remain outstanding. Historical integration evidence is
retained in the [first-batch review](docs/reviews/2026-09-05-readiness-milestone.md).

The core contract is `2026-09-06-raw-spot-v3`; expanded v6 uses
`2026-09-06-tv13-option-ticks-v4` with a sealed input manifest. Preserve pre-audit freezes,
211/441 paused v6 partials, rows, marks and bundles as historical artifacts.
Create fresh campaign outputs; old v6 resume/merge commands and old v5 reuse
are superseded. Never relabel old artifacts to pass validation. Source-only
deployment can stop existing experts because loaders reject stale bundles.
[Migration requirements](docs/reviews/2026-09-05-remediation.md).

- [x] Resume remaining tick stores with four resource-budgeted symbol processes;
  preserve 181 completed stores, partition CPU affinity leaving two physical cores,
  retain 4 GiB available RAM guard and the 30-minute watcher. See HANDOFF for evidence.

- [x] Start an automatic two-hour fifth-worker freeze trial controller, with
  measured four-worker baseline and automatic return to four if rate does not
  improve or memory pressure rises. Handoff tracks draining/preflight/live status.

## 1. Reconcile the active checklist

- [x] Separate implemented audit repairs and completed prior features from
  open work; replace contradictory active instructions with this checklist.
- [x] Preserve previous task/roadmap/reference text in
  [handoff-history](handoff-history/); retain decision and experiment logs.
- [x] Correct v6 notes: **v6 keeps v5's window**; the archive audit identified
  **15 weekly-expiry names**, not 25.
- [x] Reconcile the first implementation milestone with TODO and HANDOFF.
- [x] Record the completed data repair and exact seal restoration after the
  aborted first pipeline pilot; retain its outputs as ineligible history.

Already implemented: per-underlying universe reads and sorted new derivations;
PIT membership; PBO reporting; magnitude/EV head; panel watchlist recording;
Keltner/BBW scaffolding; weekly DTE plumbing; streamed feeds and fresh REST
fallback. Historical tests/results do not waive new-campaign validation.

## 2. Finish the TradingView indicator work

Scope: the **ten highest-boost scripts across every exposed page of the
supplied general listing, plus three highest-boost Editors' Picks**. The
general listing contains 1,000 recent scripts across 42 pages, not the all-time
library; Editors' Picks contains 758 across 32 pages. Default to that literal
scope while the optional all-time clarification is unanswered. The result is
13 distinct indicators whose detail pages label them open source.
[Selection and acceptance plan](docs/specs/TRADINGVIEW_EXPANSION.md).

- [x] Inventory all pages, rank exact boost counts, check source access and
  preserve the [snapshot](docs/specs/tradingview-boost-snapshot-2026-09-05.json).
- [x] Pin thirteen exact Pine sources, versions, hashes, imports and license
  records. Attribution/defaults/input contracts live in adaptation manifests;
  unused transitive Footprint library acquisition remains documented pending.
- [x] Implement and locally test the first eight scoped ports: Gaussian,
  Fibonacci, Uptrick, RSI, ICT, Emre MSB, SR Channels and VWOB. Emre box arrays
  remain unported.
- [x] Add the remaining five scoped local ports: AMD, Setup Scanner,
  Structural Liquidity/POC, HTF Log-Regression Profile and Footprint geometry/
  supplied signed-volume modes. Native Footprint remains unsupported.
- [x] Add the verified source/adaptation/runtime registry. No active-pool
  admission until exported TradingView fixture and input-contract checks pass.
- [x] Separate scoped indicator outputs from mechanical entry/exit wrappers.
  Confirm existing [Keltner breakout and BBW rolling-minimum semantics](docs/specs/V6_KELTNER_BBW_SEMANTICS.md)
  and all four sweep/frozen outputs without changing formulas.
- [x] Implement local scopes in the spec's dependency order: smoothing/trend state;
  confirmed structure/sessions; composite setups/resolved statistics;
  volume profiles/higher timeframes; footprint engines with explicit data needs.
- [x] Add the [chart-export fixture workflow](docs/specs/TRADINGVIEW_FIXTURE_RUNBOOK.md),
  capture/input bindings and comparison reports. Synthetic test CSVs do not
  establish external Pine parity or admit a family.
- [ ] Verify Pine value/event parity, prefix invariance, batch/incremental
  equivalence and all four sweep/frozen signal frames. Delayed pivots appear
  at confirmation; outcomes enter statistics only when resolved.
- [x] Wire all thirteen feature scopes (96 columns), eight source-default
  directional families, typed Setup identities and ten tick columns behind
  strict input gates. No new families are externally admitted yet.
- [x] Bind actual field/proposal-event comparisons, instrumentation, terminal
  snapshots, missingness and transitive evidence hashes; draft harnesses remain
  uncompiled/unreviewed.
- [x] Add command-line capture-pack preparation and verification: current
  127-field/44-event checklist, unreviewed draft, retained comparison report,
  separate hash anchor and completion marker after evidence rechecks.
- [x] Add bounded split-harness generation for the three existing trend drafts,
  preserving original bytes and every observation while reducing added plots.
  Browser automation now uses the signed-in TradingView profile. The context
  helper compiled, but Essential Trial blocks CSV export; account export
  access and actual source-harness compilation remain pending.
- [ ] Obtain actual chart outputs/context, validate the full proposed source
  scope, and admit the sealed feature candidate. Unsupported native footprint/
  intrabar modes remain outside the scope.
- [x] Run the complete regression suite for the first implementation batch.
- [ ] Finalize generation boundaries and revalidate after full pool integration.

## 3. Prepare the corrected research campaign

- [x] Find/fix the downloader's chunk-end omission and add regression tests.
- [x] Restore/verify the SPY raw-history pilot (38 MiB); all 6,448 overlapping
  2025 resampled OHLCV bars match. The completed full repair is recorded below.
- [x] Add isolated named campaign paths, stable shard merge, immutable input/
  source/runtime fingerprints and fail-closed local stage launchers.
- [x] Verify the launcher rejects the five former underlying gaps despite the
  old one-direction preflight passing. Repaired data now has 500 option and
  500 underlying sessions in the pinned model window.
- [ ] Continue the backup/deeper-history inventory outside the repaired
  April 2024–August 2026 stock window, including compaction losses and missing
  FA/PIT monthlies; restore surviving observations where available.
- [x] Preserve/checksum the original cache and allocate fresh campaign freeze,
  checkpoint, row, mark, report and model paths under the current contract.
- [ ] Finish inventory/checksums of remaining historical research artifacts,
  including the preserved 211/441 paused v6 partials.
- [x] Replace old additive-only v6 launch assumptions with a full corrected
  freeze plan. Reuse requires compatible newly validated artifacts and matching
  provenance, never pre-audit v5.
- [x] Select SPY/IBKR and two workers for a bounded freeze/build/assemble pilot.
  Keep v6's current v5 window; deeper windows belong to v7.
- [x] Validate local launchers and failure/resume behavior before heavy work.
  Rebuild/verify a Batch image only if cloud acceleration is used.
- [x] Separate raw contemporaneous stock spot for OCC strike selection/IV
  from adjusted technical history; reject old price-basis data and surfaces.
- [x] Complete staged whole-universe stock repair: all **453 symbols** have
  fresh raw and all-adjusted histories with **6,887,003 identical timestamps**.
  Validate 602 stock sessions including warmup, issuer identities and early
  closes; retain explicit CLSK/SBET exceptions and partial intervals.
- [x] Retain the **5,214,222-contract all-observed universe** and all 500 option
  day files; rederive **33,597,149 option daily rows** and 266,905 surface rows
  using raw contemporaneous spot. Seal the candidate and verify original cache
  bytes. [Data evidence](docs/reviews/2026-09-06-data-repair.json).
- [x] Stop `raw-options-20260906` after its provider wrote derived contract
  files into the sealed candidate. Verify all 123,471 sealed payloads, preserve
  1,299 added files in campaign quarantine and restore the exact original seal.
  Its completed IBKR shard remains ineligible for reuse.
  [Restoration evidence](docs/reviews/2026-09-06-pilot-cache-restoration.json).
- [x] Independently review the separate writable provider-cache fix, including
  concurrent materialization and exact sealed-input preservation.
- [x] Launch replacement pilot `raw-options-20260906-r2` with locked exit markers,
  a recovery descriptor and two dynamically selected workers.
- [x] Preserve and stop core pilot `raw-options-20260906-r2` before expanded
  source integration: both freezes merged, IBKR completed 8,910 rows, SPY MA
  partial retained. All 123,711 original inputs/seal/runtime match. Assembly
  did not run. Recovery descriptor retired; nonzero stop status preserved.
- [x] Download a bounded Massive historical quote/trade pilot and capture
  raw nanosecond/provenance, complete pagination and storage/timing evidence.
- [x] Verify descriptive causal replay of the captured option ticks while
  preserving original capture bytes. [Replay evidence](docs/reviews/2026-09-06-option-tick-replay.json).
- [x] Share prior-date/PIT raw-moneyness selection between features and labels;
  bind explicit trade-condition policy and exact tick request/store identity.
- [x] Download and materialize a correctly selected v6 call/put sample: 17,814
  quotes and 648 reported trades, all ten features present, exact joins pass.
  Durable local store is under `nn_meta/option_tick_features/`.
- [x] Implement and independently review full pre-outcome request planning: all
  twenty families, exact TRAIN/full-window caps, weekly grids, prior-date raw
  selection and source/config/input hashes; no option outcomes or downloads.
- [ ] Execute full pre-outcome request planning from verified source/context,
  download/verify all required tick windows, and seal complete feature inputs.
- [ ] Validate the richer live condition/receipt adapter and full-session twin;
  run ablations. No predictive gain or production admission is established.

## 4. Rebuild and compare fairly

The existing configured v5/v6 pipeline can be piloted after data and runtime
preflight. Adding any of the thirteen new ports requires its external parity
and admission checks first. The stopped pilot tested the repaired core
pipeline. Expanded feature/selection/join code is implemented; actual source
comparisons, historical coverage and the sealed manifest remain prerequisites. Use the home box first; cloud acceleration needs a measured
workload, VM-hour budget and explicit job IDs.

- [x] Complete this expanded v6 campaign freeze on causal inputs (September 9).
  Other affected pools remain separate rebuild work.
- [x] At roughly 227/453 completed v6 freeze shards, prepare build/evaluation/
  training launchers; keep heavy downstream stages unlaunched until freeze
  completes. User is dedicating the home box to this work for the next week.
- [x] Build matching per-symbol/family rows, complete marks and provenance;
  assemble with PIT membership and verify coverage/fingerprints.
- [x] Add streamed assembly, vectorized mark checks, reusable prepared arrays,
  bounded seed processes, resumable final seeds and bounded ensemble scoring.
- [x] Add separate event-balanced classifier and downside-quantile experiments
  using existing labels, purged temporal evaluation and no auto-promotion.
- [x] Configure three post-freeze conditional folds without weakening the
  generator-horizon, exit-time purge or embargo checks.
- [x] Inspect continuation comparisons, walk-forward results and final gates.
  September 12 verdict: hold scanner promotion. All 20 NN runs have NaN loss;
  GBT remains promising. See the deployment review and matching test baselines.
- [ ] Fix all-missing NN feature handling and finite-value guards; rerun family
  selection in a fresh scope, preserving the original failed training evidence.
- [ ] Replay fixed policies with executable quote/latency limits and stressed
  spreads/costs; compare to the frozen baseline on the same marked ledger.
- [ ] Benchmark larger worker counts/GPU; evaluate ranking, learned contract
  selection/exits, broader event weighting, calibration/abstention and mature
  prospective FA. Dependencies are in the training review.
- [ ] Check deterministic reproduction with fixed seeds and exact inputs.
- [ ] Evaluate candidate and baseline on the same corrected cash/cost ledger:
  every roll fill, entry-bar loss, mark reconciliation and costs.
- [ ] Put validation/test after a global proposal generator's optimization
  horizon and label results conditional. End-to-end nested claims require
  fold-local proposal refreezing/rebuilds.
- [ ] Walk-forward select and finalize passing candidates only; preserve
  refusals, mark hashes, gate settings and source-spec fingerprints.
- [ ] Record corrected [EXPERIMENTS](docs/EXPERIMENTS.md), retaining September 4
  gate-selection history. Fresh forward evidence remains necessary.

## 5. Verify operational readiness alongside research

September 6 read-only follow-up: [production alert review](docs/reviews/2026-09-06-production-alert-review.md).
All four ensembles load/score and Telegram/SIP REST access work. The separate
compatibility patch a315034 is now deployed, preserving old models.
[Deployment evidence](docs/reviews/2026-09-06-production-ops-deployment.md).
v5 refresh resumed under memory monitoring; completion and live-session
acceptance remain pending.
- [x] September 8 server review: eight operational findings fixed and deployed on
  the compatibility branch (option feed idle gate + contract registration,
  recorded Sunday refresh at 6 workers, alive-minute bucket tolerance,
  session-aware staleness, no-bars skips with weekly recheck, one top-five slot
  per symbol+side, WARNING-only backtester.log + quiet cron console + logrotate,
  heartbeat escalations) plus anchored feed watchdogs.
  [Review](docs/reviews/2026-09-08-server-ops-fixes.md).
- [x] Repair/complete v5 server surface refresh with a measured memory budget:
  `scripts/run_refresh.sh v5` (6 workers, recorded exit status); the Sep 8 rerun
  was still downloading at handoff — confirm `surfaces: v5 0d` in the heartbeat.
- [x] Deploy compatible production freshness, final-close/calendar and legacy
  outbox fixes, with separate experimental + confirmed EOD panel.
- [ ] Validate market-session behavior and EOD timing/coverage before declaring
  end-to-end readiness.


Actual read-only inspection found pre-audit server commit `9351d01`, four
expert crons and both feed processes. Full-session parity remains pending.
September 8, 2026 is Tuesday. [Evidence](docs/reviews/2026-09-05-readiness-milestone.md).

- [x] Inspect deployed commit, cron, processes, logs and feed state/timestamps
  without changing alert/digest state. Current-contract bundle rollout remains open.
- [ ] Verify closed/current bars, complete stream buckets, current-session
  REST fallback, restart/backfill and stale/forming-bar rejection through a
  market session; compare signal timestamps, not process/pass counts.
  Sep 8 session observed: ~190 names/cycle fell to REST on single quiet minutes
  and the 09:31 pass failed all 441 v5 names as stale after the holiday — both
  fixed that evening; re-observe a full session on the new code.
- [x] Confirm :01/:02/:03 staggering and workers against observed server state.
  Bracketed `pgrep`/`pkill` patterns are NOT sufficient on the watchdog lines
  (they self-match the restart command); anchored `feeds\.x$` is installed.
- [x] Add v6 expert identity/campaign bundle paths, frozen weekly DTE matching,
  explicit stream campaign universes and captured session-calendar handling.
- [x] Add opt-in OPRA quote/trade recording with exact decoded timestamps,
  receipt provenance, bounded contract admission and visible capture failures.
- [ ] Verify current-contract bundles and isolated previews, then prepare a
  coordinated source/bundle rollout with compatible rollback inputs.
- [x] Check both user/system timers: StockTwits/cache-backup absent; user
  deadman active.
- [ ] Restore collectors/backups and audit FA/PIT jobs on the home box.
- [ ] Review obsolete Artifact Registry tags against retained/reproducible
  campaign images before cleanup.

## 6. Advance execution and broader research

Independent implementation can proceed alongside earlier work. A changed
shared alert format still needs the user's go/no-go on a concrete preview;
preparing resolver/calculations is authorized.

- [x] Prepare/test a pure captured-chain contract preview with chronology,
  OCC/quote/delta checks, deterministic selection and explicit unverified
  deliverables. Live fetching, reference metadata and offline parity remain open.
- [x] Contract resolution to a listed OCC symbol and OPRA watch registration
  from the alert path (`nn_meta/live/feeds/contracts.py`, ops branch) — the
  quote stream now has something to stream. Advisory only; alert text and
  model decisions unchanged.
- [ ] Quote/greeks retrieval, liquidity checks and quote-aware alert text.
  Specify matching offline selection before changing a model's live decision
  semantics.
- [ ] Prepare quote-verified entry/exit/roll accounting and a sampled spread
  model. Distinguish OHLCV from observed bid/ask results; document any
  proposed eligibility-gate change before adoption.
- [ ] Extend minute/day/trade history and PIT/surface coverage for v7 and SPX0's
  2022 bear-regime investigation. Massive Advanced has landed; completeness,
  costed selection and parity remain.
- [ ] Design the Alpaca **paper** execution seat after resolver/quotes:
  sizing, exits/rolls, reconciliation and a defined forward record.
- [ ] Automate prospective FA/PIT monthlies on the home box with capture
  cutoffs and immutable cohorts. The August FA monthly is contaminated
  historical evidence: **zero clean prospective monthlies** toward graduation,
  which requires at least three corrected frozen cohorts tracked forward.
- [ ] Add FA digest/fundamental overlays and evaluate Alpaca news/screener
  inputs with deduplication and explicit measurement windows.
- [ ] Continue volatility features and HAR-RV/GARCH comparison; a sequence
  model must improve OOS results per regime before admission.
- [ ] Revisit SPX0 after corrected deeper-data/accounting checks. Four prior
  rounds established no seat; retain bounded vertical mechanics.
- [ ] Queue stacking after validated panel outputs; RL sizing/exits stay last.
  DD-braked alerts are refused until sizing/execution can enforce the policy.

History: [previous TODO](handoff-history/TODO-2026-09-05-before-checklist-reconciliation.md),
[full-day handoff](handoff-history/HANDOFF-2026-09-05-wipe-restore-v5-ladder-feeds.md),
[DECISIONS](docs/DECISIONS.md), [EXPERIMENTS](docs/EXPERIMENTS.md).

## September 12 monitoring and report delivery

- [x] Correct the watcher to follow the explicit training continuation and recognize supervisor/seed stages.
- [x] Verify successful evaluation and final ensemble completion; preserve original failed runs.
- [x] Publish the complete v6 training summary and V2/V3/V3.1/V4/V5 archives in the private dashboard Training tab, with comparable tables and provenance.
- [x] Disable Telegram delivery for this watcher; keep summaries in the dashboard.

## September 15 V7 download/performance checkpoint

- [x] Start four-process V7 stock-minute and option aggregate acquisition under the user-approved 250 GB cap, with durable receipts and reboot-enabled service.
- [x] Install and benchmark Arrow IPC, Polars and Zarr; implement shared MA signal computation, bounded immutable storage and quote-request union/reuse pilots.
- [x] Validate 1,646 tests plus 18 subtests and real storage/working-set/quote capture pilots. See current HANDOFF and September 15 download/performance review.
- [x] Check current V6 paper producer, input refresh scheduling, relay, server delivery and dashboard freshness. Overnight check: 25 cycles, 8 sent notices, fresh relay; morning refresh/market-session acceptance pending. [Evidence](docs/reviews/2026-09-15-v6-paper-health.md).
- [x] Finish scoped documentation/commit/push for V7 acquisition and performance files.
- [ ] Complete V7 integrated admission: adapters and the full schema are implemented, but full-universe causal inputs, physical expiry, quote coverage, training integration and resource gates remain open (see current checklist above).
- [x] Verify SPY 2022 raw/adjusted receipt hashes and regular-session minute presence: matching timestamps, 251 sessions, 97,710 minutes, zero missing; full-universe/vintage audit remains open.

## September 15 market-session incident and V7 admission

- [x] Diagnose V6 stale context: all three morning refreshes hit missing September 14 MASSIVE minute object.
- [x] Install lightweight provider-availability retry timer without changing the activated inference runtime; 1,651 tests +18 subtests pass.
- [ ] Observe provider file availability, successful V6 refresh and next accepted live paper cycle/delivery; ordinary strategy exits are also blocked until context recovers.
- [x] Inventory completed V7 base acquisition: 8,282/8,284, 52.516 GB; 270 observed-empty stock captures require audit.
- [x] Capture September 14 option day/minute files after publication; base acquisition reached 8,284/8,284. The preceding 8,282 count is the historical incident checkpoint.
- [ ] Complete the ordered [V7 readiness gates](docs/reviews/2026-09-15-v7-feature-and-freeze-audit.md) before full freeze/build/training.

## September 15 V7 preparation implementation continuation

- [x] Rebuild PIT membership on filtered inputs with calendar-preserving deletion/lookback policy: 597 tickers, 595 identities; rerun eligible-session coverage.
- [x] Replace legacy DTE/moneyness placeholders with selected-contract semantics; version factorized stores and preserve initial missing daily warmup.
- [x] Implement and synthetically test shared funded physical-expiry ledger, stock inventory/settlement and extended portfolio horizons.
- [x] Add executable fail-closed full-universe evidence aggregator; current result rejects missing stage evidence.
- [ ] Resolve 122 zero-session lifecycle cases, dated sectors and held-position deliverables; finish causal price/action evidence and all-security daily context.
- [ ] Supply the physical context/receipt adapters, official references, settlement calendar and Alpaca stock quote capture; pass real shared expiry replays.
- [ ] Complete actual option quote/trade demand/capture, full-history assembly/training trials and resource pilots; pass every readiness stage before launch.

See [training preparation](docs/reviews/2026-09-15-v7-training-preparation.md).

## September 16 V7 lifecycle continuation

- [x] Explain 121/122 lifecycle zero sessions in a separately bound retrospective review; keep execution/PIT admission blocked and preserve VERU as unresolved.
- [x] Add and test official cash-merger expiry settlement and exact OCC prior-day reference exceptions; real evidence adapters and successor data remain open.

Evidence: [lifecycle preparation](docs/reviews/2026-09-16-v7-lifecycle-preparation.md).

## September 16 V7 no-OTC scope

- [x] Apply user-directed BBBY/FRC/REV/SI issuer exclusions, preserve ranks/scores, bind exact 593-ticker plan and readiness guards.
- [x] Explain VERU halt from captured original news; all 59 remaining active zero sessions have retrospective causes. Execution admission remains open.
- [x] Complete 1,047 Alpaca news queries; verify 256/4,967 original dividend amounts, retaining 4,711 unverified events.
- [x] Add tested immutable multi-shard fold selection and bounded training reads; full-history integration/resource checks remain open.
- [ ] Complete causal prices, dated sectors/lifecycle execution, daily context, quotes, physical adapters, full assembly/trials and integrated resource gates.

Evidence: [no-OTC preparation](docs/reviews/2026-09-16-v7-no-otc-preparation.md).

## September 16 V7 dated sectors and training input continuation

- [x] Capture missing prior-date references and freeze identity-bound sector records for all 339,640 eligible sessions, preserving explicit unknowns and all nine fields.
- [x] Consume dated sectors in feature rows with source/clock provenance and bind the frozen store in active inputs.
- [x] Implement bounded train-only preprocessing, exact disk-based return quantiles, finite checks and verified fold/preprocessing resumption.
- [ ] Finish full-history feature/data/execution integration, runnable model trials and measured binned-memory/resource gates; component coverage is not readiness.

Evidence: [sectors and training inputs](docs/reviews/2026-09-16-v7-sectors-training-inputs.md).

## September 16 causal-feature checkpoint and recurring V6 error

- [x] Integrate causal action epochs into all TV/technical features and bounded strategy proposal batches; retain raw execution and cross-action stops.
- [x] Verify a real AAPL dividend pilot across all 11,268 variants and four timeframes: 757,465 proposals; full suite 1,786 tests plus 18 subtests passed.
- [x] Capture original AAPL publication/identity evidence and partial official settlement documents; preserve four DTCC 404 failures as unfinished work.
- [x] Diagnose September 16 V6 pending-quote errors and SEDG exit; user directed leaving V6 unchanged and continuing V7. See September 16 pending-exits review.
- [ ] Complete remaining V7 full-history, action, quote, physical settlement, trial and resource evidence; V7 is not ready to train.

Evidence: [causal feature pilot and resume notes](docs/reviews/2026-09-16-v7-causal-feature-pilot.md).

## September 16 V7 stock quotes and settlement events

- [x] Implement receipt-bound Alpaca SIP stock quote capture/replay and dated size conversion; verify actual AAPL 20,628-quote pilot.
- [x] Correct settlement counting for covered stock trading dates on bank holidays; full suite 1,804 tests +18 subtests.
- [ ] Resolve official historical settlement calendars and complete funded observed physical replay; captured conflicting/mutable documents are not admission.
- [ ] Connect bounded folds and train-only preprocessing to runnable predeclared trials, full-history assembly and resource gates.

Evidence: [stock quotes and settlement](docs/reviews/2026-09-16-v7-stock-quotes.md).

## September 16 V7 executable model components

- [x] Predeclare 21 initial constant/GBT/NN objective/seed trials and connect bounded folds to actual fitting, immutable attempts, finite checks, model reload parity and verified resumption.
- [x] Verify validation-label independence and deterministic NN/GBT fits for all three objectives; full suite 1,813 tests +18 subtests.
- [ ] Integrate complete historical folds, full campaign runner, portfolio baselines, calibration/threshold declarations, multiple-testing and measured resource gates. Initial uncalibrated component trials do not pass full readiness.

Evidence: [runnable model pilots](docs/reviews/2026-09-16-v7-model-trials.md).

## September 16 V7 full raw daily stock preparation

- [x] Build all 2,966 symbol/year raw daily shards and reconcile all 339,640 eligible sessions, 591 identities and 67 exact-date aliases; retain 59 missing sessions.
- [x] Verify all joined prices/clocks and exact completed resumption; full suite 1,817 tests +18 subtests.
- [ ] Apply causal actions and full-security option surfaces, market/sector context and warmup reporting; raw facts alone do not complete daily-context admission.
- [ ] Measure isolated full-history resource behavior; host swap increased during this build/resume observation interval, so no no-swap gate passed.

Evidence: [full raw daily build](docs/reviews/2026-09-16-v7-full-stock-daily.md).

## September 16 full daily option-surface checkpoint

- [x] Build all 1,129 day surfaces and reconcile 669,749 raw ticker/date rows and all 339,640 eligible sessions; preserve missing observations.
- [x] Capture and verify an extended Alpaca exchange calendar, exact next-session availability, all-row lineage and 58 scalar parity checks; verify completed resumption.
- [ ] Complete causal daily returns, reviewed identity continuity, market/sector context and cold-start/warmup integration before admitting the daily-context stage.

Evidence: [full option-surface build](docs/reviews/2026-09-16-v7-full-surfaces.md).

## September 16 user-directed midpoint paper pricing

- [x] Use valid provider midpoint, otherwise bid/ask average, for V6/V7 simulated option entries/exits/rolls/marks; retain quotes and separate costs.
- [x] Verify copied-ledger transition and deploy V6 through Git with a bounded activation amendment; preserve closed history and realized equity.
- [x] Bind the V7 price-policy amendment in active scope/readiness; full suite 1,834 tests plus 18 subtests passed.
- [ ] Rebuild/reverify affected V7 derived bindings and option labels/marks/portfolios under midpoint pricing; no old ask/bid artifact relabeling.

Evidence: [midpoint pricing and deployment](docs/reviews/2026-09-16-midpoint-paper-pricing.md).

## September 16 V7 causal daily calculations and fresh parent bindings

- [x] Rebuild all 2,966 raw daily shards and 1,129 option-surface days under the midpoint active manifest; reconcile every value in both 339,640-row eligible tables.
- [x] Implement no-fill causal daily returns/context with reviewed action/span inputs, ten feature columns and warmup reporting; verify 40 actual AAPL sessions and all prefixes.
- [x] Run the full suite: 1,851 tests plus 18 subtests passed.
- [ ] Complete full-security identity/action evidence and market/sector integration, then admit daily context only with full-universe evidence.

Evidence: [causal daily calculations and rebuilt data](docs/reviews/2026-09-16-v7-causal-daily.md).

## September 16 full V7 corporate-action reconciliation

- [x] Reconcile all 10,380 captured action records for 594 active source/membership symbols; retain 5,030 exact-date groups and 213 complex events with original payload provenance.
- [x] Capture and visually verify the original DVN release; record the September 2024 $0.44 total-cash correction replacing the whole conflicting provider event group once.
- [x] Pass full regression: 1,863 tests plus 18 subtests.
- [ ] Resolve remaining publication, combined-event, amount/unit, no-event and identity-continuity evidence before applying the full inventory to causal features.

Evidence: [full action inventory and correction](docs/reviews/2026-09-16-v7-action-inventory.md).

## September 16 V7 full cash-publication evidence

- [x] Audit all 4,975 cash candidates against captured headlines/body text; match 286 actions with retained source/version provenance.
- [x] Capture/check all 18 Apple issuer announcements and corroborate every amount in dated news; retain 17 record/pay date checks and explicit vintage limits.
- [x] Pass full regression: 1,878 tests plus 18 subtests.
- [ ] Integrate publication evidence with complete-security action/no-event and identity review before full causal admission.

Evidence: [cash-publication review](docs/reviews/2026-09-16-v7-cash-publications.md).

## September 16 reviewed cash actions connected to causal returns

- [x] Compile reviewed whole event groups exactly once with prior Alpaca closes and adjacent eligible security identities; retain every unresolved provider record.
- [x] Apply all 18 reviewed Apple events and the Devon correction; verify 19 real event returns and 19 unchanged pre-event prefixes.
- [x] Pass full regression: 1,892 tests plus 18 subtests.
- [ ] Complete full-security continuity/no-event coverage and remaining action reviews before full daily admission.

Evidence: [cash-action integration](docs/reviews/2026-09-16-v7-cash-action-integration.md).

## September 16 full daily listed identities

- [x] Implement bounded full-window capture for the five listed exchanges, with shared quota and no OTC or stock-price requests.
- [x] Implement exact-day identity joins and continuity gaps; verify all 296 first-day eligible IDs.
- [x] Pass full regression: 1,903 tests plus 18 subtests.
- [ ] Finish all 5,645 capture shards, run the full raw/eligible identity join, review gaps and stitch aliases before daily admission.

Evidence and live process: [daily identity review](docs/reviews/2026-09-16-v7-daily-identities.md), HANDOFF.
