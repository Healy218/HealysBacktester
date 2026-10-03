# Current state and artifact index

Pointer/configuration owner for the lab; V6 pointers updated October 2, 2026.
[ROADMAP](../ROADMAP.md) owns milestone status and acceptance conditions;
[TODO](../TODO.md) owns selected work. This page selects exact inputs and
runtime identities. Other current documents link here instead of copying them.

**Selected V6 paper:** [October 2 Alpaca transition](#october-2-v6-paper-alpaca-options-transition).
Held quotes use Alpaca; full-universe entry features remain blocked.

**Evidence freshness:** V6 paper and incubator observations below are dated. Other sections retain their own dated scopes and
timestamps; old progress alone does not establish present service health.
Verify the indicated live receipts when asked for present health or progress.
Never infer a current ETA from a historical throughput sample.

## Runtime identity and locations

| Scope | Host / checkout | Authoritative state or evidence |
| --- | --- | --- |
| Research/editing | Home, `/home/healy/Coding/HealysBacktester`, `main` | Main TODO and selected V7 inputs below |
| V7 capture | Home, research checkout | V7 acquisition runtime below; capture `v5` is a controller revision, not the V5 model |
| V5 expert | Hetzner, server checkout | Server scanner operation; retained [production review](reviews/2026-09-06-production-alert-review.md) is dated evidence, not a fresh health assertion |
| V6 frozen scanner source | Home, `/home/healy/Coding/HealysV6` | Frozen release `deploy/v6/releases/v6-cash-repair-20260913`; original activation/source hashes remain enforced |
| V6 fresh Alpaca PAPER | Home, V6 checkout | `nn_meta/live/v6_alpaca_paper/`; [activation receipt](reviews/2026-09-27-v6-alpaca-activation.json) |
| V6 historical simulator | Home, V6 checkout | `nn_meta/live/v6_server/`; old portfolio history retained, execution/relay schedules retired; its data producer remains selected |
| FA automation | Home, `/home/healy/Coding/HealysAutomation` | `deploy/fa-runtime.json`, `logs/job-health/`, `fa/archive/` and FA artifacts below; do not inspect stale copies in another checkout |
| Continual incubator | Home, research checkout | `deploy/incubator-continual-v6-r3.json`, `incubator/continual-v6/r3/latest-run.json`; routing below |

## V7 acquisition runtime

### Dated references — capture completed September 28

- Service: `healys-v7-references-20260928.service`.
- Declaration/progress/attempts: `nn_meta/validation/v7-reference-campaign-20260928/`.
- Immutable batches: `nn_meta/data_v7/dated-reference-campaign-20260928/`.
- Launcher: `bash scripts/start_v7_reference_campaign.sh 32`; selected 16 threads
  by autosizing, CPU quota 100%, MemoryHigh/Max 1/2 GiB, no swap.
- Completed successfully at 16:48:10 Central, with all 2,223,844 planned pairs.
  Service exit was successful; 1-GB memory peak was not an OOM kill.
- Full audit: `nn_meta/validation/v7-reference-reconciliation-20260928-full-r0/`.
  It verifies 2,212,991 standard pairs, five existing blackouts, 10,817 other 404s
  and 31 strict-validator rejections. Raw retained files total 2,120,051,077 bytes.
- Exact rename overlay: `nn_meta/validation/v7-reference-rename-review-20260928/`;
  consumer proof: `v7-reference-rename-consumer-check-20260928/`. Explicitly bind
  `ReviewedContractReferences` to normalize the 22 reviewed underlying names.
  The nine cash-deliverable rows and 10,817 missing pairs were subsequently
  adjudicated by explicit user approval; use the compiled finite policy below.
- [Completion, exception evidence and separate V6 memory failure](reviews/2026-09-28-v7-reference-completion.md).
  Reference capture is complete; admission and actual held-path coverage remain open.

### Completed entry campaign

- Service: `healys-v7-capture-v7-20260927.service` (home box).
- Live meter: `nn_meta/validation/v7-entry-campaign-v7-20260927/progress.json`.
- Immutable launch: `nn_meta/validation/v7-entry-campaign-v7-20260927/declaration/`.
- New packs: `nn_meta/data_v7/entry-campaign-20260927/<security>/<batch-hash>/`.
- Attempt journal: `nn_meta/validation/v7-entry-campaign-v7-20260927/attempts/`.
- Shared acquisition accounting: `nn_meta/data_v7/quota.json`.
- Historical launcher: `bash scripts/start_v7_capture_campaign_v7.sh 12 32`.
  Entry capture is complete; do not relaunch without a specific new defect/scope.
- [Concurrency upgrade](reviews/2026-09-27-v7-parallel-capture.md); original
  declaration and journals remain in `v7-entry-campaign-20260927/`.
- [Original launch review](reviews/2026-09-27-v7-entry-campaign-started.md) and
  [initial live proof](reviews/2026-09-27-v7-entry-campaign-launch.json).

This job downloads the exact full-universe **entry quote/trade** union minus
already captured coverage. It does not yet automate all held/roll/stock/reference
acquisition or assembly/training. Those are the precise remaining V7-3/next-stage
connections in TODO, not reasons to rebuild completed preparation.

Twelve autosized process workers, up to 32 I/O threads each (**384-request ceiling**),
and one numerical thread per worker. Selected after the user-requested September 27
trial; [measurements and preservation](reviews/2026-09-27-v7-twelve-worker-capture.md).
MemoryHigh/Max remain 14 GiB with no swap. Prefetch backs off at 6/8/10 GiB of
working-memory pressure, excluding only clean inactive file cache. All prior
producers and the current source-bound v7 producer remain frozen; version any
subsequent behavior change. CPU quota remains 800%, low scheduling priority,
and TasksMax is 464. The same runner can resume with a measured lower worker
ceiling after draining; older runners cannot accept newly produced v7 packs.

The selected storage policy is [V7_CAPTURE_STORAGE_V7_20260927.json](specs/V7_CAPTURE_STORAGE_V7_20260927.json).
The user superseded the old 100/250/640-GB fixed limits and 20-GiB reserve.
Allocation now follows live free space, leaving **10 GB free** locally and
accounting for in-flight writes. New payloads overflow to MRHA (UUID 62C9-C390)
under `HealysBacktester/v7-entry-campaign-20260927`, also leaving 10 GB there.
Logical pack directories/receipts stay local, with only SQLite payload files
linked to MRHA. Four real overflow batches passed existing-reader readback.
Keep MRHA connected. September 29 post-interruption: verified UUID 62C9-C390
and remounted `/run/media/healy/MRHA`. All four existing entry payload symlinks
resolve; three sampled packs pass checksums. About 87 GiB internal and 693 GiB
MRHA free at inspection. No bulk migration performed. The frontier capture uses
an older local worker/quota ledger; do not assume it inherits entry overflow routing.
[Storage/recovery scope](reviews/2026-09-29-power-surge-recovery.md).

### User-authorized completed-payload migration — September 29 evening

Selected service: `healys-v7-mrha-migration-v2-20260929.service`.
State: `nn_meta/validation/v7-mrha-payload-migration-20260929-r1/`:
`plan.json` / `files.sqlite3` own the finite manifest; `progress.json` and
`migration.jsonl` own measured progress/cutovers; `consumer-v2.json` binds recovery.
Scope is 504,516 sealed V7 raw payloads, 229.38 GB logical / 204.49 GB unique
content. Three SQLite-sidecar cases are excluded. Actual reclaimed space must be
measured; shared extents and active readers can delay or reduce reclamation.

Destination: `/run/media/healy/MRHA/HealysBacktester/sealed-v7-payloads-20260929/`.
Keep UUID 62C9-C390 mounted; restore catalog/instructions accompany external objects.
Original logical directories/receipts stay local; verified file links preserve
reader paths. Active V6 inputs/working data, features, models, indexes and writable
replay databases stay on the SSD. Do not reinitialize quota ledgers or subtract
retained migrated data from logical capture usage. Steam unchanged.

Sequential mover: CPU 100%, 768-MiB/1-GiB memory high/max, Nice 19, idle I/O,
no swap; 20-GiB MRHA reserve. Original v1 safely stopped on a hardlink alias's
ctime change; v2 binds the prior plan and checks that specific recovery case.
Check current receipt and exact service; launch is not completion. This supersedes
older observations saying no bulk migration had been performed.
[Scope, verification and recovery](reviews/2026-09-29-mrha-payload-migration.md).

### Completion observation — September 28, 2026

At **04:58:11 Central**, entry capture completed successfully with full entry
coverage, no stop reason and zero pending tasks. The completed/reused queue count
is **10,940,386**, reconciled against the original 10,941,828 joined ranges after
subtracting earlier indexed captures (net 1,442 fewer queue entries).
[Completion and automatic V6 handoff](reviews/2026-09-28-overnight-entry-completion.md).
The final receipt recorded 144.35 GB retained campaign files, 144.15 GB local free
and 743.72 GB MRHA free. References, held paths and remaining reconciliation still
keep the overall 7-3 gate open. The earlier ETA observations, including the
completed 18:30 check, are historical under `nn_meta/validation/v7-eta-check-20260927/`.

## V7 scope and selected inputs

Accepted V7 scope: March 15, 2022–September 14, 2026; 591 securities,
20 strategy families, 8,451 variant/timeframe combinations, 5/15/30-minute
signals and 221 downstream columns. Preserve one-minute execution, actual
1–9-DTE purchases, midpoint pricing/costs, the option-premium stop, strategy
exits, pre-close ITM expiry exit and funded physical fallback.
[Specification and accepted amendments](specs/MULTITIMEFRAME_RESEARCH.md).
No scope change is introduced by this index.

All shorthand roots below are under `nn_meta/validation/`.

| Input or completed work | Location |
| --- | --- |
| V7-2 completion | `v7-2-completion-20260925/complete.json` + `gate.json` |
| Frozen 591-security / 1,773-store catalog | `v7-2-full-catalog-20260922-rebuild-5-15-30/` |
| Full causal daily/market context | `v7-daily-context-20260925-full/` |
| Full completed demand | `v7-3-scheduler-20260925/demand/<security>/` |
| Full demand/entry union audit | `v7-3-entry-union-20260926/` |
| Existing packed coverage used by live campaign | `v7-execution-sample-index-20260927-r12/` |
| Dated reference demand | `v7-dated-reference-demand-20260927/` + sibling `.checkpoints/<security>/references.sqlite3` |
| Dated regular option hours | `v7-dated-hours-20260927/`; audit `v7-dated-hours-audit-20260927/` |
| Approved exact reference exclusions | `v7-contract-blackouts-20260928-approved/` (10,831 including the prior five); approval `docs/reviews/2026-09-28-v7-reference-exclusion-approval.json` |
| First-leg conservative envelopes | `v7-execution-envelopes-20260927/` + sibling `.checkpoints/` |
| Original five-path replay evidence (retained, superseded for continuation below) | `v7-execution-discovery-20260927-r12/` |
| Replay restart audit | `v7-execution-pilot-audit-20260927/` |
| Packed entry volume estimate | `v7-joined-packed-v2-forecast-20260926/` |
| Verified cleanup/migration | `v6-archive-migration-20260926/` and [review](reviews/2026-09-26-authorized-storage-reclamation.md) |

Raw dated reference sample: `nn_meta/data_v7/entry-joined-sample-references-20260926/`.
Raw execution packs: `nn_meta/data_v7/execution-frontier-20260927-r1` through `-r12`.
Historical exchange sources: `nn_meta/data_v7/option-hours-evidence-20260927/`
and `option-hours-followup-20260927/`. Captured calendar:
`nn_meta/data_v7/exchange-calendar-20260916/`.

## V7 input boundaries

The dated-reference **plan** is finished; the frozen full-scope reference **download** is complete, while
known entry exceptions are adjudicated under the approved finite policy. Actual held-date
admission remains open. The hours reconstruction is finished for the reviewed scope.
Exact exclusions are implemented; do not broaden them automatically. The entry
request plan/packing/cleanup and entry capture are complete; the dated-reference
campaign also completed. Replay machinery exists;
actual remaining paths/captures and full dataset
assembly still have to run. No full trained V7 artifact exists.

Model history remains 2022-03-15 through 2026-09-14. Regular-hours rule coverage
extends through 2026-09-23; do not confuse that with a model-history extension.
All 591 securities, 5/15/30 signals, 221 features and existing execution/fold
policies remain. Do not treat `research_ready:false` on an intermediate artifact
as evidence that its completed subtask failed. The legacy readiness checker has
stale pre-amendment/222-column requirements; consume current receipts instead
of rewriting freezes to turn that old report green.

## V7 execution continuation

The versioned shared/physical runner is connected. Latest actual ledger:
`nn_meta/validation/v7-integrated-execution-20260928-r3/`; quote snapshot:
`v7-frontier-quote-index-20260928-r3`; retained source paths:
`v7-execution-discovery-20260928-r3` (validation roots). Use these newer receipts
for integration; prior revisions remain valid evidence. The shared ledger completed
DIS/ABBV, retains NVDA at its next exact missing mark, and has not reached real
exercise/stock liquidation. Full V7-4 is still open. See the
[integration review](reviews/2026-09-27-v7-integrated-execution.md) and the current
three-argument `scripts/run_v7_integrated_execution.sh` launcher.

The September 28 r2 ledger preserves 1,466 earlier events and three decisions,
with 195 marks; cash was $87,596.26474814238 at that receipt.
Next NVDA240322C00910000 quote window:
`[1711039950000000000,1711039980000000001)`.
VKTX/FUTU source gaps remain. [Prefix preservation and continuation](reviews/2026-09-28-v7-reference-capture-and-frontier.md).
This remains five-path evidence, not full-universe execution coverage.

## V7 full-universe execution discovery

All roots here are under `nn_meta/validation/` unless specified otherwise.
This is separate from the retained five-path integrated ledger above.

| Scope | Selected location |
| --- | --- |
| Full immutable queue | `v7-full-execution-plan-20260928/jobs/<security>/`; live `progress.json` at plan root |
| Approved exception policy | `v7-contract-blackouts-20260928-approved/`; total 10,831 exact pairs |
| Recovery evidence / entry impact | `v7-reference-recovery-audit-20260928/`, `v7-reference-entry-impact-20260928/` |
| Quote base for next wave | `v7-frontier-quote-index-20260928-r4/` |
| Selected discovery campaign | `v7-execution-campaign-20260928-r1/` |
| Campaign progress / worker diagnostics | `progress.json`, `logs/<security>.log`, `waves/<security>/progress.json` beneath campaign |
| Per-security outcomes and missing requests | `waves/<security>/securities/<security>/wave.sqlite3` |

September 29 recovery: user selected resuming V7 after the V6 worker configuration
change, without waiting for catch-up/training. The original planner completed
591/591 securities, 793,394,264 proposals and 328,386,847 horizons; its September 29
service exited. Original wave worker/source contracts remain unchanged.

The completed evening/overnight continuation superseded the earlier daytime
invocation for the selected frozen replay queue. Historical recovery observations are retained in
[the outage census](reviews/2026-09-29-power-surge-recovery.md) and
[daytime recovery review](reviews/2026-09-29-v7-resumed-discovery-and-capture.md).

| Scope | Current location / service |
| --- | --- |
| Frozen actual requests | `v7-recovery-frontier-20260929-r0/`: 109,825 quote windows and 1,985 reference requests |
| Completed quote capture | `v7-frontier-capture-20260929-r0/progress.json`; `healys-v7-frontier-evening-20260929.service` |
| Raw quote packs | `nn_meta/data_v7/execution-recovery-20260929-r0/` |
| Prior evening continuation | `v7-evening-continuation-20260929-r0/progress.json`; checkpointed at 22:01 September 29 |
| Completed replay passes | `healys-v7-pending-overnight-20260929.service`; initial resumed pass, then supervisor continuation |
| Completed no-cutoff supervisor | `healys-v7-until-complete-20260929.service`; `v7-until-complete-20260929-r0/progress.json`, complete September 30 08:18 |
| Selected replay inputs/output | `v7-evening-continuation-20260929-r0/selected-replay.json`; same existing campaign checkpoint |
| Latest sealed capture index | `v7-frontier-capture-20260929-r0/index-receipt.json`; sealed evening r0, all 109,825 windows |
| Combined held/base references | `v7-reference-epoch-20260929-r0/`; 2,225,829 original contract/date responses |
| Exact alternate admission | `v7-held-reference-admission-20260929-r1/`; two exact dated-list recoveries |
| Approved new replay policy | `v7-contract-blackouts-20260929-held-approved/`; 10,835 pairs including all prior exclusions |
| Frozen actual-pending cohorts | `v7-pending-replay-plan-20260929-r0/`; 93 securities / 21,624,449 horizon-targets |
| Independent replay pilot | `v7-evening-replay-pilot-20260929-r0/`, `v7-evening-replay-parity-20260929-r0/` |
| Preserved original discovery | `v7-execution-campaign-20260928-r1/waves/`; controller `v7-execution-recovery-20260929-r0/`, original r4 inputs |
| Database recovery preimages | `v7-pending-replay-plan-20260929-r0.recovery/`; initial incomplete planner transaction also preserved |

September 30 at 08:18 Central: the no-cutoff supervisor completed after two
continuation passes. All 93 selected securities finished, with 21,624,449
horizon-target evaluations and no failures. Per-wave receipts sum to 129,873
pending input requests (not a deduplicated capture-window count). Supervisor
and campaign receipts now say complete/replayed_pending respectively.
Original full-universe discovery remains checkpointed. The completed 109,825-window
capture and frozen replay do not close full execution/input coverage or start training.
[Completion and remaining scope](reviews/2026-09-30-v6-step-policy-v4.md).
[Preflight, exact services and no-cutoff continuation](reviews/2026-09-29-v7-overnight-resume.md).

Independent per-horizon comparison matches all 20 pilot results. All remain
capture-incomplete with two further requests; this is not full replay acceptance.
The user approved four exact new exclusions; two other detail 404s were recovered
through exact list records without replacing raw provider evidence. Original
source-bound producers/ledgers remain; fresh inputs bind separate epochs.
[Evening evidence and approval](reviews/2026-09-29-v7-evening-continuation.md).
Neither snapshot capture nor bounded discovery closes 7-3 or execution gates.

### September 30 continuous required-input continuation

User selected finishing all of 7-3 where possible, without an overall cutoff.
This continuation supersedes the September 30 morning stopping point above.
Original discovery keeps its original inputs; new pending replay consumes new
sealed epochs. All roots below are under `nn_meta/validation/` unless stated.

| Scope | Selected location/service |
| --- | --- |
| Reconciled completed replay frontier | `v7-recovery-frontier-20260930-r0/`: 129,873 requests, 126,719 quote windows, 573 dated references |
| Current quote acquisition | `v7-frontier-capture-20260930-r0/`; initial service `healys-v7-frontier-20260930.service` |
| Current raw quote packs | `nn_meta/data_v7/execution-recovery-20260930-r0/` |
| Current sealed references | `v7-reference-epoch-20260930-r0/`; 2,226,402 original responses |
| New reference admission evidence | `v7-held-reference-reconciliation-20260930-r0/`; all 573 new pairs standard |
| Next frozen pending replay plan | `v7-pending-replay-plan-20260930-r0/`; 20,729,596 horizon-targets |
| Original discovery continuation | `v7-execution-recovery-20260929-r0/`; initial service `healys-v7-discovery-20260930.service` |
| Continuous discovery supervisor | `healys-v7-required-discovery-20260930.service`; `v7-required-inputs-20260930-r0/discovery/` |
| Continuous acquisition/replay supervisor | `healys-v7-required-frontier-20260930.service`; `v7-required-inputs-20260930-r0/frontier/` |
| Successive full-scope epoch receipts | `v7-required-inputs-20260930-r0/epochs/<ordinal>/` |
| Reconciler real-data verification | `v7-frontier-reconciliation-pilot-20260930-r1/` |

At 11:32 Central both supervisors were waiting for their exact initial services;
quotes and original discovery were making progress without reported failures.
The reference capture/audit completed at 11:21:57. The approved policy remains
`v7-contract-blackouts-20260929-held-approved/` (10,835 exact pairs); the new epoch
also preserves both prior exact-list admissions. No new exclusion was introduced.

Each supervisor binds its scripts. Four-/six-hour child checkpoints are resumed;
there is no overall cutoff. Existing completed captures/replays are not restarted.
Resource waits retain checkpoints. Explicit failures and unsupported actual
requests leave their precise evidence for investigation. Check service journals
and `progress.json` together; a waiting service is not proof of advancing work.
Only `closure_candidate_ready` reaches final evidence review, and it does not
itself close 7-3 or authorize training. [Workflow and verification](reviews/2026-09-30-v7-frontier-continuation.md).

### October 2 session-close receipts and pause boundary

Observation read at session close: selected discovery campaign receipt updated
**October 2 19:59:24 Central** (`2026-10-03T00:59:24.515148Z`) still reports
`running`, zero active/admitted workers and `resource_wait=memory reserve`.
Resource policy v4 reserves 25,600 MiB with `daily_reservation=true` despite
`incubator_mib=0`; worker ceiling is twelve. This is a scheduler wait, not lost
checkpoints or evidence of OOM. Fresh receipts must establish the next run state.

Original retained work at 16:00: 1,838,826 decision groups / 173,038,120 execution
scenario assessments, 74 terminal securities (66 full plus eight verified empty),
172 partial. Counts include pending-input outcomes. Epoch 00001 replay assessed
20,015,688/20,015,688 targets separately. Epoch 00002 capture failed at 15:38:49:
0/84,407 windows, 3,517 batches with Massive HTTP 403; frontier records
`RuntimeError: capture_v7_recovery_frontier.py exited 1`. Provider cancellation
is recorded; no replacement historical source or new exclusions admitted.
Evidence: `logs/lab-hourly-watch/runtime-1790974800.json` and selected receipts.

V6 October 2 r5 run ended **16:24:01 Central**, blocked at candidates/labels:
5/449 symbols complete, 444 incomplete, `training_started=false`; service exit 1.
Successful checkpoints retained. Earlier 16:03 counts were in-progress errors,
not this final result. Update/retry and watcher timers were disabled at the
subsequent user pause; [exact units](reviews/2026-10-02-user-training-pause.md).
Paper and unrelated services were unchanged by that pause. The session-close
V7-only work selection is owned by TODO/ROADMAP/DECISIONS, not inferred shutdown.

### October 2 discovery concurrency successor

The user requested maximum supported discovery concurrency and a measured ETA.
Resource policy v4 / scheduling controller v3 resumed at **13:39:30 Central**,
superseding the earlier two/four-worker policy after a checkpoint drain. Nine
workers were observed active at 13:40; consult fresh receipts for actual counts. Selected scientific campaign and wave
paths remain unchanged. Exact transition evidence:
`nn_meta/validation/v7-discovery-resources-20261002-r4/{before,stopped,deployment}.json`.
`measurement.json` and `measurement-summary.json` record the production trial.

Launcher: `scripts/finish_v7_discovery_resources_v4.py`; runtime override
`zzzz-resources-v4.conf` on the same discovery service. Dynamic admission permits
up to twelve workers, CPU threads minus two and available memory with owned
anonymous/kernel memory added back once. Budget: 1 GiB/worker; preserve paper,
incubator and host reserves. Service cap remains 14 GiB, new slices five minutes.
The existing optimized campaign declaration and scientific worker seals remain
unchanged; `discovery-campaign/resource-revision-v3.json` owns scheduler binding.
Read `resource_policy` and `active_securities` from live campaign progress for
actual admission; old dated two/four-worker counters are historical.
[Policy, validation and ETA limits](reviews/2026-10-02-v7-discovery-concurrency.md).

### October 2 optimized V7 adoption (selected)

User authorized adoption and resumption. Both existing services started at
**12:45:08 Central** using `scripts/finish_v7_optimized_inputs_v1.py`.
New root: `nn_meta/validation/v7-required-inputs-20261002-perf-r0/`:
- `discovery/progress.json`, `frontier/progress.json`: supervisor phases/errors.
- `discovery-campaign/{declaration,progress}.json`: original 591-security scope.
- `epochs/00001/replay/{declaration,progress}.json`: retained replay continuation.
- `waves/<security>` in each campaign selects one predecessor/successor;
  `revisions/<security>/inherited-checkpoint.json` owns import provenance.
- `adoption.json`, `deployment.json`, `canary-validation/{complete,parity}.json`
  and `verification.json` own deployment and observed results.

Watcher pointer: `logs/lab-hourly-watch/v7-selection.json`. Original parent
campaigns and completed captures remain preserved; routine counts now come from
this selected view. Runtime drop-ins: `zz-optimized-v1.conf` on the same
`healys-v7-required-{discovery,frontier}-20260930.service` names. Stop drains
bounded slices with a 30-minute service timeout. Dynamic daytime/overnight worker
limits remain as below; actual progress receipts distinguish active workers from
new admission capacity. This supersedes the 09:59 intentional pause.

The tested candidate's scientific methods are unchanged; new wave v4/replay v3
add verified copy-on-write imports to avoid duplicating about 80.93 GB of partial
checkpoints. A new campaign declaration preserves predecessor identities rather
than rebinding old waves. [Adoption and evidence](reviews/2026-10-02-v7-performance-adoption.md).
Original bounded comparison: `nn_meta/validation/v7-performance-20261002-r0/summary.json`;
[benchmark limits](reviews/2026-10-02-v7-performance-benchmark.md). Full gate closure
and whole-universe throughput are not established by adoption.

### October 2 discovery resource revision

At **08:00:11 Central**, discovery switched to
`scripts/resume_v7_discovery_resources_v2.py`, calling
`scripts/run_v7_execution_recovery_v2.py`. Same selected service, recovery
progress path and wave roots above. New source/resource anchors:
`discovery/resource-revision-v2.json` and recovery
`declaration-resource-v2.json`; original declarations remain unchanged.
Drop-in: `99-discovery-resources-v2.conf` under the existing runtime service.
Admission uses `scripts/lib/autosize.sh` through
`scripts/v7_discovery_resources_v2.py`: ceiling four overnight, two weekdays
07:00–21:00 Central; 3-GiB per-worker estimate and 12/18-GiB host available-memory
reserve respectively. Recomputed before dispatch; no forced termination when
capacity falls. Service high/max 12/14 GiB, no swap, no CPU quota.
At **08:00:55**, two active workers, fresh progress, no errors or OOMs. The
four-worker speedup remains unmeasured. All 195 existing wave declarations were
verified unchanged after a clean checkpoint stop. Evidence:
`nn_meta/validation/v7-discovery-resources-20261002-r0/`.
[Resource revision and measurement limits](reviews/2026-10-02-v7-discovery-resources.md).

### October 1 V6 occurrence repair — completed r5, selected daily root

**02:32:01 Central:** r5 through September 30 completed all 449 symbols and 40
training members, evaluated and froze 122 verified candidate payloads, zero errors.
Candidate: `incubator/continual-v6/r5/runs/2026-09-30/candidate/`;
complete SHA-256 `4d8693a739c3eb9169f73bb334ee6c11b7fba35c35872b17ef94b9a4093d9a08`.
Recovery elapsed 56m22s, training 39m32s, evaluation/freeze 6m25s. Reused 447
completed symbols; this is not a clean unattended daily timing result.
All 447 seals plus CRSP/MTUM old feature and completed-label references preserved.
333,260 candidates: 120,249 matured, 100,167 pending, 112,844 unfilled.
Diagnostic rejected on return MSE (5.335516 vs parent 5.335310/zero 5.325535);
Brier improved (0.213463 vs 0.213882). Updated freeze retained; no deployment.

Root/config: `incubator/continual-v6/r5`, `deploy/incubator-continual-v6-r5.json`.
Persistent `healys-v6-continual.service.d/50-daily-v5.conf` selects
`scripts/v6_continual_resume_v5.py`. Temporary 90-r4/95-r5 runtime overrides were
removed; normal daily resource policy and timer restored. Subsequent same-date
runs may report `candidate_already_frozen`; inspect original completed result.
`nn_meta/validation/v6-daily-repair-20261001-r5/` owns `incubator-result.json`,
`completed-data-audit.json`, `completion-verification.json`,
`restored-services.json` and `restored-progress-verification.json`.
CLI and hourly watcher select r5; existing open old viewers need restarting.

Original discovery and migration restarted automatically at 02:32. Frontier
initially failed on two prior HTTP 502 batch receipts. Versioned transport recovery
restarted it **02:48:11** under the same service, via runtime
`healys-v7-required-frontier-20260930.service.d/98-transport-recovery.conf` and
`scripts/resume_v7_frontier_transport_20261001.py`. This admits only the exact
archived stopped pass for one retry through the unchanged producer; all completed
packs and failure receipts remain. It then returns to normal controller checks.
Evidence: `nn_meta/validation/v7-frontier-restart-20261001-r0/`.
At **02:49**, discovery had fresh active securities, capture reached
64,584/126,719 windows with no current failed batches, and migration reached
275,575 files / 204,212,780,359 logical bytes. All three had active cgroup CPU.
Timers for daily V6, backup and archive were re-enabled by the saved restoration
plan. These are dated observations; inspect current receipts for ongoing health.
[Repair, diagnostics and restart evidence](reviews/2026-10-01-v6-occurrence-repair.md).

### September 30 23:04 V6 two-day update — historical r4 attempt


**23:18:23 Central dedicated resource revision:** same daily service and r4 root,
temporary runtime drop-in `90-dedicated-r4.conf` invoking
`scripts/v6_daily_dedicated_20260930.py`. Actual five autosized data workers,
16 training threads, 25/26-GiB high/max, no CPU quota. All 32 completed symbol
seals unchanged; five fresh symbol updates at 23:18:50. Competitors/timers paused
again; verified candidate completion removes the temporary override and restores
them. Evidence: `nn_meta/validation/v6-daily-update-20260930-r4/dedicated/`.
Frontier stop exceeded three minutes and used SIGKILL; its saved state is retained
but resumed capture health must be checked. Migration checkpointed cleanly.
The following launch observation describes the superseded coexistence allocation.

Selected daily root: `incubator/continual-v6/r4/`; configuration
`deploy/incubator-continual-v6-r4.json`; status `latest-run.json`, resources
`resources.json`. `healys-v6-continual.service.d/40-daily-v4.conf` selects
`scripts/v6_continual_resume_v4.py --autosize-workers`. Actual run started
23:04:36 Central through September 30, three data workers/two training threads,
20-GiB hard ceiling and 400% CPU. Timer restored; next opportunity 00:00 Central.
`nn_meta/validation/v6-daily-update-20260930-r4/` owns preparation, failure archive,
pilot and launch receipts. Frozen-prefix snapshots retain old bars and audit
provider revisions; 231,323 prior seals verified by reference. Stage timestamps
support measurement. Full completion is pending; inspect current receipts.
Watcher defaults now select r4/daily service; restart an old viewer to load them.
[Scope and evidence](reviews/2026-09-30-v6-two-day-update.md).

### Hourly terminal health watcher

**October 2, approximately 16:43 Central — user pause:** V6 continual, data and
context-retry timers and both lab/legacy V7 hourly timers are disabled/inactive.
No model training process remains active; continual retains its preceding failed
result with MainPID=0. Watcher state has `stopped=true`. No automatic restart
time chosen. Session-close direction subsequently deferred non-V7 work until V7
is done; do not infer a tonight restart. Existing seals/checkpoints retained.
[Exact paused units and verification](reviews/2026-10-02-user-training-pause.md).

**October 2 reporting scope:** hourly messages focus on V6 Alpaca paper trading
and V7 gate 7-3. Completed migration/storage summaries are omitted; storage is
mentioned only for a new active-work blocker. V6 incubator appears while active
or needing attention; a successfully sealed daily update is omitted even if its
diagnostic verdict is adverse. Selected run comes from r5/latest-run.json.

`scripts/lab_hourly_watch.py` now captures `v7_work`: cumulative discovery
cohorts/decision groups and horizon-target assessments, outcome counts, finished
and partially processed securities, plus separate per-round replay totals and
frozen replay denominators. Pending-input outcomes are included in assessments;
these are not final training labels. Never add discovery/replay rounds together
as unique work. Full-discovery percentage remains unavailable without a matching
verified denominator. Deltas compare the preceding saved hourly work snapshot,
not the current pass or a same-slot refresh; the first new snapshot has no delta.
`incubator_visibility` records whether a run should appear. A dedicated scanner
journal prevents frequent broker logs from hiding scanner failures.
Producer changes take effect on the next invocation of the existing service;
no trading/research service restart. Both legacy/new queue prefixes deduplicate.
12 focused watcher tests passed; live cumulative readback at 09:43 Central found
1,527,621 discovery cohorts and 143,241,170 horizon-target assessments, including
79,980,410 capture-incomplete assessments. These are dated work measurements.


September 30 **23:36 Central**: `healys-lab-hourly-watch.timer` installed,
enabled and active; next slot **October 1 00:00 America/Chicago**, then each :00.
Service/producer: `healys-lab-hourly-watch.service` / `scripts/lab_hourly_watch.py`.
Bound target verified without sending: `01a0f343-c76a-7842-915b-0c111e8e2e28`.
Top-of-hour timer uses one-second accuracy/no jitter; busy delivery retries every
minute and coalesces pending checks. Reports appear in this terminal. This is
read-only health diagnosis; the dedicated V6 controller owns automatic sequencing
and restoration. Prior older-conversation V7 updater was left unchanged.
`logs/lab-hourly-watch/runtime-preflight.json` is the deployment host observation;
`runtime-<UTC-slot-epoch>.json` preserves hourly evidence, `runtime.json` the
latest host observation, and `state.json` records queued/started delivery (created
at the first actual dispatch). Dispatch alone does not prove a completed report.
Five focused dispatch tests and installed unit validation passed.

Historical observation before the r5 repair: the initial host snapshot at **23:36:47** found V6 active, 115/449 complete,
with CRSP `Daily parent artifact inputs differ`; this is an actual unresolved
build error, not an expected pause. Other workers continue, but errors prevent
training/freeze and restoration after the pass. Read-only reproduction in
`logs/lab-hourly-watch/crsp-input-mismatch.json` found unchanged stock prefix
hashes but an additional `tv_rating` ordinal-1 occurrence at September 28 19:45
when history is extended through September 30. The inherited batch has only
ordinal 0 for that strategy, so exact declaration checking rejects reuse.
No bound producer/artifact was changed and no research job was restarted.
Do not infer successful overnight completion from the configured sequence.

### September 30 dedicated V6 handover — candidate completed and jobs restored

**Completion observation, September 30 22:40:57 Central:** selected r3 run through
September 28 is `candidate_frozen` / `done`, 449/449 symbols and 40/40 members.
Candidate `incubator/continual-v6/r3/runs/2026-09-28/candidate/` has 122 verified
payload files; verdict `rejected` (return MSE exceeds incumbent and baseline).
Previous model retained; no deployment. Training took 35m29s, evaluation/freeze
5m36s. Focus state is `restored`; success/0 exit at 22:40:49. Restoration readback
showed migration and both V7 successor services active. Inspect current receipts
for subsequent health. Old merged error fields in focus progress are historical;
final candidate and exit receipts establish completion. The completed freeze remains through September 28; latest closed date is
September 30. Daily freshness is therefore not yet current. The installed
`healys-v6-continual.timer` schedules 15:45 Central weekdays plus overnight
00:00–07:45 quarter-hour retry opportunities. Its original enabled/active state
was included in the successful restoration. Subsequent live health needs readback.
Diagnostic rejection retains both new data and the completed candidate freeze;
it does not prevent subsequent daily updates. Details below describe the
historical handover/recovery, not a still-running V6 catch-up.

The selected one-time timer is `healys-v6-focus-20260930.timer`, starting
`healys-v6-focus-20260930.service` at **15:01 Central September 30**. This takes
precedence over the preceding continuous-V7 observation and the normal 15:45
V6 timer for this interval. Installed timer is enabled/active/waiting with the
exact 15:01 next event; service was inactive at preparation. `schedule.json`
retains installation/preflight hashes. Scheduling is not proof the handover ran.

Runtime evidence: `nn_meta/validation/v6-focus-20260930/progress.json`,
`pause-plan.json`, `paused-services.json`, `incubator-result.json`,
`restored-services.json`, `service-exit.json` and the exact service journal.
V6's actual pipeline receipt remains `incubator/continual-v6/r3/latest-run.json`.
At handover, competing local V7/migration/FA/backup/data/scanner jobs are paused;
basic order management/monitoring and hourly reporting continue. Actual V6
startup follows checkpoint drain. Selected pinned catch-up remains September 28.

V6 allocation: 25/26-GiB high/max, no swap, no CPU quota, all available training
threads (16 observed), 4500-MiB data-worker budget with 4096-MiB host reserve.
Automatic restoration follows a verified completed candidate, including its
evaluation; failure/incomplete/deadline keeps competing jobs paused for review.
The next-morning research cutoff and all model/admission contracts remain.

September 30 **16:33:47 Central worker revision**: selected service drop-in
`healys-v6-focus-20260930.service.d/20-workers.conf` now invokes
`scripts/v6_focus_workers_20260930.py --worker-mib 3584 --auto-restore`.
Actual restart selected **five data workers** (five processes verified), keeping
4096-MiB host/2048-MiB parent reserves and 25/26-GiB high/max. All **357** completed
symbol seals were retained unchanged; catch-up/training method is unchanged.
`nn_meta/validation/v6-focus-20260930/worker-revisions/r1/` owns prior-run and
restart evidence. The earlier `service-exit.json` records the deliberate old-pool
stop; compare its timestamp with the newer running receipt and live journal.

Terminal viewer: `./venv/bin/python scripts/watch_v6_incubator.py --follow`.
Reads the selected r3 `latest-run.json`, focus progress and live service memory;
refreshes every five seconds across data, training and evaluation/final freeze.
September 30 16:47:44 Central: separate Konsole viewer confirmed running,
362/449 symbols complete, training pending, service memory 3.98/26 GiB.
This is a dated observation, not a claim of continuing health.

September 30 **20:47:50 Central transport resume**: the main pass stopped at
19:15 with 35 failures. The separate HTTP-502-only retry worker recovered ten
symbols and exited `needs_review` at 20:13 because the other 25 had distinct
transport-error messages. Verified actual completion was **424/449**.
Resumed the same focus service after both workers/services had stopped, retaining
all 424 seal hashes. Five autosized workers; at 20:48:12 fresh WFC/WMT/WPM/WULF/WYNN
progress was observed, 424/449 main count, no new errors, training pending.
`nn_meta/validation/v6-focus-20260930/transport-resume-r1/` owns before/after and
archived failure receipts. The old `symbol-retries-r1/` remains historical;
its helper is bound to the old invocation and must not be restarted as-is.
Unchanged data checks lead automatically to training/evaluation/freeze;
further failures still require review. This observation does not prove completion.

Restored V7 uses the same supervisor names and checkpoint roots, with separately
bound `scripts/resume_v7_compute_20260930.py`: up to two discovery workers,
four quote workers and the existing one serial replay worker; 8/6-GiB service
limits, CPU quotas removed. Actual worker counts remain memory-aware.
[Scope, restart details and verification](reviews/2026-09-30-v6-dedicated-compute.md).

One-time terminal report: `healys-v6-handover-update-20260930.timer` / `.service`,
installed/enabled for **15:05 Central September 30**. Verified target thread is
`01a0f343-c76a-7842-915b-0c111e8e2e28`; the older hourly updater remains separately
bound. `logs/v6-handover-update-20260930/{state,runtime}.json` records request
submission and dispatch-time host observations. A submitted request is not proof
of a completed report. Read-only update covers migration/V7 stopping totals and
V6 actual startup; busy-thread retries do not interrupt user work.

Measured 13:39:30–13:54:30 Central: +2,362,080 assessments, 9.448M/hour,
7–9 active workers; 1,493,431,400 remaining gives 6.59 continuous days at that
rate for original discovery only. Paper was Massive-403 blocked; full scanner
co-load and calendar completion are not established. See measurement-summary.json.

## V6 Alpaca paper and incubator

### October 2 ten-minute entry policy

User-authorized cutover installed at 10:36:02 Central. Selected scanner is v11
(`scripts/run_v6_alpaca_scanner_v11.sh`), consumer v2 and broker runtime v6.
Entry admission/allocation/source retention use 600 seconds from signal close;
quote freshness and order ladder pricing/waits are unchanged. Drop-ins
`99-ten-minute-v11.conf` (scanner) and `99-ten-minute-v6.conf` (orders) supersede
the earlier launchers below. Current manifest SHA:
`e6d33229e249ffd4a0ba0f116cf73434b16fb97c91e834f71ad250c424f31c06`.
[Change, tests and evidence](reviews/2026-10-02-v6-ten-minute-window.md).
Earlier dated runtime descriptions below retain their historical scope.


Configuration and startup were verified at the September 27 activation:
[deployment/runbook](reviews/2026-09-27-v6-alpaca-activation.md) and
[receipt](reviews/2026-09-27-v6-alpaca-activation.json).
The fresh state's `paper-restart.json` enables scanning and paper submission;
`broker-status.json`, `scanner-dispatch-status.json`, `latest-preview.json`,
`portfolio.sqlite3` and `broker-orders.sqlite3` own actual subsequent state.
Read SQLite evidence in read-only mode.

- Scanner: `healys-v6-alpaca-scanner.timer` / `.service`, every 15 minutes in
  its configured window; v11 launcher/adapter and ten-minute consumer, memory-aware
  sizing up to 11 workers within a 16 GiB cap (14 GiB high, no swap).
- Broker: `healys-v6-alpaca-orders.timer` / `.service`, every 15 seconds in its
  configured window; market/calendar checks govern execution. Since September 30
  10:33 Central, `scripts.run_v6_alpaca_runtime_v6` now selects the retained three-step orders:
  fixed initial midpoint buy 1.05/1.10/1.125, sell 0.95/0.90/0.875, waits
  30/30/60 seconds, buys rounded up and sells down. Legacy chains retain their
  saved policy. Cancel confirmation precedes replacement; partial fills,
  ownership and maximum-step buy reservations remain enforced.
  [Policy, deployment and actual retry fills](reviews/2026-09-30-v6-step-policy-v4.md).
- Read-only monitor: `healys-v6-alpaca-paper-monitor.timer`; output
  `/tmp/v6-alpaca-paper-monitor-latest.json` (ephemeral observation).
- Daily producer retained: `healys-v6-data.timer`; scanner reads the latest
  immutable index from the old state's `data-index.json`. This shares inputs,
  not historical positions.
- Old home forward/risk/relay/projected-ledger/session-update schedules and the
  old server V6 watcher were retired. The old Stonks simulator projection is
  historical; it is not the new account's actual fill history.

October 1 repair snapshot (historical; current scans follow `data-index.json`):
`nn_meta/live/v6_server/data/2026-09-30-vintage-20261001-r1/`,
published October 1 at **10:45:53 Central**, manifest SHA
`535dde7c63a7bc226a9f34b21b0cda18b8cf051128bbf7611e54b163ab825441`.
The original V6 data-index source points to it; model/release remain unchanged.
The prior September 30 snapshot is preserved. TLT adjusted history was restated;
the new snapshot and fresh raw/adjusted overlap passed validation for the full
universe. Repair evidence: `nn_meta/validation/v6-paper-vintage-20261001-r0/incremental/`.
[Repair and scanner verification](reviews/2026-10-01-v6-paper-vintage-repair.md).
The hourly watcher now checks Alpaca scanner/broker receipts independently of
the incubator, with paper service observations and a separate paper journal.
October 1 predecessor launcher: `scripts/run_v6_alpaca_scanner_v10.sh`; source reconciler v3
continues to protect active chains and distinguish prior fills from new unfilled
signals reusing their contract. New consumer `scripts/run_v6_forward_resilient_v1.py`
runs held monitoring alongside detection, retrying only empty fresh-quote errors.
Allocation still requires successful monitoring and the frozen entry deadline.
The model, feature modules, 30-second quote validation and broker policy are unchanged.
October 1 predecessor manifest SHA:
`06459ec7cb58784cc35af07030c88f0685540a167074dd1c97fcb0a30e150f9c`.
October 1 predecessor admission: `healys-v6-alpaca-scanner.service.d/95-monitor-v10.conf`;
resource limits remain selected by `90-resource-v9.conf`.
Prior manifest/unit: paper `runtime-revisions/scanner-monitor-v10-20261001/`.
`position-monitor-status.json` records quote attempts and completion/blocking;
its timestamp must match the pass before drawing conclusions. It is absent on
idle startup. The hourly watcher reads it with scanner and broker receipts.
At October 1 15:32:54–15:32:57 Central, installed v10 exited successfully with
all 449 symbols verified and `idle / outside_market_hours`; broker polling was
`market_closed` at 15:34. Market-hours recovery/timing remains unverified.
[Quote recovery evidence and acceptance](reviews/2026-10-01-v6-paper-quote-recovery.md).
Earlier same-day TLT recovery, v9 scan timing and FLY quote failures remain in
[the prior repair review](reviews/2026-10-01-v6-paper-vintage-repair.md).
These are dated observations; current receipts own present health.
Previous manifest/services/databases: `runtime-revisions/scanner-contract-reuse-v3-20260930/`
and `runtime-revisions/step-policy-v4-20260930/`.
Older runtime lineage remains intact; historical readiness/activation evidence is
linked from [the prior step-policy review](reviews/2026-09-28-v6-step-orders.md).

September 30 at 10:40 Central: all 77 broker orders match journal status/fill
quantity. Zero open orders; AXP ×7 and VG ×104 approved one-time retries filled
at step 2 for $9.75 and $0.70 respectively. WFC ×26 remains. The 10:30 scanner
failed before cutover on no fresh post-decision WFC quote. The 10:45 scan then
blocked on an unfilled VG projection retained because of earlier same-contract
fills. Reconciler v3 deployed 10:59; the 11:00 scan archived that exact VG source
and completed in 256.537 seconds: 308 candidate rows, zero detection errors,
444 symbol results and five without a current bar. Order service v5 is successful;
both timers remain selected. [Dated observation](reviews/2026-09-30-v6-step-policy-v4.md).
Per-pass source reconciliation: `scanner-source-reconciliation.json`. Read
current scanner/broker receipts for subsequent holdings, fills and health.

Continual V6 incubator configuration: `deploy/incubator-continual-v6-r3.json`.
The anchored base is `nn_meta/campaigns/v6-cash-repair-20260913/v6/artifacts/meta_dataset.parquet`;
new candidates start August 25. Its input index remains
`/home/healy/Coding/HealysV6/nn_meta/live/v6_server/data-index.json`, independent of
paper selections. Research output root: `incubator/continual-v6/r3/`.
Provider evidence is reused from `r1/market/`; prior r1 seals are retained.
The initial September 28 snapshot is pinned by hash in the selected config.

- `latest-run.json` and `runs/<session>/status.json`: actual stage, failures and counts.
- `features/`, `labels/`, `market/`: sealed incremental data and retained evidence.
- `runs/<session>/symbols/`, `progress/`, `arrays/`, `candidate/`: checkpoints and models.
- `latest-candidate.json`: newest fully frozen candidate; `latest-accepted.json`:
  newest candidate passing the research diagnostic gate. Neither deploys a model.
- Service/timer: `healys-v6-continual.service` / `.timer`, 16:45 New York weekdays;
  every 15 minutes from midnight through 07:45 Central Monday–Saturday for
  overnight retries. Units live in `deploy/systemd/`.
  The service also requires successful completion of the selected V7 entry
  download (campaign `8ea809659f0647dbbfef9682321a6828dc182ccac1bbbe9d3e2d5bfb4e99f568`).
  A failed, paused or missing V7 receipt keeps V6 deferred. After completion, the
  next normal timer opportunity can resume V6, subject to daily-input readiness.
  A calendar-aware condition also blocks starts between today’s open minus
  30 minutes and close plus 15 minutes, including late persistent-timer starts.
  `journalctl --user -u healys-v6-continual.service` owns runtime logs.

The corrected r3 full-universe run started September 28 at 23:07:14 Central.
It preserves 38 completed r2 symbols, 4,623 feature seals and 23,569 label seals
by hash-bound inheritance. The original repair evidence covers all 17 r2 errors.
September 30 observation: **325/449 complete**, with 124 remaining timeout/deadline
entries at the 08:00 calendar cutoff. The 05:32 retry retained prior completed
symbols. Service is inactive after its market-hours guard; next timer 15:45 Central.
Training/freeze have not started. The unfinished September 28 snapshot stays pinned.
[Latest observation](reviews/2026-09-30-v6-step-policy-v4.md),
[prior restart evidence](reviews/2026-09-29-paper-reconciliation-v6-resume.md).
[Worker sizing and validation](reviews/2026-09-29-v6-worker-sizing.md),
[retained repair evidence](reviews/2026-09-28-v6-continual-error-repair.md).
Selected code: `scripts/run_v6_continual_v3.py`, `incubator/recovery_v6/`;
retry wrapper: `scripts/v6_continual_resume_v3.py --autosize-workers`. Original inheritance census:
`incubator/continual-v6/r3/inherited-r2.json`; prior installed unit/exit receipt:
`incubator/continual-v6/r3/runtime-revision/`. The unfinished date AND snapshot
stay pinned across retries. Installed allocation: up to four autosized data workers,
4500 MiB each with 8192 MiB host reserve; CPU 400%, 19/20-GiB high/max, no swap.
Training remains two threads. Current sizing returned three; startup determines
actual concurrency. The authorized 17:31 restart selected three workers;
future starts autosize again. The 12-hour budget and calendar cutoff remain.
`service-exit.json` records termination separately from stale progress.
[Original r2 recovery](reviews/2026-09-28-v6-continual-recovery.md) and
[r1 memory failure](reviews/2026-09-28-v7-reference-completion.md) are historical.
Full-universe catch-up, full training and nightly latency remain unproven.
[Original implementation/pilot](reviews/2026-09-27-v6-continual-incubator.md).

The replay-only `healys-ai-incubator-after-close.timer` was disabled at activation.
Its Friday inference receipts remain historical under `incubator/runs/after-close/`
and `incubator/artifacts/daily/`. [Historical audit](reviews/2026-09-27-incubator-fa-alpaca-readiness.md).
V5 trade-outcome scoring is superseded by the continual-training scope.

## FA collection and evaluation

Operational paths below are relative to `/home/healy/Coding/HealysAutomation`:

| Evidence | Path |
| --- | --- |
| Runtime configuration | `deploy/fa-runtime.json` |
| Source archives | `fa/archive/<source>/<month>.parquet` |
| Job receipts and health | `logs/job-health/<job>/latest.json` |
| Immutable feature snapshots | `fa/artifacts/enrichment/<timestamp>/manifest.json` and `features.parquet` |
| Experimental evaluation reports | `fa/artifacts/enrichment_reports/<timestamp>.json` |
| Outcome prices and session calendar | `fa/daily_prices/`, `inputs/calendar.json` |
| Prospective monthly artifacts | `fa/artifacts/prospective/` |
| Evaluation implementation | `fa/evaluate_features.py` |

**Observed September 27:** collection/enrichment/evaluation jobs were healthy;
raw partitions include July, August and September. The expanded snapshot
pipeline began September 10 Chicago (September 11 UTC), with 17 consecutive
daily snapshots through September 26 Chicago. Raw collection predates it.

Snapshot `20260927T014037632061Z`: 300 symbols; financials 232, float 228,
short interest/volume 300 each, price-history features 120.
Report `20260927T020036287757Z.json`: 960 eligible rows across **six distinct
entry dates**, no folds, `insufficient-purged-history`. These six dates are
not total collection days. Labels use the first session close after capture
through the fifth subsequent session close; newer snapshots await outcomes.
The evaluator requires 40 training days and 10 test days with purging.

Collection is daily (some sources more frequent); monthly cohort freezing is
a separate scheduled task. At inspection the first prospective monthly run
was scheduled September 30 at 20:15 Chicago, with no clean cohort yet present.
Reddit/EDGAR use server collection and archive transfer; local skip settings
are not evidence that these sources are globally disabled.

The old August ranking's cutoff defect disqualifies that ranking as clean
forward evidence; it does not discard all earlier raw data.
[FA reference](reference/FA_CONTEXT.md), [original cutoff finding](reviews/2026-09-05-live-ops-audit.md).

## Pointer maintenance

Change a selected pointer only with evidence identifying its scope and what
it supersedes. Preserve old receipts and immutable declarations. Update the
owning gate/task only if its status actually changes. Keep historical sample
counts, transient rates and test totals in their dated reviews; do not make
another running-status section in README, GOALS or DOCUMENTATION.

## October 2 V6 paper Alpaca options transition

Selected scanner v12: `scripts/run_v6_alpaca_scanner_v12.sh` / `.py`, consumer
`scripts/run_v6_forward_resilient_v3.py`, adapter `scripts/v6_alpaca_market_v1.py`.
Installed drop-in: `99z-alpaca-options-v12.conf`. At 14:20:49 Central, manifest
`72dda355ea27c0e8d355949fc7185e4ce64e88bf2825d635936b7796137ff420` admitted
Alpaca held quotes and blocked unvalidated full-universe entry features. At
14:23:50 held monitoring completed with zero errors; scanner entry status remained
blocked as intended. Old Massive-403 receipts are historical, not the selected path.

Evidence: `nn_meta/validation/v6-alpaca-provider-20261002-r0/`; deployment,
verification, stream census and bounded recorder probes. No full-universe recorder
or feature adapter is admitted. Existing model/universe and frozen sources remain.
[Transition, limits and remaining admission](reviews/2026-10-02-v6-alpaca-provider.md).

At 14:55:03 Central, the account rejected the 2,434-contract quote subscription
with 405 (symbol limit exceeded); `capacity-verification.json` preserves the
actual entitlement failure. No full-universe recording is running.
