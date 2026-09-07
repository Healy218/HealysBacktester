# Handoff — full v6 freeze running with four workers

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
