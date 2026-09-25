# TODO — V7 readiness, one deliverable at a time

## Parallel V6 Alpaca paper restart

- [x] Verify dedicated paper credentials, account eligibility and empty broker
  state; prepare a separate hash-verified V6 state with scanning and order
  submission disabled. Evidence: `docs/reviews/2026-09-24-v6-alpaca-paper-start.md`.
- [ ] Build a structured-event order bridge with stable event/order IDs,
  fresh mark-limit pricing, whole-contract buying-power sizing, broker
  reconciliation, fills and lifecycle handling. Preview future V6 events
  before activating paper submissions or retiring the old V6 timers. Keep
  simulator and broker P/L separate in Stonks.

## 7. Consolidated remaining TODOs before the goal is finished

- [x] **7-1. Complete usable identity/action histories under an agreed admission policy.**
  Completion evidence: Every relevant security/session/action has an explicit resolved treatment, consumed by the actual feature and held-position paths.

- [ ] **7-2. Produce complete causal daily/market context and full feature/proposal stores.**
  Completion evidence: Full 591-security census with correct availability,
  warmup, sectors and all 8,451 registered 5/15/30 variants per security; no
  substituted fixture inputs. The active run is managed by
  `healys-v7-catalog-build.service` and writes to
  `nn_meta/validation/v7-2-full-catalog-20260922-rebuild-5-15-30`, with 4
  outer security workers, one inner thread, compact-final enabled, and 1,773
  target stores. After the September 24 action/coverage recovery, 415 sealed
  securities are retained under an explicit equivalence manifest; four more
  sealed before the first controller exited. The corrected service verifies
  all admitted events before launch,
  fails on the first builder error, and does not automatically retry. The CLI
  and hourly observer remain bound to this output.

  September 24 audit found that the repaired coverage had omitted seven sealed
  reviewed renames and the unrelated-instrument treatments. A new reviewed
  coverage artifact restores admission for the eight affected securities;
  all other 583 securities retain identical admitted dates and action events.
  The earlier resumed service used that coverage for exactly the eight changed
  securities. It subsequently stopped on a loader guard at 425 completed
  securities. The original 1,773-store target remains open; the 45 formerly
  deferred securities received exact source review and bounded admission.

  September 24 follow-up: the first service stopped at 425 securities / 1,275
  stores on a VMW eligible-source guard. The exact 45-security noncash review
  and nine additional listed-span restrictions are now sealed; the production
  loader guard was fixed only after workers stopped. All 166 unfinished
  securities pass the real loader under the final coverage. The 415 reused
  and ten newly sealed securities passed the catalog receipt audit; two
  shortest histories also passed actual five-minute store builds. The revised
  unit passed a full 166/166 production-loader preflight and resumed actual
  workers at 18:18 CDT. At 18:21 CDT it had 426/591 securities and
  1,281/1,773 proposal stores, with four active workers and no input blocks.
  See
  [the 45-security repair audit](docs/reviews/2026-09-24-v7-last45-repair.md).

  The current run is the 7-2 build execution, not completion evidence yet.
  After it seals, verify every store, source binding, catalog census, compact
  footprint, worker/restart receipts and the 100 GiB reserve before checking
  this item. A read-only live preflight and resource sampler are implemented;
  the full technical audit is intentionally post-seal and does not by itself
  authorize 7-3. Historical 1-minute and pre-amendment 5/15/30 pilots remain
  historical only. See the [7-2/7-3 transition plan](docs/reviews/2026-09-20-v7-3-prep.md).

- [ ] **7-3. Complete actual option-path demand, dated hours/reference inputs and targeted captures.**
  Start only after 7-2's full-store verification. First derive proposal-driven
  entry demand for all completed securities from their 5/15/30 stores; then
  union bounded quote/trade windows, resolve dated option hours and standard
  contract references, and capture entry, mark, exit, roll and applicable
  stock-delivery windows. Preserve no-fresh/no-contract outcomes without
  fabricating requests. Completion evidence: the union covers every required
  option path within the 250 GB acquisition ceiling, with immutable request,
  capture and provider-failure receipts.

- [ ] **7-4. Finish integrated option/physical/shared-capital execution.**
  Completion evidence: Real captured cases and full accounting demonstrate midpoint stops, signals, expiry, funding, settlement and liquidation without invented outcomes.

