# TODO — V7 readiness, one deliverable at a time

## October 2 Massive subscription decision

- [ ] By **2026-10-02**, give the user a source-backed keep/cancel recommendation
  for Massive Options Advanced. Check whether V7's required pre-February-2024
  option quotes/trades have been captured and verified; audit representative
  SPX/NDX two-year Alpaca OPRA quote/trade windows for the proposed V8; and
  establish the V6 Alpaca feature-adapter/decision-parity result. If these
  are incomplete, retain Massive for one more month and reassess before the
  following renewal. The user will decide the subscription; do not cancel it
  automatically. See `docs/reviews/2026-09-24-v6-alpaca-paper-start.md`.

## Parallel V6 Alpaca paper restart

- [x] Verify dedicated paper credentials, account eligibility and empty broker
  state; prepare a separate hash-verified V6 state with scanning and order
  submission disabled. Evidence: `docs/reviews/2026-09-24-v6-alpaca-paper-start.md`.
- [x] Implement the guarded structured-event bridge core: stable event/order
  IDs, mark-limit pricing, buying-power sizing, broker reconciliation and an
  append-only intent/observation journal. The real-account preview saw zero
  new scanner events; no broker order was submitted. Code/tests were pushed
  in `75e2374` and `1b2da2f`.
- [ ] Finish prospective fresh-scanner integration and lifecycle verification,
  including multi-roll handling, before enabling Alpaca paper submissions.
  Fresh scanning and submission remain disabled. Preview genuine new events;
  never import the old simulator's positions. Keep simulator and broker P/L
  separate in Stonks. The account-only read monitor runs every five minutes
  during market hours; monitoring does not establish broker execution.

## 7. Consolidated remaining TODOs before the goal is finished

- [x] **7-1. Complete usable identity/action histories under an agreed admission policy.**
  Completion evidence: Every relevant security/session/action has an explicit resolved treatment, consumed by the actual feature and held-position paths.

- [x] **7-2. Produce complete causal daily/market context and full feature/proposal stores.**
  September 25 completion: all 591 securities, 1,773 sealed 5/15/30 stores,
  8,451 variants per security, 221-column downstream schema; plus 667,239
  joined daily rows and 1,182 passing historical-prefix replays. All catalog
  stores were preserved. The full daily audit verifies source/receipt hashes,
  exact routing, action returns, market context, missingness and next-open
  availability. Completion gate: `nn_meta/validation/v7-2-completion-20260925`.
  See [completion and launch evidence](docs/reviews/2026-09-25-v7-2-complete-and-v7-3-start.md).

- [ ] **7-3. Complete actual option-path demand, dated hours/reference inputs and targeted captures.**
  **Active as of September 25.** The first MTUM demand pilot passed: 29,843
  actual proposals, 3,552 quote/trade requests, 76 contracts. All 591 securities
  remain in scope. The full entry-demand service is now running for all 591,
  reusing the completed pilot checkpoints.
  The resumable all-security demand scheduler is implemented with exact
  historical-loader proof support. Four validation securities passed: 97,935
  proposals, 7,674 requests and 6,700 union capture windows; all 12 receipts
  survived restart unchanged. This is a validation subset, not full demand.
  Full-scope census: 793,394,264 proposals, 27,576,105 timeframe decisions and
  20,345,211 selection decisions. A 193.45 GB stress forecast supports the
  200 GiB stage allocation and 640 GB total-project budget. The full service
  `healys-v7-entry-demand-20260925.service` launched with four workers; 130/591
  had sealed at the recorded follow-up, with no failures. Monitor its own
  progress, then reconcile the full request union before targeted captures.
  Crash recovery: 546 checkpoints survived the user-session shutdown. All frozen
  catalog receipt pairs and completed demand input/source bindings still match.
  The user approved the exact Linux 7.2.6 → 7.2.7 compatibility validation;
  four real byte-parity replays passed. The separate recovery service
  `healys-v7-entry-demand-recovery-20260925.service` now revalidates/reuses those
  checkpoints before finishing the remaining 45. Its meter is
  `v7-3-scheduler-20260925/kernel-recovery/progress.json`. The root progress
  is the failed strict-runtime restart. The measured recovery cap is 140 GiB;
  all originals remain intact. See the
  [recovery record](docs/reviews/2026-09-25-v7-3-crash-recovery.md).
  September 26: **all 591 demand checkpoints and the full entry-request union
  audit are complete**. The 793,394,264 proposals produced 76,910,536 unique
  requests and 42,030,534 union quote/trade windows over 1,057,177 contracts.
  All no-contract/no-fresh outcomes remain explicit. The first actual SPY
  March 15, 2022 consumer window was captured and verified: 3,239 quotes,
  1,208 trades, 73,313 bytes. Full acquisition still requires a measured
  volume/storage plan; only ~50.69 GB is available above the disk reserve.
  Training has not started. Dated references/hours and full execution-path
  coverage remain open. See [union and first capture](docs/reviews/2026-09-26-v7-entry-union-and-first-capture.md).
  The separate viewer is `./venv/bin/python scripts/watch_v7_demand.py --follow`
  (now shows completed demand). Both stale V6/catalog hourly timers are disabled.
  Later September 26: the full-population volume plan reconciled all 591 stores;
  **1,440 sampled captures passed**, with 237,417 records across 362 securities
  and all five years. Current-layout entry storage estimates 218.04 GB (mean
  plus three SE: 265.77 GB), exceeding 181.02 GB remaining acquisition quota
  and ~50.67 GB local capacity above the reserve. Experimental lossless columns
  estimate 164.08 GB but are not a production archive. A full exact contiguous
  union audit reduces capture ranges to 10,941,828 without adding any seconds;
  longer-range resource/receipt handling still needs validation. Asked the user
  for another storage location; an unmounted MRHA exFAT disk is visible but
  has not been used. Bulk acquisition/training remain gated; all originals and
  both budget limits remain preserved. See
  [capture storage forecast](docs/reviews/2026-09-26-v7-capture-storage-forecast.md).
  Storage review follow-up: the user authorized using more local capacity and
  joining intervals only without quality loss. New capture planning uses a
  **20 GiB reserve**; the latest free-space check rose externally to 231.58 GB,
  leaving ~210.10 GB above that reserve. Joined downloads passed raw/causal
  parity for all 126 requests in six real cases (62 fixed captures → 12 joined).
  The project inventory found 13.30 million files / 2.89 million directories;
  old V6 expanded inputs account for 9.54 million files and 51.53 GB. A focused
  SHA256 audit found 53.88 GB of extra identical contents, including 28.87 GB
  of prepared training arrays; no cleanup was performed. Current V7 declarations
  still reference many older intermediates. Exact retention/duplicate evidence:
  [storage and quality review](docs/reviews/2026-09-26-storage-retention-and-adjacent-quality.md).
  Next: content-preserving duplicate cleanup/verified archival planning, a
  representative joined-range forecast and packed capture storage before bulk
  acquisition. The acquisition/project ceilings and remaining training gates
  are unchanged.
  See `docs/reviews/2026-09-25-v7-3-full-demand-launch.md`.
  Evidence: `docs/reviews/2026-09-25-v7-3-demand-scheduler.md`. Launch evidence: `nn_meta/validation/v7-3-launch-20260925`.
  Derive proposal-driven
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

