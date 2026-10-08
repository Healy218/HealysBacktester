# Roadmap — HealyLabs options research and MLOps lab

The lab's purpose is ongoing development, comparison and responsible operation
of options-trading model artifacts and specialist researchers. Progress means
completed, reproducible milestones and measured outcomes. The end goal remains
open-ended; each selected phase has bounded requirements and an exit condition.

**Selected work: [V8](#v8--edge-first-on-liquid-stocks-and-etfs) — stages 0 and 1.**
October 7 user direction: prove an edge on liquid stocks and ETFs under realistic
bid/ask fills before any options or meta-model work. ETFE closed October 7 (v5
failed; the 2026 test stays unspent); its section below is retained as history.
[Decision](docs/DECISIONS.md), [evidence](docs/EXPERIMENTS.md) (October 7 entries).

V7 research stays paused with its original gates/evidence preserved. MRHA archival
completed October 3 at 16:55:50 Central with all 2,847 shards verified and final
reclamation recorded. [Completion audit](docs/reviews/2026-10-03-v7-archive-completion-audit.json).
This closes storage task 7-3.archive, not the unfinished V7 scientific gate.
Other research/update campaigns remain paused; V8 selection does not resume them.
[TODO](TODO.md) owns actionable tasks. [CURRENT_STATE](docs/CURRENT_STATE.md)
owns selected inputs and runtime pointers. [GOALS](GOALS.md) owns the maturity
scorecard. Status below is reconciled September 27, 2026; live health requires
checking the linked operational evidence.

## Lab workstreams and dependencies

| Workstream | Established position | Next milestone and dependency |
| --- | --- | --- |
| Shared data and provenance | PIT identity/actions, frozen inputs, capture, replay and recovery components exist | V8.0 complete (frozen contract); V8.1 pre-registration next; retain immutable lineage for all researchers |
| Model researchers: classification, EV and future generations | V5/V6 artifacts and evaluation machinery exist; V7 retained; ETFE closed October 7; V8 selected | V8.1 verdict on the underlying before any model or options work |
| Paper execution and risk | Prospective V6 paper fills/reconciliation observed; October 2 Alpaca held quotes deployed | Full-universe entry features blocked pending Alpaca recording capacity and validation; sustain broker risk/reconciliation ([transition](docs/reviews/2026-10-02-v6-alpaca-provider.md)) |
| Continual research/training incubator | Initial catch-up and repaired two-session update through September 30 complete; both evaluated freezes retained, diagnostic regressions recorded; V7/storage restored ([October 1 evidence](docs/reviews/2026-10-01-v6-occurrence-repair.md)) | Measure a clean one-session update and sustained coexistence; V7 admission follows its own gate |
| FA discovery and context | Collection, rankings, enrichment snapshots and experimental evaluation exist | Complete the FA milestones below; no automatic admission into V7 or trading |
| Pine/external indicator parity | Selected ports exist | Source/version/availability and numerical parity evidence before new proposals are admitted |
| SPX0 / deeper index-options research | Earlier bounded-vertical studies did not earn a seat | Corrected deeper-history, liquidity/cost evidence and its existing drawdown gate; independent of V7-3 |
| Volatility specialists | HAR-RV/GARCH baseline machinery exists | Available-at inputs and incremental evidence by regime before sequence-model complexity |
| Stacked combinations | Deferred | Validated experts/FA inputs and comparable out-of-sample/forward evidence before combining outputs |
| RL sizing and exits | Deferred, last in dependency order | Reliable execution ledger and demonstrable improvement over simple sizing/exits |
| Platform, dashboards and journal | Deployment/monitoring and existing displays exist | Accurate artifact/account identity, recoverable operations and broker facts distinct from projections |

V7 archive completion is verified; V8 is selected (ETFE closed).
Other research workstreams above remain paused.
Their next milestones remain retained requirements, not active assignments.
Actual installed-service state is recorded separately in CURRENT_STATE; work
selection does not itself prove service shutdown or authorize spending.

## V8 — edge first on liquid stocks and ETFs

Selected October 7, 2026. Prove an edge under realistic bid/ask fills before any
options or meta-model work. Universe: point-in-time technology names plus SPDR
sector and broad ETFs. Delisted names stay in the historical test while they were
members (survivorship-free); live and paper trading only ever see current members.
Owned data only: V7 raw inputs read in place, plus Alpaca's free tier.
[Specification](docs/specs/V8_DESIGN_20261007.md) owns technical requirements;
[TODO](TODO.md) owns the stage 0–1 checklist.

| Gate | Deliverable | Status |
| --- | --- | --- |
| **V8.0 — Universe and cost contract** | PIT pool, bars, spreads, liquidity rule, fill model; [frozen contract](docs/specs/V8_CONTRACT_20261008.json) | **Done 2026-10-08** |
| **V8.1 — Edge on the underlying** | Pre-registered walk-forward, benchmark-beating after costs, deflated Sharpe, PBO < 0.5, 1.5× cost stress | Authorized; pre-registration next |
| **V8.2 — Volatility** | Candidate if V8.1 fails | Needs go-ahead |
| **V8.3 — Instrument mapping (options)** | Only after a proven edge | Needs go-ahead |
| **V8.4 — Meta-model** | Only if V8.1 or V8.2 passes | Needs go-ahead |
| **V8.5 — Holdout and forward evidence** | 2026 holdout, paper trading | Needs go-ahead |

Exit: a V8.1 verdict recorded in [EXPERIMENTS](docs/EXPERIMENTS.md). If nothing
passes, V8.2 is next, not a meta-model.

## ETFE — Exchange Traded Funds Expert

**Closed October 7, 2026** (v5 failed; 2026 test unspent). Retained as history.

ETFE is a brand-new expert replacing the active V7 research priority. It does
not reuse V7 model weights/checkpoints, relabel artifacts or close V7's unfinished gates. [Specification](docs/specs/ETFE.md) owns technical inheritance.
Initial configuration/catalog, provider diagnostics and the completed-minute
VWAP reference component are implemented. October 3 user direction requests
the complete plan through a working research expert's first build/freeze/train
run. This section owns that sequence; [first-run acceptance](docs/specs/ETFE_FIRST_RUN.md)
owns technical deliverables. The current gate remains ETFE-0.

| ID | Position | Deliverable and acceptance condition |
| --- | --- | --- |
| **ETFE-0 — Scope and provider contract** | Four definitions declared; admission validation continues alongside fresh raw acquisition | Exact SPY/QQQ/VOO and 1/5/15-minute scope, 0–5 DTE purchases/rolls, VWAP method; scoped Alpaca coverage through fixed October 2, 2026 end; required provenance/eligibility/execution facts resolved before admission |
| **ETFE-1 — Frozen inputs** | **Bootstrap/normalization/bounded expansion and calendar-level demand complete; symbol/session and causal strategy demand remain. Full freeze depends on ETFE-0 and ETFE-4.pilot** | Fresh source-bound acquisition, complete required underlying/options/context coverage, dated contracts/calendars, explicit missingness, fixed dates and immutable input freeze |
| **ETFE-2 — Strategies and causal features** | Bounded all-family components and joined diagnostic schema validated; full-history generation/admission depend on ETFE-1 | All 20 families/25,353 ticker variants, thirteen TV scopes, explicit trade/bar feature mapping, new schema and causal/parity evidence |
| **ETFE-3 — Execution and dataset** | Bounded synthetic shared scheduler/lifecycle/horizon and stress components implemented; full gate open, depends on ETFE-1/2 and ETFE-4.pilot | Tested VWAP-based simulated ledger, stops/expiry/roll/settlement, complete build, purged folds/trials and immutable dataset/experiment freeze; ETFE-4.recovery required before full build |
| **ETFE-4 — Resources and recovery** | Cross-cutting; early pilot before bulk work, final proof before training | ETFE-4.pilot measures capture/build/train/storage demand; ETFE-4.recovery proves restart; ETFE-4.admission binds full-build resource evidence to the training budget |
| **ETFE-5 — Training and evaluation** | Gated; depends on ETFE-0 through ETFE-4 | All predeclared trials completed, baseline/out-of-sample evaluation, trained artifact freeze, clean-process inference/replay and honest accepted/rejected verdict; no automatic deployment |

### ETFE first-run sequence

The order below preserves gate IDs; their numbers are ownership labels, not a
reason to postpone resource checks until after a large build. Small fixtures may
exercise later components early; that never closes full-coverage gates.
October 4 clarification adds bounded raw bootstrap before source admission.
This permits progress on actual Alpaca inputs without claiming source questions
are resolved. All later freeze, scientific and integrated-resource gates remain.

| Order / task ID | Work | Exit evidence before the next dependent step |
| --- | --- | --- |
| 0A — **ETFE-1.bootstrap** | Fresh bounded stock/option downloads, raw page lineage, resume and measured transport footprint. **Completed October 4**, 30 partitions. | Verified fresh page chains and recovery; no historical dataset or execution admission implied. Subsequent normalization/expansion is recorded below. |
| 0B — **ETFE-1.normalize / ETFE-1.expand** | **Completed October 4 for selected inputs:** typed Parquet for 186 partitions/1,677,986 rows; stock-month expansion and two additional option strata, with 0DTE enabled. | Full raw-row reconciliation, hashes, actual resume and stock-calendar missingness: zero SPY/QQQ gaps, twelve explicit VOO gaps. Full option/context acquisition and scientific admission remain open. |
| 0C — **ETFE-1.demand-calendar** | **Completed October 4:** collection-window phase-A calendar inventory, 691 sessions and all civil expiries for purchase/context purposes. | 190,716 logical expiry/status edges reconcile to 6,300 physical queries, with 60 exact fresh queries reused. Symbol/session, signal/feature and holding demand remain; no full resource forecast or input freeze implied. [Contract](docs/specs/ETFE_DEMAND_20261004.md). |
| 0D — **ETFE-1.expand-january** | **Completed October 4:** bounded January discovery, earlier-history census and full returned-symbol January 18/19 bars, normalized and independently reconciled. | 960 successful GETs; 200,637 new rows, 34,660 surface symbol/day edges. January 18 at the open remains first observed within the tested inventory; usable/full history stays unresolved. [Evidence](docs/reviews/2026-10-04-etfe-demand-boundary.md). |
| 0E — **ETFE-2.causal-components / ETFE-1.demand-pilot** | **Completed October 4:** fresh session grids and fifteen raw diagnostics; January 18–19 census of all twenty families / 25,353 ticker variants. | Every variant passed prefix/batch checks; actual scope resume and all 458,133 logical demand links reconciled. Raw diagnostics are unadmitted; full schema, dated references, full phase-B/C demand and integrated pilot remain open. [Evidence](docs/reviews/2026-10-04-etfe-causal-pilot.md). |
| 0F — **ETFE-1.trade-window-capture** | **Completed October 4:** all 225 missing phase-B pilot trade intervals, 103 queries / 105 GETs, 77,057 new normalized trades. | Raw resume, full occurrence/timestamp reconciliation and 4,626-minute demand audit passed. Empty intervals, three trade-without-bar minutes and unknown equal-time ordering remain explicit; no historical feature/execution admission. [Evidence](docs/reviews/2026-10-04-etfe-trade-windows.md). |
| 0G — **ETFE-2.option-trade-bar-components** | **Completed October 4:** ten registered formulas and explicit availability/condition/missingness rules; selected r1 covers 4,739 windows linked to all 458,133 pilot events. | Independent all-value/mask/reason/membership reconciliation, real future/order checks and actual resume passed. Initial r0 numerical rejection preserved; tolerance unchanged. Outputs remain diagnostic, with full schema and dated admission open. [Evidence](docs/reviews/2026-10-04-etfe-option-features.md). |
| 0H — **ETFE-2.tv-components** | **Completed October 5:** all 96 registered projections across thirteen numerical sources on fresh Alpaca bars; 2,964 January observations and all 458,133 event links. | Field-specific readiness, independent all-projection/mask/reason/membership audit, eighteen real prefix/future checks and actual resume passed. Raw diagnostics only; native Pine parity, remaining schema/context and dated admission stay open. [Evidence](docs/reviews/2026-10-05-etfe-tv-features.md). |
| 0I — **ETFE-2.remaining-components** | **Completed October 5 within declared real/synthetic scope:** remaining 100 fields and variant MA projections; all 221 component names reconciled. | Independent catalog/daily/signal/membership audits, all-variant prefix/batch checks and actual resume pass. Dated contract/sector and seven option-context fields remain missing on real inputs; their synthetic formula/API checks do not close source or joined-schema admission. [Evidence](docs/reviews/2026-10-05-etfe-remaining-features.md). |
| 0J — **ETFE-2.joined-schema** | **Completed October 5 within bounded diagnostic scope:** registered 221 values plus 221 masks joined for every original pilot event. | Independent natural-key reconciliation of all values, masks, reasons, modeled clocks and lineage; every chunk's changed-batch-boundary check and actual stop/resume pass. Dated inputs, full-history feature validation and scientific admission remain open. [Evidence](docs/reviews/2026-10-05-etfe-joined-schema.md). |
| 0K — **ETFE.provider-actions** | **Completed October 5 within bounded capture scope:** fresh corporate-action records and process-date tail, with finite mutation-route probes. | Raw/normalized and independent stream audits, actual resume and guarded pagination pass. Tail recovers actions effective before the price cutoff but processed later. Original publication, complete action history and broader provider admission remain open. [Evidence](docs/reviews/2026-10-05-etfe-action-evidence.md). |
| 0L — **ETFE.provider-action-replay** | **Completed October 5 within four-day transport scope:** source-bound replay with exact event-overlap reconciliation and one pre-effective action witness. | Original r0 precision rejection preserved; successor r1 completes with strict bounds, whole-second overlap, independent audit and actual resume. Older empty controls leave retention unknown. Input admission and freeze/train gates remain open. [Evidence](docs/reviews/2026-10-05-etfe-action-replay.md). |
| 0M — **ETFE-3.execution-components** | **Completed October 5 within synthetic mechanics scope:** funded integer entries, shared bar participation, partial exits/latched stops and option-cash settlement. | Handworked cashflows, independent Decimal reconciliation, five-prefix replay and separate-process restart pass. Real admission, expiry/roll/physical delivery, full execution stress and labels remain open. [Evidence](docs/reviews/2026-10-05-etfe-execution-components.md). |
| 0N — **ETFE-3.expiry-components** | **Completed October 5 within synthetic continuation scope:** quote-based expiry, settled-proceeds rolls, shared exercise reservations, call delivery and partial stock liquidation. | Four hand cases, independent cash/share audit, thirteen-prefix replay and actual restart pass. Full scheduler, funded-put inventory integration, real admission, stresses and label horizons remain open. [Evidence](docs/reviews/2026-10-05-etfe-expiry-components.md). |
| 0O — **ETFE-3.integration-components** | **Completed October 5 within bounded synthetic scope:** shared ordinary/lifecycle scheduler, generated clocks, settlement-extended diagnostic horizons and 27 stress profiles. | Six tapes / 162 combinations / 189 outcomes reconcile; actual restart and independent cash/share/census audit pass. Three stressed paths retain missing inputs. Full-history resource validation, real admission, isolated scientific labels and dataset build remain open. [Evidence](docs/reviews/2026-10-05-etfe-integration-components.md). |
| 0P — **ETFE-1.demand-frontier** | **Completed October 5 within envelope/bounded capture scope:** full-calendar returned-symbol counts, phase-C input obligations, measured route payloads and March 5–25 discovery continuation. | 126 successful GETs / 8,462 normalized records; both 2,073-session frontier audits, raw occurrence audit and zero-request restart pass. Exact full-window signal/path demand, missing quote/exercise measurements and full resource budgets remain open. [Evidence](docs/reviews/2026-10-05-etfe-demand-frontier.md). |
| 0Q — **ETFE-1.stock-quote-pilot** | **Completed October 5 within finite transport/diagnostic scope:** underlying SIP quote density across six sessions, plus March 26–April 15 discovery continuation. | All 54 windows / 1,943,472 quote occurrences and 7,344 discovery rows reconcile; actual restarts and 304 tests pass. Same three ETFs; quote size conversion, official exercise references, exact path demand and full budgets remain unadmitted/open. [Evidence](docs/reviews/2026-10-05-etfe-stock-quotes.md). |
| 0R — **ETFE-1.full-discovery** | **Completed October 6 within full-calendar discovery transport scope:** six range queries, 452,347 contracts and all 6,300 expiry/status partitions. Full-window announcements add 33 declaration dates. | Independent raw/typed/calendar reconciliation and actual resumes pass; 320 tests. Dated validation exposes missing terms clocks, 43,720 multiplier anomalies, 53,634 settlement conflicts and one action payable conflict. Full market windows and historical admission remain open. [Evidence](docs/reviews/2026-10-06-etfe-full-coverage.md). |
| 0S — **ETFE-1.exact-window-demand** | **Window census and known-candidate exact-option capture completed:** full context, packed signal and factored entry/feature demand over computable stock history; bounded option density sample and twelve VOO SIP gap rechecks. | 4,311,060 decision clocks / 151,005,384 logical 0/1/5-DTE links; known-candidate physical union and independent clock/bound audit. Source-bound option plan: all 3,036 requests captured/normalized (2,275,130 occurrences); independent full audit reconciles raw-to-Parquet and capture-to-union. No dated selection or execution is admitted; realized holding paths and full strategy demand remain open. Official Invesco evidence retrospectively resolves QQQ's March 2024 payable date. [Evidence](docs/reviews/2026-10-06-etfe-window-demand.md). |
| 0T — **ETFE-0.dated-policy** | **Completed October 6:** user-selected v1 rules for contract economics/availability, settlement, action knowledge, history start and VOO re-warm, applied to fresh inputs. | 452,342 of 452,347 contracts admitted; all 227,529 candidate rows available by entry start; provider settlement matches SEC rule except one declared day; independent audit and tests pass. Exercise reference (closing-auction capture, 1,486/1,487 sessions), $0.01 rule with reported pins and dated quote-size units added later the same day. P1, R1/R2 and action revisions remain documented as unmodeled. [Policy](docs/specs/ETFE_DATED_INPUT_POLICY_20261006.md). |
| 0U — **ETFE-1.existence / selection-v2 / envelope** | **Completed October 6–7:** daily-bar existence census, selection v2 (95.1% of 6,993,352 decision clocks; weekly 2/4 for SPY/QQQ), bars-only envelope capture (40.6M option minute bars, 46.0M SIP quotes), all normalized and independently reconciled. Row unit amended to decision clocks with earliest firing-variant exit. | Labels, features, context capture and the integrated pilot remain. [Envelope](docs/specs/ETFE_ENVELOPE_CAPTURE_20261006.md), [amendment](docs/specs/ETFE_ROW_UNIT_AMENDMENT_20261007.md). |
| 1 — **ETFE-0.contract** | Establish scoped ETFE history coverage and fixed end, audit every feature, define trade/bar replacements, warmup, causal availability, dated contracts and complete VWAP execution semantics under the 0–5 DTE rule. Predeclare final-boundary exclusions, targets and selection policy. | Versioned source/feature/execution contract with no unresolved required input for admission; explicit scoped coverage/eligibility rules. May proceed alongside bounded raw acquisition. |
| 2 — **ETFE-4.pilot** | Run a bounded representative capture → feature → execution → dataset → training smoke pilot, including busy SPY/QQQ, sparse VOO, open/close, expiration, gaps and difficult contract cases. | Measured requests, disk including temporary/freezes, RAM per worker, throughput, model-fit peak and recovery checkpoint sizes. Declare local storage reserve, rate limits and autosized worker/thread budgets before bulk work. |
| 3 — **ETFE-1.acquire / ETFE-1.freeze** | Expand the current source-bound Alpaca capture/normalization path; acquire required underlying 1m data, option VWAP bars/trades, dated contract/actions/calendar evidence and context. Reconcile pages, retries, duplicates, gaps and source provenance; seal the input inventory. | Complete required-input coverage census, explicit valid no-trade versus missing-provider cases, verified hashes/partitions and immutable input freeze. Adjustments/expiry/deliverables remain dated, not inferred from today's chain. |
| 4 — **ETFE-2.features** | Generate all registered strategy variants on session-aligned 1/5/15m bars; build the approved option trade/bar features, all nonquote/context and thirteen TV scopes. Freeze schema/dtypes/availability rules. | Variant census, indicator/direction parity, prefix-invariance and no-future-data checks; documented warmup/missingness; no silent quote-column substitution. |
| 5 — **ETFE-3.execution** | Complete simulated entries, marks, costs, quantities, stops, strategy exits, expiry exits, OTM rolls and funded physical delivery/stock liquidation. Implement shared five-slot/10%-equity accounting and terminal labels. | Hand-worked and real-data ledger reconciliation, causality, boundary/missing-mark/size stress, no implicit margin or invented fills; all unresolved outcomes accounted for. VWAP reference alone is insufficient. |
| 6 — **ETFE-4.recovery / ETFE-3.build** | Prove bounded streaming/sharding and interrupted restart on the integrated pilot, then execute the complete scoped dataset build with resumable receipts. | Restart matches uninterrupted output; full candidate/eligible/excluded/unresolved census, row/label/source alignment, complete scope and measured peak RAM/disk. A smoke sample or successful process exit is not a full build. |
| 7 — **ETFE-3.freeze / ETFE-4.admission** | Seal dataset partitions, schema, execution/input/source hashes, temporal folds, preprocessing rules, finite trials and evaluation/selection policy. Reconcile actual full-build resource use with the training allocation. | Independently verified immutable dataset + experiment freeze; no row/horizon leakage, ten-session embargo, training-only fitting and sufficient resources/recovery. No in-place changes after sealing. |
| 8 — **ETFE-5.train** | Train from the frozen dataset under the predeclared finite trial plan. Initial design carries forward constant baselines plus GBT and neural-network families for win, weighted-win and robust return objectives; new ETFE manifests/weights only. | Every required fold/trial has completed fit, model, logs, seeds, preprocessing hashes and predictions. Failed or abandoned required fits mean the campaign is incomplete. Small training smoke runs do not count. |
| 9 — **ETFE-5.evaluate / ETFE-5.freeze** | Compare all trials and model-driven decisions with predeclared baselines on identical rows, costs and shared-capital ledger. Evaluate chronologically held-out results and stress assumptions; freeze models, predictions and verdicts. | Complete net-return/risk and prediction metrics, trial accounting, selected-or-abstain decision, immutable trained-artifact bundle and acceptance/rejection receipt. Profitability is not assumed. |
| 10 — **ETFE-5.expert-proof** | Load the frozen bundle in a clean process, replay an untouched-by-fitting input slice with the production-style feature/decision interface, and verify deterministic restart/restore and schema rejection. | Functional offline expert emits auditable scores and eligible decisions/abstentions; replay matches frozen predictions within declared tolerances; manifest→input→row→model lineage and restore test pass. First research run is then complete. |

**First-run definition of done:** all ETFE-0 through ETFE-5 acceptance evidence
exists, the full build and all declared training trials finished, the dataset
and trained bundle are separately frozen and verified, and clean-process expert
inference/replay succeeds. A candidate can complete this engineering milestone
and still fail the performance gate; retain its negative verdict and withhold
promotion. A material data/causality failure prevents technical completion.
Paper/live deployment, continuous updates and incubator integration are subsequent
milestones, not implied by a finished training run.

**Forecast discipline:** no reliable wall-clock completion estimate exists yet.
Publish capture/build/train/storage estimates with measured workload counts and
uncertainty after ETFE-4.pilot; refresh against full-build throughput. Reuse verified
inputs/components and deduplicate demand, but never restore all V7 to start ETFE.
If measured storage does not fit, resolve placement/capacity before bulk capture;
do not assume MRHA headroom, auto-delete frozen inputs or narrow the scope silently.

This is the requested implementation plan, not a claim of a launched campaign.
The current frozen setup retains false readiness flags. Future readiness is a
new evidence-bound artifact, never an edit to its preparation receipt. Once
implementation is selected, routine work proceeds within scope; only genuine
unresolved user choices/resource authorization require clarification.

V7 component methods and tests may inform ETFE validation of changed universe,
timeframes, provider and dates; Massive quotes and V7 weights/checkpoints are
not ETFE inputs. Completion of
ETFE-0 does not establish data availability or model readiness.

## Phase 7 — V7 data, execution and training

Retained, paused predecessor. The seven steps keep their existing scope and order;
7-1/7-2 remain complete and 7-3 remains open. ETFE selection does not resume V7.
Partial later-stage implementation is preserved.
Technical scope and accepted amendments are indexed in
[CURRENT_STATE](docs/CURRENT_STATE.md#v7-scope-and-selected-inputs).

| Step | Status | Deliverable and condition for completion | Evidence / dependency |
| --- | --- | --- | --- |
| **7-1 — Identity and actions** | **Complete** | Source-bound identity/actions and explicit admitted held-boundary treatment | [Closure](docs/reviews/2026-09-18-v7-6-1-closure.md), [dividends](docs/reviews/2026-09-18-v7-dividends-complete.md); exclusions remain part of the admitted scope |
| **7-2 — Causal context and proposals** | **Complete** | Full agreed catalog/context and retained causal-prefix/recovery evidence | [Completion](docs/reviews/2026-09-25-v7-2-complete-and-v7-3-start.md); selected receipts in CURRENT_STATE |
| **7-3 — Required option evidence** | **Open; research paused for verified cold archive and resource/provider resolution** | Actual required entry/reference/held/exit/roll/stock inputs captured and coverage/provider failures/storage reconciled under the existing exclusions | Depends on completed demand/context; [remaining-input verification](docs/reviews/2026-09-27-v7-3-remaining-input-verification.md). [Entry completion](docs/reviews/2026-09-28-overnight-entry-completion.md); [reference completion/admission](docs/reviews/2026-09-28-v7-reference-completion.md); [approved exceptions and full discovery](docs/reviews/2026-09-28-v7-full-execution-discovery.md); [resumed discovery and actual-input capture](docs/reviews/2026-09-29-v7-resumed-discovery-and-capture.md); [September 30 frozen replay completion](docs/reviews/2026-09-30-v6-step-policy-v4.md); [continuous full-scope input continuation](docs/reviews/2026-09-30-v7-frontier-continuation.md); [October 2 performance pause](docs/reviews/2026-10-02-v7-performance-pause.md); [bounded performance validation](docs/reviews/2026-10-02-v7-performance-benchmark.md), [optimized adoption and resumption](docs/reviews/2026-10-02-v7-performance-adoption.md); closure requires actual final coverage receipts |
| **7-4 — Integrated execution** | **Partial implementation; full gate open** | Integrated full-scope ledger with reconciled fills, marks, costs, expiry, settlement and applicable stock delivery/liquidation | Existing components and [retained integration](docs/reviews/2026-09-27-v7-integrated-execution.md); finish against required 7-3 inputs |
| **7-5 — Assembly and folds** | **Upcoming; components exist** | Full agreed dataset, label horizons and predeclared purged folds/trials connected and reconciled | Depends on admitted inputs and execution labels; preserve existing assembly/fold components |
| **7-6 — Resources and recovery** | **Upcoming; component evidence exists** | Measured integrated build/training footprint, bounded memory, restart and coexistence with operational experts | Depends on actual 7-5 workload; reuse unchanged resource/recovery proofs |
| **7-7 — Readiness and launch** | **Upcoming** | Current readiness consumes accepted contracts/receipts; predeclared training campaign launched after real gates pass | Depends on 7-1 through 7-6; old checker fields must not reopen completed artifacts |

After launch, training completion, model evaluation, artifact freezing,
incubator admission and any paper/live promotion remain distinct lab milestones.
A successful launch is not a performance verdict or permission to deploy a model.

## Completed work

Completed evidence stays completed unless a named defect or approved scope
change invalidates it. This registry records deliverables; live counters and
revision-specific commands belong in CURRENT_STATE or their dated receipts.

| Deliverable | Completed scope and evidence |
| --- | --- |
| September 5–6 audit remediation and expanded V6 pipeline | [Remediation](docs/reviews/2026-09-05-remediation.md); historical artifacts retain their original contracts and verdict limits |
| V6 training and frozen expert | Training/freeze completed; old simulator history retained. Abandoned short-DTE research is not an active queue |
| ETFE initial setup and bounded Alpaca probes | October 3: independent scope, 20-family 1/5/15 catalog, immutable manifests/integrity checks and live read-only probes. Data admission remains open. [Evidence](docs/reviews/2026-10-03-etfe-setup.md) |
| ETFE quote-route diagnosis | October 3: official staff confirmation plus 13 live controls establish unsupported public historical-quotes route; all three latest OPRA quote controls succeed. Provider contract remains open. [Evidence](docs/reviews/2026-10-03-etfe-quote-404.md) |
| ETFE VWAP reference amendment | October 3: user-approved trade/bar method; completed-minute VWAP selected, causal reference component and immutable successor setup implemented; 46 focused tests passed. Full execution/features not admitted. [Review](docs/reviews/2026-10-03-etfe-vwap.md) |
| ETFE first-run plan and note reconciliation | October 3: full dependency sequence, build/input/dataset/model-freeze and expert-proof acceptance recorded; current-phase TODO and document owners reconciled. Documentation only, no future gate closed. [Review](docs/reviews/2026-10-03-etfe-first-run-plan.md) |
| ETFE-0 component contracts | October 3: exhaustive feature map, execution/evaluation/acquisition definitions, 84-fit declaration and ten live controls. H1/R1/R2/P1 remain open; no pilot or gate closure. [Review](docs/reviews/2026-10-03-etfe-contract.md) |
| ETFE Alpaca pull diagnosis | October 3: 40 live GETs, sample trade/bar and six-page equivalence, rejected feed parameter, historical metadata anomalies and dated QQQ/VOO explanations. Source gate remains open. [Review](docs/reviews/2026-10-03-etfe-alpaca-pulls.md) |
| ETFE fresh download bootstrap and 5-DTE guard | October 4: isolated resumable Alpaca capture, 30 complete raw partitions, live checkpoint preservation, v3 setup and tested purchase/roll DTE guard. Full-history admission and integrated pilot remain open. [Review](docs/reviews/2026-10-04-etfe-fresh-acquisition.md) |
| ETFE 0DTE normalization and bounded expansion | October 4: v4 permits qualifying 0–5 DTE entries/rolls; 254 new GETs, 186 normalized partitions, all 1,677,986 row occurrences reconciled. VOO gaps/full option coverage remain explicit. [Review](docs/reviews/2026-10-04-etfe-normalization-expansion.md) |
| ETFE phase-A calendar demand and January coverage | October 4: 6,300-query calendar inventory; 960 new successful GETs and 200,637 normalized records, including all-returned-symbol earlier-history and January 18/19 checks. First-observed/usable boundaries remain distinct; phase-B/C demand and full acquisition stay open. [Review](docs/reviews/2026-10-04-etfe-demand-boundary.md) |
| V7 cold archive and verified local reclamation | October 3: all 2,847 shards/564 roots preserved on MRHA; 35,031 eligible local files removed; matching final receipts and sampled restore checks. [Audit](docs/reviews/2026-10-03-v7-archive-completion-audit.json) |
| V7-1 and V7-2 | Gate closures above; do not reopen old dividend lists, context builds or catalog freezes |
| V7-3 demand scheduler, request census, exact union and lossless joining | [Demand/recovery](docs/reviews/2026-09-25-v7-3-crash-recovery.md), [union](docs/reviews/2026-09-26-v7-entry-union-and-first-capture.md), [joining](docs/reviews/2026-09-26-v7-capture-storage-forecast.md) |
| Storage cleanup, packing and bounded packed readers | [Migration](docs/reviews/2026-09-26-authorized-storage-reclamation.md), [packed captures](docs/reviews/2026-09-27-v7-joined-packed-capture.md) |
| Dated reference demand, regular hours and exact blackouts | [Hours/paths](docs/reviews/2026-09-27-v7-dated-hours-and-execution-paths.md), [blackouts](docs/reviews/2026-09-27-v7-contract-reference-blackouts.md); a completed demand plan is not completed capture |
| Replay frontier, first-leg envelope census and partial shared ledger | Existing replay/resume components and retained integration; possible envelopes are not download orders; full 7-4 remains open |
| Full-universe entry capture controller, versioned concurrency and MRHA overflow | [Launch](docs/reviews/2026-09-27-v7-entry-campaign-started.md), [concurrency](docs/reviews/2026-09-27-v7-parallel-capture.md), [storage/memory](docs/reviews/2026-09-27-v7-storage-and-memory.md); active configuration has one pointer owner |
| Execution/dataset/model components | Fills/marks/stops/rolls, physical ledger, causal features, factorized rows, purging, train-only preprocessing and finite trials exist; full integration/admission is separate |
| V6 Alpaca-only held-option quotes | October 2: deployed and observed held monitoring without Massive calls; [evidence](docs/reviews/2026-10-02-v6-alpaca-provider.md). Full-universe feature recording/admission remains blocked on capacity and validation, separately tracked in TODO |
| V6 Alpaca paper activation | [Deployment](docs/reviews/2026-09-27-v6-alpaca-activation.md); startup verified, actual prospective fill observation still pending at that checkpoint |
| V6 prospective paper fills and reconciliation | September 29: authenticated 48-order comparison, eight filled orders, four matching holdings, zero open orders; [evidence](docs/reviews/2026-09-29-paper-reconciliation-v6-resume.md). Ongoing risk monitoring remains operational work |
| V5/V6 nightly incubator activation and Friday inference | [Activation](docs/reviews/2026-09-25-incubator-nightly-activation.md), [Friday audit](docs/reviews/2026-09-27-incubator-fa-alpaca-readiness.md); historical replay scope superseded by [continual training](docs/reviews/2026-09-27-v6-continual-incubator.md), without invalidating the inference evidence |
| Documentation consolidation | [Ownership and preservation review](docs/reviews/2026-09-27-documentation-consolidation.md); no research/runtime work performed |

## FA milestones — paused pending user selection

This is the sole FA milestone map. [FA context reference](docs/reference/FA_CONTEXT.md)
retains the detailed requirements and distinctions between raw captures,
feature snapshots, labels and monthly cohorts. Existing collectors, manifests,
feature snapshots and evaluation code are reusable work, not presumed missing.

| ID | Position | Deliverable and acceptance condition |
| --- | --- | --- |
| **FA-0** | Quality/contract work open | Inventory and profile source/date partitions, identity/join coverage, availability and missingness; freeze a data contract and dated baseline limitations report |
| **FA-1** | Collection/automation exists; full coverage audit open | Verify immutable/replayable capture receipts, event keys, source/capture time, PIT identity revisions, failure handling and bounded resource/retention policy across the required sources |
| **FA-2** | Daily enrichment exists; full context bars open | Causal per-security 5/15/30-minute and appropriate daily bars with explicit age/decay; prefix, grain, join and incremental-equivalence evidence |
| **FA-3** | Experimental label/evaluation code exists; history accumulating | Sufficient chronological purged history, source/baseline ablations and inspectable coverage; three clean forward-tracked monthly cohorts before graduation claims |
| **FA-4** | Deferred behind FA-0–3 | Compare simple rules/regularized/tree baselines, calibrate and test stability; freeze reproducible candidates only with incremental out-of-sample value after costs, or record rejection |
| **FA-5** | Deferred behind FA-4 | Versioned sidecar/embedding interface, causal offline/shadow joins, parity, resource feasibility and forward evidence; explicit admission decision |
| **FA-6** | Optional, behind FA-5 | Panel/stacking/universe admission only after its gates; sustained drift/freshness/cohort monitoring, artifact retention and rollback |

August's historical ranking cannot count as a clean prospective cohort; that
finding does not discard all older raw data. Daily collection and monthly
cohort freezing are separate cadences. Neither FA nor future specialists add
unselected prerequisites to Phase 7.

## Completion and scope discipline

- Preserve PIT inputs, frozen/source-bound artifacts and causal availability.
- Use funded shared-capital accounting with costs and declared comparisons.
- New complexity must beat the boring baseline under its own admission gate.
- To reopen a completed deliverable, name the defect/scope change, affected
  receipt and narrow repair in DECISIONS/TODO. Preserve unaffected completion.
- A review, test count, elapsed wait or obsolete status flag cannot silently
  expand a gate. Changes to acceptance criteria require an explicit decision.

## Historical records

Earlier roadmap/task detail is preserved in the
[pre-consolidation snapshot](handoff-history/docs-2026-09-27-before-consolidation/ARCHIVE.md)
and the [earlier roadmap archive](handoff-history/ROADMAP-2026-09-27-before-live-doc-reconciliation.md).
They retain history, not active task authority. Decisions and actual verdicts
remain in [DECISIONS](docs/DECISIONS.md) and [EXPERIMENTS](docs/EXPERIMENTS.md).
