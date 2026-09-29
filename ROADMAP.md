# Roadmap — HealyLabs options research and MLOps lab

The lab's purpose is ongoing development, comparison and responsible operation
of options-trading model artifacts and specialist researchers. Progress means
completed, reproducible milestones and measured outcomes. The end goal remains
open-ended; each selected phase has bounded requirements and an exit condition.

**Selected phase: 7 — V7 data, execution and training. Current gate: 7-3.**
[TODO](TODO.md) owns actionable tasks. [CURRENT_STATE](docs/CURRENT_STATE.md)
owns selected inputs and runtime pointers. [GOALS](GOALS.md) owns the maturity
scorecard. Status below is reconciled September 27, 2026; live health requires
checking the linked operational evidence.

## Lab workstreams and dependencies

| Workstream | Established position | Next milestone and dependency |
| --- | --- | --- |
| Shared data and provenance | PIT identity/actions, frozen inputs, capture, replay and recovery components exist | Complete Phase 7's actual required coverage; retain immutable lineage for all researchers |
| Model researchers: classification, EV and future generations | V5/V6 artifacts and evaluation machinery exist; V7 preparation is active | Finish Phase 7; evaluate its trained artifacts before any incubator or operational admission |
| Paper execution and risk | V6 full scan and submit/cancel verified September 28; independent-order V2 policy deployed; first actual fill pending | Observe real prospective fills/recovery; demonstrate sustained broker reconciliation separately from model quality |
| Continual research/training incubator | V6-only continual pipeline implemented and activated September 27; SPY pilot and full-size member benchmark passed | Automatic post-V7 restart verified; finish catch-up and candidate freeze, then measure a full daily update; V7 admission follows its own gate |
| FA discovery and context | Collection, rankings, enrichment snapshots and experimental evaluation exist | Complete the FA milestones below; no automatic admission into V7 or trading |
| Pine/external indicator parity | Selected ports exist | Source/version/availability and numerical parity evidence before new proposals are admitted |
| SPX0 / deeper index-options research | Earlier bounded-vertical studies did not earn a seat | Corrected deeper-history, liquidity/cost evidence and its existing drawdown gate; independent of V7-3 |
| Volatility specialists | HAR-RV/GARCH baseline machinery exists | Available-at inputs and incremental evidence by regime before sequence-model complexity |
| Stacked combinations | Deferred | Validated experts/FA inputs and comparable out-of-sample/forward evidence before combining outputs |
| RL sizing and exits | Deferred, last in dependency order | Reliable execution ledger and demonstrable improvement over simple sizing/exits |
| Platform, dashboards and journal | Deployment/monitoring and existing displays exist | Accurate artifact/account identity, recoverable operations and broker facts distinct from projections |

FA collection, operational monitoring and scheduled inference may continue
while research is deferred. Additional work is selected through the main TODO;
this map does not authorize a new campaign or spending decision.

## Phase 7 — V7 data, execution and training

The seven steps retain their existing scope and order. Partial later-stage
implementation is preserved; it does not move the active gate past 7-3.
Technical scope and accepted amendments are indexed in
[CURRENT_STATE](docs/CURRENT_STATE.md#v7-scope-and-selected-inputs).

| Step | Status | Deliverable and condition for completion | Evidence / dependency |
| --- | --- | --- | --- |
| **7-1 — Identity and actions** | **Complete** | Source-bound identity/actions and explicit admitted held-boundary treatment | [Closure](docs/reviews/2026-09-18-v7-6-1-closure.md), [dividends](docs/reviews/2026-09-18-v7-dividends-complete.md); exclusions remain part of the admitted scope |
| **7-2 — Causal context and proposals** | **Complete** | Full agreed catalog/context and retained causal-prefix/recovery evidence | [Completion](docs/reviews/2026-09-25-v7-2-complete-and-v7-3-start.md); selected receipts in CURRENT_STATE |
| **7-3 — Required option evidence** | **Active: known reference exceptions adjudicated; full paths open** | Actual required entry/reference/held/exit/roll/stock inputs captured and coverage/provider failures/storage reconciled under the existing exclusions | Depends on completed demand/context; [remaining-input verification](docs/reviews/2026-09-27-v7-3-remaining-input-verification.md). [Entry completion](docs/reviews/2026-09-28-overnight-entry-completion.md); [reference completion/admission](docs/reviews/2026-09-28-v7-reference-completion.md); [approved exceptions and full discovery](docs/reviews/2026-09-28-v7-full-execution-discovery.md); actual held coverage remains required |
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
| V7-1 and V7-2 | Gate closures above; do not reopen old dividend lists, context builds or catalog freezes |
| V7-3 demand scheduler, request census, exact union and lossless joining | [Demand/recovery](docs/reviews/2026-09-25-v7-3-crash-recovery.md), [union](docs/reviews/2026-09-26-v7-entry-union-and-first-capture.md), [joining](docs/reviews/2026-09-26-v7-capture-storage-forecast.md) |
| Storage cleanup, packing and bounded packed readers | [Migration](docs/reviews/2026-09-26-authorized-storage-reclamation.md), [packed captures](docs/reviews/2026-09-27-v7-joined-packed-capture.md) |
| Dated reference demand, regular hours and exact blackouts | [Hours/paths](docs/reviews/2026-09-27-v7-dated-hours-and-execution-paths.md), [blackouts](docs/reviews/2026-09-27-v7-contract-reference-blackouts.md); a completed demand plan is not completed capture |
| Replay frontier, first-leg envelope census and partial shared ledger | Existing replay/resume components and retained integration; possible envelopes are not download orders; full 7-4 remains open |
| Full-universe entry capture controller, versioned concurrency and MRHA overflow | [Launch](docs/reviews/2026-09-27-v7-entry-campaign-started.md), [concurrency](docs/reviews/2026-09-27-v7-parallel-capture.md), [storage/memory](docs/reviews/2026-09-27-v7-storage-and-memory.md); active configuration has one pointer owner |
| Execution/dataset/model components | Fills/marks/stops/rolls, physical ledger, causal features, factorized rows, purging, train-only preprocessing and finite trials exist; full integration/admission is separate |
| V6 Alpaca paper activation | [Deployment](docs/reviews/2026-09-27-v6-alpaca-activation.md); startup verified, actual prospective fill observation still pending at that checkpoint |
| V5/V6 nightly incubator activation and Friday inference | [Activation](docs/reviews/2026-09-25-incubator-nightly-activation.md), [Friday audit](docs/reviews/2026-09-27-incubator-fa-alpaca-readiness.md); historical replay scope superseded by [continual training](docs/reviews/2026-09-27-v6-continual-incubator.md), without invalidating the inference evidence |
| Documentation consolidation | [Ownership and preservation review](docs/reviews/2026-09-27-documentation-consolidation.md); no research/runtime work performed |

## FA milestones — research deferred, collection continues

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
