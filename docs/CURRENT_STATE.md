# Current state and artifact index

Pointer/configuration owner for the lab, reconciled September 29, 2026.
[ROADMAP](../ROADMAP.md) owns milestone status and acceptance conditions;
[TODO](../TODO.md) owns selected work. This page selects exact inputs and
runtime identities. Other current documents link here instead of copying them.

**Evidence freshness:** V6 research and V7 queue/discovery were checked September
29; the dated observation below distinguishes running processes from stopped jobs
with stale progress. Other sections retain their own dated scopes and timestamps.
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

Selected recovery launcher: `bash scripts/start_v7_recovery_20260929.sh` with
`discovery`, `capture`, `references`, `retries` or `references-recover` modes.
Do not blindly relaunch active services or completed acquisition scopes.

| Scope | Current location / service |
| --- | --- |
| Recovery controller | `v7-execution-recovery-20260929-r0/`; `healys-v7-execution-recovery-20260929.service` |
| Mutable replay checkpoints | Original `v7-execution-campaign-20260928-r1/waves/`; original parent marked stopped with successor |
| Frozen actual requests | `v7-recovery-frontier-20260929-r0/`: 109,825 quote windows plus 1,985 reference requests |
| Quote capture progress | `v7-frontier-capture-20260929-r0/progress.json`; `healys-v7-frontier-capture-20260929.service` |
| Raw quote packs | `nn_meta/data_v7/execution-recovery-20260929-r0/` |
| Bounded missing-batch retries | `healys-v7-frontier-retry-20260929.service`; waits for capture exit, up to three passes before cutoff |
| New quote index | Consume only sealed path/hash from `v7-frontier-capture-20260929-r0/index-receipt.json`; initial target ends `20260929-r5`, retry indexes include invocation/pass |
| Held-reference capture / audit | `v7-held-reference-campaign-20260929-r0/`, `v7-held-reference-reconciliation-20260929-r0/` |
| Held-reference alternate recovery | `v7-held-reference-recovery-20260929-r0/`; raw packs under `nn_meta/data_v7/held-reference-recovery-20260929-r0/` |

Dated post-interruption observation, September 29 at 16:36–17:05 Central:
all three transient V7 discovery/capture/retry services are absent/inactive.
Progress JSON still says running/capturing; it is stale. Verified 3,005 packs /
72,120 of 109,825 quote windows; 37,705 remain. The last controller had recorded
290 HTTP-502 failures. No r5 combined index or index receipt was sealed.
All 93 wave receipts survive: 28 discovered, 61 checkpointed, two previously
interrupted, two stale-running. Copies of both interrupted workers' databases and
rollback journals recovered and passed quick checks; originals remain untouched.
Frozen snapshot and controller-bound source hashes pass. Full checked census:
[power-interruption recovery](reviews/2026-09-29-power-surge-recovery.md).
The 12:52 observation is retained in the earlier recovery review.

Two discovery workers: 5/6-GiB high/max, CPU 200%. Four quote workers: 5/6-GiB,
CPU 200%. No swap. Both stop dispatching at 15:00 Central and drain; the retry
wrapper also respects that cutoff before V6's 15:45 timer. Observe actual exits.
The controller's discovered counter covers its current traversal; inspect all
retained per-wave receipts for the global census during the incomplete traversal.

All 1,985 held-reference requests were captured/audited: 1,979 standard, six detail
404s. Both alternate-list queries for each missing pair completed, finding exact
matches in two queries. Admission review and remaining unknown dispositions are
open; no new exclusions were approved or activated. Existing 10,831-pair policy
is unchanged. New references/quotes require new bound replay epochs; the current
discovery still uses the frozen original r4 quote/reference inputs.
[Recovery, tests and observation](reviews/2026-09-29-v7-resumed-discovery-and-capture.md).
Neither snapshot capture nor discovery completion closes 7-3 or later execution gates.

## V6 Alpaca paper and incubator

Configuration and startup were verified at the September 27 activation:
[deployment/runbook](reviews/2026-09-27-v6-alpaca-activation.md) and
[receipt](reviews/2026-09-27-v6-alpaca-activation.json).
The fresh state's `paper-restart.json` enables scanning and paper submission;
`broker-status.json`, `scanner-dispatch-status.json`, `latest-preview.json`,
`portfolio.sqlite3` and `broker-orders.sqlite3` own actual subsequent state.
Read SQLite evidence in read-only mode.

- Scanner: `healys-v6-alpaca-scanner.timer` / `.service`, every 15 minutes in
  its configured window, dynamically sized workers (v6 adapter: up to eight), 12 GiB memory limit.
