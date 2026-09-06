# TODO — TradingView expansion and corrected research

Reconciled September 5, 2026. The user authorized starting all six workstreams
below with multiple agents. Work on `main` in the primary checkout;
[HANDOFF](HANDOFF.md) records completed milestones. Dependencies control when
each later stage can run.

The audit repairs are implemented and merged: **51 main findings and four
additional concerns**. First TradingView/readiness batch integration passed
**790 tests and 18 subtests** (planning baseline: 642). Corrected research results
and a new production rollout remain outstanding.
[First-batch evidence](docs/reviews/2026-09-05-readiness-milestone.md).

The build contract is `2026-09-05-causal-v2`. Preserve pre-audit freezes,
211/441 paused v6 partials, rows, marks and bundles as historical artifacts.
Create fresh campaign outputs; old v6 resume/merge commands and old v5 reuse
are superseded. Never relabel old artifacts to pass validation. Source-only
deployment can stop existing experts because loaders reject stale bundles.
[Migration requirements](docs/reviews/2026-09-05-remediation.md).

## 1. Reconcile the active checklist

- [x] Separate implemented audit repairs and completed prior features from
  open work; replace contradictory active instructions with this checklist.
- [x] Preserve previous task/roadmap/reference text in
  [handoff-history](handoff-history/); retain decision and experiment logs.
- [x] Correct v6 notes: **v6 keeps v5's window**; the archive audit identified
  **15 weekly-expiry names**, not 25.
- [x] Reconcile the first implementation milestone with TODO and HANDOFF.

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
  remain unported; the five other selected scripts remain source-pinned.
- [x] Add the verified source/adaptation/runtime registry. No active-pool
  admission until exported TradingView fixture and input-contract checks pass.
- [ ] Define outputs and mechanical entry/exit rules separately. Resolve
  existing Keltner breakout/mean-reversion and BBW rolling-minimum/percentile
  semantics before freezing the expanded pool.
- [ ] Implement the spec's dependency order: smoothing/trend state;
  confirmed structure/sessions; composite setups/resolved statistics;
  volume profiles/higher timeframes; footprint engines with explicit data needs.
- [ ] Verify Pine value/event parity, prefix invariance, batch/incremental
  equivalence and all four sweep/frozen signal frames. Delayed pivots appear
  at confirmation; outcomes enter statistics only when resolved.
- [ ] Integrate admitted families/features, scoped grids and provenance.
  Keep unsupported footprint/intrabar modes visibly pending until their
  historical/live twin passes [REALTIME_SPEC](docs/specs/REALTIME_SPEC.md).
- [x] Run the complete regression suite for the first implementation batch.
- [ ] Finalize generation boundaries and revalidate after full pool integration.

## 3. Prepare the corrected research campaign

- [x] Find/fix the downloader's chunk-end omission and add regression tests.
- [x] Restore/verify the SPY raw-history pilot (38 MiB); all 6,448 overlapping
  2025 resampled OHLCV bars match. Full-universe repair remains open.
- [x] Add isolated named campaign paths, stable shard merge, immutable input/
  source/runtime fingerprints and fail-closed local stage launchers.
- [x] Verify the launcher refuses five current underlying gaps despite the
  old one-direction preflight passing (500 option days versus 495 underlying).
- [ ] Inventory raw history/backups: compaction losses, year-end underlying
  holes, renames, date coverage and PIT monthlies. Restore missing observations
  from surviving sources where available.
- [ ] Preserve/checksum historical artifacts; allocate fresh freeze,
  checkpoint, row, mark, report and model paths under the current contract.
- [ ] Replace old additive-only v6 launcher assumptions with a full corrected
  freeze plan. Reuse requires compatible newly validated artifacts and matching
  provenance, never pre-audit v5.
- [ ] Select representative pilots, resource limits and run manifests.
  Keep v6's current v5 window; deeper windows belong to v7.
- [x] Validate local launchers and failure/resume behavior before heavy work.
  Rebuild/verify a Batch image only if cloud acceleration is used.

## 4. Rebuild and compare fairly

Start after admitted TradingView source/data contracts and campaign preflight.
Use the home box first; cloud acceleration needs a measured workload,
VM-hour budget and explicit job IDs.

- [ ] Refreeze affected baseline and expanded pools on causal inputs.
- [ ] Build matching per-symbol/family rows, complete marks and provenance;
  assemble with PIT membership and verify coverage/fingerprints.
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

Actual read-only inspection found pre-audit server commit `9351d01`, four
expert crons and both feed processes. Full-session parity remains pending.
September 8, 2026 is Tuesday. [Evidence](docs/reviews/2026-09-05-readiness-milestone.md).

- [x] Inspect deployed commit, cron, processes, logs and feed state/timestamps
  without changing alert/digest state. Current-contract bundle rollout remains open.
- [ ] Verify closed/current bars, complete stream buckets, current-session
  REST fallback, restart/backfill and stale/forming-bar rejection through a
  market session; compare signal timestamps, not process/pass counts.
- [x] Confirm :01/:02/:03 staggering and workers against observed server state.
  Preserve bracketed `pgrep`/`pkill` patterns.
- [ ] Verify current-contract bundles and isolated previews, then prepare a
  coordinated source/bundle rollout with compatible rollback inputs.
- [x] Check both user/system timers: StockTwits/cache-backup absent; user
  deadman active. Restore collectors/backups and audit FA/PIT jobs next.
- [ ] Review obsolete Artifact Registry tags against retained/reproducible
  campaign images before cleanup.

## 6. Advance execution and broader research

Independent implementation can proceed alongside earlier work. A changed
shared alert format still needs the user's go/no-go on a concrete preview;
preparing resolver/calculations is authorized.

- [x] Prepare/test a pure captured-chain contract preview with chronology,
  OCC/quote/delta checks, deterministic selection and explicit unverified
  deliverables. Live fetching, reference metadata and offline parity remain open.
- [ ] Build contract resolution, quote/greeks retrieval, liquidity checks and
  OPRA watch registration. Specify matching offline selection before changing
  a model's live decision semantics.
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