- [ ] **7-5. Execute full data assembly and connect folds/trials.**
  Completion evidence: All required 221-column rows and outcome records reconcile; label horizons and fold purging are correct; the complete predeclared campaign is runnable.

- [ ] **7-6. Establish resource and recovery feasibility.**
  Completion evidence: Measured memory, disk, throughput, restart and coexistence evidence supports the proposed full run.

- [ ] **7-7. Pass the complete readiness gate and notify the user.**
  Completion evidence: An inspected full-scope report passes every required stage; only then may we claim V7 is ready.

- [ ] **8. Build and validate the AI artifact incubator; activate after V7 readiness.**
  Treat V5, V6, V7 and future V8 option artifacts as immutable AI candidates. At
  the configured market close, a master incubator should discover available
  `.tar.gz` artifacts, verify manifests and hashes, unpack each into an isolated
  sandbox, stream that day's paper forward-test data through every eligible
  artifact, and write one unified performance log plus per-artifact receipts.
  The first version must be read-only with respect to live alerts, broker state,
  and source artifacts; it must fail closed on missing manifests, incompatible
  contracts, duplicate artifact IDs, or insufficient forward data. Define the
  artifact manifest, compatibility matrix, resource/time budget, checkpoint and
  resume rules, comparable metrics, and retention policy before implementation.
  Design, local implementation and V5/V6 dry-run testing may begin now while
  V7 compiles. Do not activate the after-close production run, call a result a
  readiness result, or admit V7/FA artifacts until 7-2 through 7-7 gates are
  complete and the paper data boundary is explicitly approved.

  Incubator slices 1–6 are now implemented and smoke-validated for V5/V6:
  bounded resource/time budgets, dry-run and failure-path tests, a real Keras
  replay entrypoint wired to common metrics, and a checkpointed after-close
  service/timer committed but disabled by default. Replay correctly fails closed
  because the current V6 snapshot lacked the complete model feature matrix;
  immutable feature capture is now implemented as a strict publication CLI.
  `strat_volume` is derived only from the recorded strategy identity and is
  documented in the manifest. A full historical capture and 128-row real V6
  Keras replay smoke test pass under bounded threads/resources. The current
  2026-09-22 pass is now published against the actual live V6 GBT contract at
  `incubator/artifacts/v6-live-20260922/` with 304 rows and all 164 features.
  Its 40-member bundle loaded and produced 304 read-only predictions; scoring
  remains gated until candidate outcomes are joined. The older Keras bundle is
  retired from V6 daily use because its `prem_spot` contract does not match
  the live causal pass. V5 remains supported for its transition period.
  The exact-identity outcome joiner is implemented. The 2026-09-23 V6 join
  matured one explicit candidate-level `net_return` (DUOL/macd/30 DTE,
  -12.4581%); 303 of 304 rows remain pending, so no readiness or performance
  claim has been manufactured. The duplicate old Keras replay IDs are excluded
  from the curated registry; the live GBT campaign passed its bounded replay.
  The after-close runner now captures a dated V6 matrix from genuine pass
  parquets, routes V5/V6 artifacts to distinct sealed requests, isolates result
  directories, and writes date-scoped checkpoints, receipts and a unified
  performance log. The curated `incubator/artifacts/active/` bundles use each
  model's actual EV decision head; historical P(win)-labeled V6 smoke output
  is not performance evidence. Multi-row scoring and input-drift regressions
  pass. The read-only V6 closed-position exporter now seals current-pricing
  outcome evidence; 14 closed positions yielded only the one exact match to
  the 2026-09-22 candidate day. V5 scanner batch capture, daily assembly and
  scaler-mean replay are implemented locally. The V5 capture backport is now
  deployed on the existing server branch and its cron opt-in is enabled. The
  first nine genuine V5 passes sealed 3,555 distinct candidate identities and
  48 features with verified hashes/config binding as of 2026-09-24 15:47 UTC;
  the active day is still growing. Full-day census, approved local staging,
  exact-identity V5 outcomes and paper scoring remain open. A V6-origin V5
  compatibility smoke test is not V5 paper validation. The timer remains
  disabled and the service has no execution opt-in; production isolation and
  7-2–7-7 gates still block activation.

