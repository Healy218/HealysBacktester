# Handoff — trial preflight actively verifying inputs

Latest verification September 7: controller 2541751 is RUNNING, phase preflight
since 13:18:26 UTC. Original four workers have drained; 33 completed shards retained
on disk. Zero freeze workers during full pinned input verification is expected.
Three-second live sample: read_chars +88.6 MB, physical read_bytes +79.9 MB, CPU
jiffies +230; 2.38 GiB RSS. This is active verification, not a stopped controller.
Five-worker queue and two-hour trial clock have NOT started at this check.
Watcher corrected to explicitly show 0/5, previous four-worker average 12.0/hour,
ETA recalculates after restart, and trial clock not started during preflight.
Eight watcher tests pass. Do not edit the pinned trial controller or causal inputs.

User authorized a two-hour fifth freeze worker trial; return to four if throughput
does not improve. New controller PID 2541751 started 2026-09-07 13:03:40 UTC.
At last check it is DRAINING the old launcher 2086441/start 5911018 with SIGINT:
original ThreadPool cancels queued jobs and waits for its four active symbols.
Do not kill those workers or launch another supervisor. Five is the queued target,
not yet a verified live count. The controller waits for the old launcher to exit,
then executes original coverage, scope fingerprint and campaign-lock gates before
starting only remaining symbols. Completed shards are validated and hash-preserved.

Controller: scripts/run_v6_freeze_trial.py; immutable running snapshot at campaign
preparation full-run/worker-trial/source.txt. Original research_local.py and all
causal source/input files remain unchanged. Controller replaces only the imported
parallel_commands scheduling function; original final shard validation/merge and
before/after fingerprint checks still execute. Inherits original environment and
CPU affinity (excludes two physical cores). No build/training launch.

Baseline: 12.0242 symbols/hour, 24 completions in 1.996 hours, 11:01:47–13:01:32 UTC.
The two-hour clock begins when the pending-symbol queue starts, excluding drain
and preflight time. At review retain five only if measured completions/hour exceeds
that baseline; otherwise lower target to four, letting active searches finish.
Memory guard also permanently lowers target to four if MemAvailable drops below
4 GiB or full memory PSI avg60 exceeds 5% for 120 seconds. No new starts while below
4 GiB. Reduction drains an occupied fifth slot; this is not a hard memory limit.
Comparisons are observational: symbol workloads differ and ETA remains approximate.

Durable root: nn_meta/expanded_inputs/v6-local-20260906/full-run/worker-trial/
- status.json: draining/preflight/running/merging/complete/failed phase, active PIDs,
  target count, baseline, measured throughput, memory headroom and review decision.
- review.json: timed two-hour comparison once reached.
- baseline.json, environment.json (research settings only), retained-shards.json,
  result.json on final exit. source.txt binds controller implementation.
Log: preparation campaign freeze-worker-trial-resume-20260907.log.
Launch receipt: preparation campaign freeze-worker-trial-launch.json.
Do not use the older capture resume.json to restart this running trial.

Watcher recognizes the controller, reads target workers and review time, and
suppresses the intentionally drained original launcher's exit while trial is live.
Original freeze-launcher-result.json is historical after this handoff; use
worker-trial/result.json for final trial-driven freeze outcome. 30-minute Telegram
timer remains active. Full regression 1450 tests +18 subtests passed; focused trial
coverage verifies five simultaneous slots, retained shards and memory admission.

Watcher now inserts average/hour and approximate UTC finish with trailing ⏲️ immediately below
the live stage. Uses counter deltas over contiguous same-stage observations,
up to six hours; resets at stage gaps/counter decreases. Requires five minutes
of observations; zero throughput shows waiting. Training ETA awaits an explicit
job total, never assumes 453 symbols equals training jobs. Seven watcher tests
pass, including arithmetic, placement, zero progress and stage/reset handling.