- [ ] **8. Run V5/V6 daily artifact replay; add V7 after its readiness gate.**
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
  The user authorized nightly read-only replay of the existing frozen V5/V6
  bundles on fresh candidate data, with V7 to be added only after its build
  and readiness gate. This refreshes predictions, not model weights. Do not
  admit V7/FA artifacts or call pending-outcome predictions a performance or
  readiness result until their separate gates pass.

  Incubator slices 1–6 are now implemented and smoke-validated for V5/V6:
  bounded resource/time budgets, dry-run and failure-path tests, a real Keras
  replay entrypoint wired to common metrics, and a checkpointed after-close
  service/timer implemented. Replay correctly fails closed
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
  September 24 finished with 26 genuine V5 passes, 8,190 candidates and all
  Parquet hashes valid. A calendar-bound stage copies the closed V5 day from
  Hetzner to home and rejects missing 15-minute bars. The installed V5/V6
  after-close service ran both frozen bundles under network and filesystem
  isolation for that day: 8,190 V5 and 5,085 V6 predictions, two successful
  receipts, zero input blocks. Its user timer is enabled for 16:30 New York
  time on weekdays, selecting the last fully closed exchange session on late
  starts. Confirm the September 25 scheduled run and ongoing daily health.
  Exact-identity V5 outcomes and paper scoring remain open. A V6-origin V5
  compatibility smoke test is not V5 paper validation; V7 admission remains
  gated by 7-2 through 7-7.

**7-1 and 7-2 are complete, including full-scope daily context. 7-3 is active:
its scheduler and four-security validation pass; full option-path demand and
captures remain open. The live V6 repair prerequisite was completed before
7-2. V6 here means only the current home-hosted paper runtime; the abandoned
local short-DTE build is not part of this work. Items 7-4 through 7-7 remain
queued.**

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
one inner thread and the 250 GB acquisition ceiling. The September 26 user
amendment permits a **20 GiB reserve for new capture planning**, including
in-flight writes, under `docs/specs/V7_CAPTURE_CAPACITY_20260926.json`.
Original frozen launchers keep their historical 100 GiB guards; do not edit
bound producers merely to change their reserve. New bulk consumers must enforce
the amended policy explicitly.
Protect existing V6 paper operation; do not change its policy as a side task.
The earlier roughly 230 GB project estimate is stale: the September 25
measurement is 421.285 GB. The original demand allocation was 200 GiB. Recovery uses a measured 140 GiB
cap (128.81 GB stress forecast including existing output and remaining work)
within the unchanged 640 GB total-project budget. Option captures need a fresh
storage forecast.
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
