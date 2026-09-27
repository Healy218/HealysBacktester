# Current state and artifact index

Pointer/configuration owner for the lab, reconciled September 27, 2026.
[ROADMAP](../ROADMAP.md) owns milestone status and acceptance conditions;
[TODO](../TODO.md) owns selected work. This page selects exact inputs and
runtime identities. Other current documents link here instead of copying them.

**Evidence freshness:** the observations below come from the September 27
capture/operations checks and retained receipts. Documentation consolidation
performed no new service probe, capture, deployment or artifact mutation.
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
| Incubator | Home, research checkout | `incubator/runs/after-close/`, `incubator/artifacts/daily/`; routing below |

## V7 acquisition runtime

- Service: `healys-v7-capture-v7-20260927.service` (home box).
- Live meter: `nn_meta/validation/v7-entry-campaign-v7-20260927/progress.json`.
- Immutable launch: `nn_meta/validation/v7-entry-campaign-v7-20260927/declaration/`.
- New packs: `nn_meta/data_v7/entry-campaign-20260927/<security>/<batch-hash>/`.
- Attempt journal: `nn_meta/validation/v7-entry-campaign-v7-20260927/attempts/`.
- Shared acquisition accounting: `nn_meta/data_v7/quota.json`.
- Launcher: `bash scripts/start_v7_capture_campaign_v7.sh 12 32`; do not start a duplicate
  while the service is active. Existing batches are verified/reused on resume.
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
Keep MRHA connected. Existing external files and completed local packs are intact.

### One-time ETA check — September 27, 2026

User-requested timer `healys-v7-eta-20260927-1830.timer` is scheduled for
**2026-09-27 18:30 America/Chicago** (23:30 UTC), accuracy 1 second.
It runs `nn_meta/validation/v7-eta-check-20260927/observe.py`, reads the live
meter selected above at execution time, and writes `check-1830.json` and
`check-1830.md` in that same directory. It reads only; it does not restart or
change acquisition. This is a local report, not an automatic chat message.
Timer activation/next-elapse were verified when scheduled; inspect its result
and report after 18:30 rather than assuming it ran. `baseline-now.*` contains
the immediate dry-run observation. Stopped/stale receipts produce no ETA.

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
| Five exact reference blackouts | `v7-contract-blackouts-20260927/`; entry impact `v7-contract-blackout-impact-20260927/` |
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

The dated-reference **plan** is finished; most full-scope reference **downloads**
remain. The hours reconstruction is finished for the reviewed scope. The five
blackouts are implemented; do not re-investigate or broaden them. The entry
request plan/packing/cleanup are complete; the live service is executing that
plan. Replay machinery exists; actual remaining paths/captures and full dataset
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
`nn_meta/validation/v7-integrated-execution-20260927-r2/`; quote snapshot:
`v7-integrated-quote-index-20260927-r2`; retained source paths:
`v7-execution-discovery-20260927-r13` (validation roots). Use these newer receipts
for integration; r12 remains valid original evidence. The shared ledger completed
DIS/ABBV, retains NVDA at its next exact missing mark, and has not reached real
exercise/stock liquidation. Full V7-4 is still open. See the
[integration review](reviews/2026-09-27-v7-integrated-execution.md) and the current
three-argument `scripts/run_v7_integrated_execution.sh` launcher.

The retained r2 ledger has 1,466 earlier events, three decisions and 164 marks
plus one subsequently added mark; cash was $87,596.26474814238 at that receipt.
Next NVDA240322C00910000 quote window:
`[1711038150000000000,1711038180000000001)`.
VKTX/FUTU source gaps remain. This is a dated continuation pointer, not a new
request to capture during documentation work.

## V6 Alpaca paper and incubator

Configuration and startup were verified at the September 27 activation:
[deployment/runbook](reviews/2026-09-27-v6-alpaca-activation.md) and
[receipt](reviews/2026-09-27-v6-alpaca-activation.json).
The fresh state's `paper-restart.json` enables scanning and paper submission;
`broker-status.json`, `scanner-dispatch-status.json`, `latest-preview.json`,
`portfolio.sqlite3` and `broker-orders.sqlite3` own actual subsequent state.
Read SQLite evidence in read-only mode.

- Scanner: `healys-v6-alpaca-scanner.timer` / `.service`, every 15 minutes in
  its configured window, dynamically sized workers, 10 GiB memory limit.
- Broker: `healys-v6-alpaca-orders.timer` / `.service`, every 15 seconds in its
  configured window; market/calendar checks govern execution.
- Read-only monitor: `healys-v6-alpaca-paper-monitor.timer`; output
  `/tmp/v6-alpaca-paper-monitor-latest.json` (ephemeral observation).
- Daily producer retained: `healys-v6-data.timer`; scanner reads the latest
  immutable index from the old state's `data-index.json`. This shares inputs,
  not historical positions.
- Old home forward/risk/relay/projected-ledger/session-update schedules and the
  old server V6 watcher were retired. The old Stonks simulator projection is
  historical; it is not the new account's actual fill history.

Startup was successful with no positions or orders. The first actual
prospective fill remained unverified at the activation checkpoint. Monday's
configured schedule and exact account snapshot are in the deployment receipt;
do not copy that snapshot as a present account balance.

Incubator timer: `healys-ai-incubator-after-close.timer`, 15:30 Chicago on
scheduled weekdays. Its V6 inputs now point to the fresh paper state's
`passes/` and `data-index.json`; V5 capture remains separate.
Friday evidence is `incubator/runs/after-close/close-20260925/` and
`incubator/artifacts/daily/v5-20260925/`, `v6-20260925/`.
Both model refreshes passed, but V6 had only three late source passes and
both receipts awaited outcomes. [Audit](reviews/2026-09-27-incubator-fa-alpaca-readiness.md).
That audit's earlier disabled-Alpaca finding is superseded by the activation
receipt; its Friday inference observations remain valid.

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