Progress header now reads 🧪🔬HealyLabs v6 progress - date/time UTC💻📲,
without the extra campaign line. Built symbols ends with 🛠️; separate Trained: N🎮,
Model files: N 🗂️, and Free disk lines.

Progress message formatting updated per user: completed inventory/tick stores
show ✅, freeze count ends with 🧊, raw batch lines and artifact presence text
removed. Existing five watcher tests pass; timer uses this format automatically.

September 7, 2026. User requested starting freeze after tick completion.
Supervisor already automatically launched it after all 453 stores verified.
No restart or duplicate job was launched.

Campaign: `v6-local-20260906`, pool v6, repaired candidate
`audit-repair-20260905-final`. Existing expanded/deferred-parity contract remains.
Preparation root: `nn_meta/expanded_inputs/v6-local-20260906/full-run/`.
`parallel/result.json` records 453 verified symbols; final-inputs.json is sealed.
All 1,032,103 planned raw capture batches are present. Tick capture is complete.

Freeze launch budget sampled 25.54 GiB available: four workers × 5 GiB plus 4 GiB
system headroom. CPUs 3,4,11,12 (two physical cores and their SMT siblings) are
excluded from heavy-worker affinity. This is launch sizing, not a hard RAM cap.
Live host verification found four freeze workers: ADBE 2306790, AFRM 2344560,
AGQ 2354903, AI 2374680; aggregate RSS about 12.9 GiB, MemAvailable about 11.8 GiB.
These worker PIDs rotate per symbol. Stage launcher 2086441, parent 1432456.
14/453 freeze shard files were complete at verification; remaining work active.

Freeze outputs: `nn_meta/campaigns/v6-local-20260906/v6/artifacts/freeze_shards/`.
Per-symbol logs: same campaign `v6/runs/logs/freeze/`.
Parent log: preparation campaign `parallel-freeze-supervisor-resume-20260907T041639Z.log`.
Do not change causal source/input files or running parallel scheduler source.
Do not rerun capture resume while current supervisor/launcher is active.

Watcher corrected: report live freeze processes and freeze launch budget rather
than the final stale tick status (452 verified/one active). Completion evidence
comes from parallel/result.json; active counts come from host process discovery.
Five focused watcher tests passed. Persistent 30-minute timer remains in use.
Build/training remain unlaunched. Prepare those launchers at 227/453 actual freeze
shards per user direction; timer reminder cannot itself invoke a coding agent.

## Production operations (separate host; last verified state retained)

September 6, 2026. User requested operational fixes and both experimental
partial-bar view + closed-bar recap five minutes before the exchange close.
Production compatibility branch ops/server-alert-readiness-20260906 is now at
a315034 (initial patch 6d83a67), separately from research main. Do not pull
research main onto old models. Home v6 causal source/data are unchanged.

Deployment and remaining checks:
docs/reviews/2026-09-06-production-ops-deployment.md.
Full ops regression 545 tests +18 subtests; follow-up 10 focused tests passed.
Freshness/final-close/calendar/stream/retry fixes and separate EOD minute cron
are active. Models/specs/thresholds retained; bundle and alert-state hash checks
passed. Actual stream/timing/delivery acceptance awaits the next session.
Calendar verified September 7 closed, first panel September 8 at 15:55 ET.
Preview prewarms at 15:46, snapshot target 15:54; incomplete coverage is labeled.

Server v5 refresh remains RUNNING, not complete: supervisor 394442, initial
worker 394443, eight download workers, sampled 1 GiB available-memory stop guard.
Exact root logs/ops/v5-refresh-20260906T222750Z/ on server. At last check,
5,000/208,684 remaining downloads done, ~76/s, 5.6 GiB available. Surface follows
successful download/compaction automatically. Check result.json and date coverage.
Server stock stream restarted as PID 394370. Rollback snapshot:
logs/ops/alert-fix-20260906T222537Z/ on server. No test trading alert was sent.


See archived handoff for older campaign chronology and source contract details.