**7-1 is complete. 7-2 is currently running the systemd-managed full 5/15/30
compact catalog; do not begin 7-3 capture work until that run and its full
verification finish. The live V6 repair prerequisite was completed before this
run. V6 here means only the current home-hosted paper runtime; the abandoned
local short-DTE build is not part of this work. Items 7-3 through 7-7
are queued.**

- [x] **Dividend portion of 7-1:** 4,918 payment leaves across 4,854 price events;
  zero uncompiled dividend groups or missing held-cash treatments. All 10,428
  original records and 4,854 actual raw price boundaries reconcile. Final
  artifact: `v7-dividends-complete-20260918`. See the
  [completion audit and explicit model limits](docs/reviews/2026-09-18-v7-dividends-complete.md).
  At that checkpoint, the remaining 234 original records were noncash; the
  later 7-1 closure resolves them with explicit boundary exclusions.
September 17 progress: [reviewed source routing](docs/reviews/2026-09-17-v7-6-1-source-routing.md)
and [authorized ordinary-action reconstruction](docs/reviews/2026-09-17-v7-ordinary-action-admission.md),
followed by [exact-date share-class resolution](docs/reviews/2026-09-17-v7-share-class-identities.md).
The full history consumes FISV/FI routing and 27 reviewed identity dates; eligible
identity mismatches fell from 186 to 162. Targeted GAP and process-date-tail
repairs bring the rebuilt action set to 4,481 events, including all 18 SPY
distributions. The user also accepted the explicit no-event reconstruction
assumption; [coverage and targeted repairs](docs/reviews/2026-09-17-v7-action-coverage.md)
record its consumer integration. The full coverage grid admits 579,160 history
sessions under the recorded assumptions. Subsequent
[finite common-share rename reviews](docs/reviews/2026-09-17-v7-common-share-renames.md)
clear another 5,644 sessions (584,804 total), with six real feature-boundary checks
and a stock rename ledger handler.
[Three unrelated rename reviews](docs/reviews/2026-09-17-v7-unrelated-renames.md)
then admit another 2,026 sessions (586,830 total). The user also accepted the separate pre-tax held-cash reconstruction model;
the [implemented dividend ledger](docs/reviews/2026-09-17-v7-stock-cash-ledger.md)
now compiles all 4,337 eligible events, verifies their clocks and consumes a real
funded AAPL quote with the reviewed 2022 settlement calendar. The remaining
years and 55 excluded cash events still require treatment.
[Ten reviewed same-share splits](docs/reviews/2026-09-17-v7-reviewed-splits.md)
bring the action set to 4,491 and admitted history to 586,840 sessions, with all
ten real feature boundaries checked and a funded TSLA split/mark case. The stock
ledger now carries split quantities into later dividends. Unresolved identity/action cases and complete
held-position treatment still kept 7-1 open at that historical checkpoint;
the September 18 closure supersedes it.
The [cash/calendar continuation](docs/reviews/2026-09-17-v7-cash-calendar-closure.md)
resolves 36 FCX/SLB cash groups and their funded-stock entitlements under the
user-approved finite extension. Current totals are **4,527 price actions,
4,373 cash entitlements and 586,876 admitted history sessions**. Captured
Alpaca trade-to-settlement fields now supply the 2022–October 2026 schedule;
all 46 independent FINRA examples and all 4,337 original cash events reconcile.
The exact remaining dividend census is **492 items: 437 uncompiled cash groups
plus 55 compiled events awaiting date treatment**. The extension is authorized
for the original remaining 528 groups as each passes review; do not request
another per-issuer cash-model approval. Identity, other complex actions and
full held-position treatment still prevented advancement to 7-2 at that
historical checkpoint; the explicit exclusion policy now permits 7-2 after the
live V6 repair prerequisite.
September 18 [recovery and cash-date continuation](docs/reviews/2026-09-18-v7-cash-date-recovery.md)
recovers eight interrupted date fixes and adds 40 reviewed cases. Current cash
entitlements are **4,421**; **444 dividend items remain: 437 uncompiled groups
plus seven date cases**. All price actions and history coverage are unchanged.
The full suite passes 2,246 tests plus 18 subtests. Item 7-1 remained open at
that historical checkpoint and is now closed by the September 18 review.
September 18 primary-term continuation: **4,744 cash payment leaves**; **154 dividend review items remain (147 groups plus seven dates)**. Multi-payment distributions adjust price once and release each payment separately. All 289 new price boundaries and the 10,428-record partition reconcile; full suite passes 2,271 tests plus 18 subtests. Dividend work remains active.
The user selected this sequence on September 17 after reviewing the
[three-day report](docs/reviews/2026-09-17-three-day-goals-and-progress.md#6-consolidated-remaining-todos-before-the-goal-is-finished).
The report's pause is historical; this checklist and [HANDOFF](HANDOFF.md)
now define the work order. This documentation update does not claim any item
finished or start a research job.

## How we advance

Work on the current item and dependencies necessary to close that item. Reuse
completed artifacts and existing evidence. Record an exact missing consumer
input before acquiring more data; do not expand broad collection or add optional
research prerequisites. A real scope or admission-policy change must be explicit
and recorded in [DECISIONS](docs/DECISIONS.md).

Close an item only with its stated completion evidence over the required scope.
Update this checkbox, the evidence review and ROADMAP/DOCUMENTATION as relevant;
archive the old HANDOFF and write the next one for the next numbered item, then
commit and push the scoped changes. If unfinished, the handoff remains on the
same item with precise remaining work. Do not advance because a component test
or a selected-symbol pilot passed. Report completed work separately from remaining
work; only 7-7 can establish full V7 training readiness.

## Scope that stays fixed

March 15, 2022–September 14, 2026; Alpaca stock data, Massive options; no OTC;
BBBY/FRC/REV/SI issuer exclusions without replacement or reranking. Retain all
20 strategy families across the user-approved 5/15/30-minute signal scope:
8,451 variant/timeframe combinations and 221 columns. One-minute remains the
observed option-execution cadence, not a signal timeframe. Prior one-minute
artifacts remain historical and are not relabeled as current.
Arithmetic option midpoint pricing, separate costs, V7 12.5% premium stop,
strategy exits, ITM expiry exit 15 minutes before regular option close, and the
agreed funded physical fallback remain required. Preserve shared portfolio
limits, chronological folds and causal inputs. Use at most four outer workers,
one inner thread, 100 GiB disk reserve and the 250 GB acquisition ceiling.
Protect existing V6 paper operation; do not change its policy as a side task.
The user reported a roughly 230 GB project and constrained disk capacity.
Reuse captures and keep remaining dividend evidence to named small documents.
Before any further bulk acquisition or full-store generation, provide a storage
forecast and establish the total-project budget; the acquisition cap alone is
not a total-project disk budget. Preserve existing historical artifacts.
Full contracts: [V7 specification](docs/specs/MULTITIMEFRAME_RESEARCH.md) and
[active inputs](docs/specs/V7_ACTIVE_INPUTS_20220315_OPTION_RISK.json).

## Completed work and deferred backlog

The report's sections 2–4 retain completed work, evidence and unresolved live V6
findings. [ROADMAP](ROADMAP.md) indexes that history and the deferred backlog;
[DOCUMENTATION](DOCUMENTATION.md) retains implementation conventions and traps.
The previous overlapping checklist is preserved verbatim in
[the September 17 TODO archive](handoff-history/TODO-2026-09-17-before-report-sequence.md).
Its old open/checkmarked entries are historical; they are not another active V7
queue. Deferred work is not deleted and must not delay this seven-item sequence.

September 18 final dividend checkpoint: **4,918 payment leaves across all 4,854 compiled cash events; zero remaining dividend cases.** Rebuilt canonical coverage admits 587,284 of 667,239 history rows. The modeled FX rule was explicitly approved and implemented. One ETHE precision reconciliation is clearly provider sourced. The dividend subtask is complete; the subsequent noncash admission review closes 7-1.

September 18 7-1 closure: all 234 remaining noncash records now have one
source-bound `explicit_boundary_exclusion` treatment. The resulting panel
excludes 75,781 affected history rows at dated or undated identity boundaries,
and the held-position guard rejects any path crossing one. No successor
identity, stock/option deliverable, price factor, or cash outcome is inferred.
Artifact: `nn_meta/validation/v7-noncash-admission-20260918`; review:
`docs/reviews/2026-09-18-v7-6-1-closure.md`. 7-2 is current after the live V6
repair prerequisite.