- Broker: `healys-v6-alpaca-orders.timer` / `.service`, every 15 seconds in its
  configured window; market/calendar checks govern execution. Since September 28
  15:08 Central, `scripts.run_v6_alpaca_runtime_v4` selects independent four-step
  orders: fixed initial midpoint ±2.5/5/7.5/10%, waits 30/30/30/60 seconds,
  buys rounded up and sells down. Cancel confirmation precedes replacement;
  partial fills, ownership and maximum-step buy reservations remain enforced.
  [Policy/deployment evidence](reviews/2026-09-28-v6-step-orders.md).
- Read-only monitor: `healys-v6-alpaca-paper-monitor.timer`; output
  `/tmp/v6-alpaca-paper-monitor-latest.json` (ephemeral observation).
- Daily producer retained: `healys-v6-data.timer`; scanner reads the latest
  immutable index from the old state's `data-index.json`. This shares inputs,
  not historical positions.
- Old home forward/risk/relay/projected-ledger/session-update schedules and the
  old server V6 watcher were retired. The old Stonks simulator projection is
  historical; it is not the new account's actual fill history.

At the September 28 readiness repair, a 10:30 Central scheduled full scan
completed in 243.058 seconds with 281 candidate rows and no detection errors.
One actual paper limit order was accepted, then canceled unfilled and reconciled;
first-fill observation remains pending. [Readiness evidence](reviews/2026-09-28-v6-paper-readiness.md).
Selected input snapshot is now
`nn_meta/live/v6_server/data/2026-09-25-vintage-20260928/`, manifest SHA
`fe2ab69e315faaa710fc95f108480354d919141841b88bbc46d6b2423b78a151`.
The existing V6 data-index source points to it; the old snapshot/model remain intact.
Scanner launcher: `scripts/run_v6_alpaca_scanner_v6.sh`. Earlier activation lineage is
retained under the paper state's `runtime-revisions/scanner-v3-20260928/`.
Order-policy lineage remains at `runtime-revisions/orders-v2-20260928/`.
At 14:21 Central, scanner v4 archived an expired, never-filled ANF projection
after authenticated zero-holdings/zero-pending reconciliation. The database
snapshot and previous manifest/unit are at `runtime-revisions/scanner-v4-20260928/`.
[Repair and prospective scan evidence](reviews/2026-09-28-v6-unfilled-source-repair.md).
The 14:30 scan completed in 254.253 seconds with 274 candidate rows and no
detection errors; IONQ/CRM orders were submitted at 14:34:30 and confirmed
canceled with zero fills by 14:37:01. The 14:45 scan archived both automatically
and completed in 256.738 seconds. Scanner v6 now also protects active step chains
during cancellation gaps; the original never-filled-entry protection remains.
Current paper-manifest SHA:
`f7467a569c5db625d480390d59dc048a66024690f73ff11ebc7ad7658a0a2898`.
Prior manifest/services/databases: `runtime-revisions/step-orders-v3-20260928/`
and `runtime-revisions/step-orders-slices-20260928/`.
At the 14:52 cutover there were zero holdings/pending orders; authenticated V3
preview and service polling passed. The final 15:08 adapter cutover likewise
reconciled zero holdings/pending orders and correctly returned market_closed.
A real prospective ladder is not yet observed.
September 29 post-interruption local observation: broker/portfolio SQLite quick
checks pass; broker records contain eight filled orders (five entries, three closes).
Last saved poll at 13:14:00 Central reports four positions. This supersedes the
first-fill-pending observation, but actual post-outage broker reconciliation and
missed management remain open. No current broker holdings were queried here.
[Outage census](reviews/2026-09-29-power-surge-recovery.md).
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
September 29 post-interruption observation: morning 93/449 checkpoint resumed
through the persistent timer at 16:11:31, reached 95/449, then was terminated
by orderly shutdown at 16:23:53. `service-exit.json` records TERM. Service inactive
at inspection; next timer midnight September 30. The remaining running receipt is
stale. Training has not started; no new candidate exists.
[Power-interruption census](reviews/2026-09-29-power-surge-recovery.md).
[Worker sizing and validation](reviews/2026-09-29-v6-worker-sizing.md),
[retained repair evidence](reviews/2026-09-28-v6-continual-error-repair.md).
Selected code: `scripts/run_v6_continual_v3.py`, `incubator/recovery_v6/`;
retry wrapper: `scripts/v6_continual_resume_v3.py --autosize-workers`. Original inheritance census:
`incubator/continual-v6/r3/inherited-r2.json`; prior installed unit/exit receipt:
`incubator/continual-v6/r3/runtime-revision/`. The unfinished date AND snapshot
stay pinned across retries. Installed allocation: up to four autosized data workers,
4500 MiB each with 8192 MiB host reserve; CPU 400%, 19/20-GiB high/max, no swap.
Training remains two threads. Current sizing returned three; startup determines
actual concurrency. Worker increase applies on the next permitted invocation;
the existing run was not restarted. The 12-hour budget and calendar cutoff remain.
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
