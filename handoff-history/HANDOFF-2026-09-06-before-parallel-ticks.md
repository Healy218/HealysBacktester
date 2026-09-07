# Handoff — production ops fixes deployed; v5 refresh and v6 capture running

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

## Latest user direction — dedicate the box to freeze work

User will close other programs and dedicate the box for the next week.
Keep build/evaluation/training unlaunched while preparing/freezing. Prepare
those stage launchers when the actual freeze is about halfway complete.
Watcher now flags that checkpoint at 227/453 freeze shard files; inventory
or tick-store completion does not trigger it. The timer sends the reminder;
it cannot invoke a coding agent to implement launchers autonomously.

Retain automatic memory sizing at freeze launch: 5,000 MiB per worker plus
2,048 MiB reserve, capped by available CPUs. Approximately 22 GiB was available
at this instruction, enough for four workers under that rule. Recalculate at
launch after downloads end and the user closes apps. This is a concurrency
budget, not OS-enforced RAM reservation or CPU affinity. No new competing
heavy jobs, forced process termination, or causal-source changes were made.

## Persistent progress watcher

User requested 30-minute updates throughout preparation/freeze/build/training.
Installed/enabled user systemd healys-v6-progress.timer and matching service;
reports at :00/:30 local time, persistent across reboot (user linger=yes).
First host report delivered successfully to the existing Telegram destination
at 12:12 CDT. Local snapshots/history: logs/v6-progress/v6-local-20260906/.
Next scheduled report at installation: September 6, 12:30 CDT.

Watcher binds exact campaign/pool processes, records PID/start identity, counts
campaign artifacts and reports idle/failed/no-progress states. It remains active
across stage gaps and after completion until explicitly disabled. It does not
launch later stages or establish model admission. Current supervisor launches
freeze only; build/evaluate/finalize still need their appropriate stage launches.
Watcher code lives in scripts/ outside the current inventory source hash set;
no causal source/input changes. Three focused watcher tests passed.

First host snapshot: 260/453 inventories, 3/453 tick stores, 6,108 raw capture
batches; inventory and preparation supervisors both active. Freeze not started.

## Active jobs and evidence

Durable root: nn_meta/expanded_inputs/v6-local-20260906/
- Inventory supervisor PID 10393, four workers.
- Full-freeze supervisor PID 10394, sixteen capture workers.
- Exact commands, PIDs and log paths: resume-start-20260906T170427Z.json.
- Logs: inventory-resume-20260906T170427Z.log and
  full-freeze-supervisor-resume-20260906T170427Z.log.
- Confirmed resume reused saved captures and advanced completed raw batches
  from 1,902 to 2,057. Inventory has 212 completed symbol manifests and is
  revalidating retained results before processing remaining symbols.
- No symbol store or final input seal yet. Baseline freeze has NOT started.
  The supervisor automatically seals complete inputs and invokes the freeze
  launcher after all 453 symbol stores validate.
- Jobs are detached from the tool session and continue running. Check these
  recorded PIDs/logs before launching anything else; do not duplicate them.
- 655 GiB free at resume; capture retains the existing 20 GiB reserve guard.

Do not change causal source/config/input files while these jobs run: provenance
checks reject drift. Preserve incomplete attempts and historical roots. The
reboot checkpoints and earlier logs remain intact. The initial operational resume needed no causal code changes. Prior full regression below
applies to the unchanged source. Original untracked artifacts_v6/ is untouched.

## Implemented and validated

All 453 contexts sealed in context-r2/planning-inputs.json, SHA256:
21fe4e672af1f243e077bead7cb87b9626b24ca2e9921e3f42a2f718111b160e

Local assumptions: calendar-session pairs anchored 2024-04-01; VWAP resets
on the first actual bar of each New York trading date; fixed 0.01 research
minimum tick; no missing bars synthesized. local_research session mode keeps
literal membership transitions and records ICT gaps for MULL and SBET.
Strict modes retain their refusals. Real SPY, MULL and SBET histories produced
all 96 TV feature columns. See docs/reviews/2026-09-06-v6-local-context.json.

Fixed real integration failures: rich pandas attrs reaching legacy arithmetic;
naive UTC baseline timestamps entering aware-only TV wrappers; TRAIN-empty
symbols failing an assertion before the existing minimum-history skip.
Explicit empty tick tasks represent no planned decisions; they cannot cover
any later selected request. Full scope stays 453 symbols / 20 families /
96 TradingView plus 10 tick columns. The unverified contract is unchanged.

New CLIs: prepare_v6_local_context, run_v6_request_inventory,
run_v6_tick_capture, run_v6_full_freeze. Streaming tick materialization retains
one raw bundle at a time and matches the existing small-store materializer
exactly in tests. Capture retries transient failures, verifies resumed bytes,
retains raw evidence, and stops before using the last 20 GiB of disk.
The full supervisor captures/materializes all symbols, seals a final manifest,
then invokes the existing full freeze launcher. A queued supervisor or capture
job must never be reported as an already-started baseline freeze.

Real historical access succeeded for AA240830P00034500 on 2024-08-27
18:30–18:45 UTC: 309 quotes and one trade. Full historical coverage is still
in progress. No model training, deployment, notifications or trades occurred.

Full regression: 1,435 tests and 18 subtests passed, 11 warnings in 52.72 s.
Diff checks passed. Original untracked nn_meta/artifacts_v6/ is untouched.
The prior handoff is archived as
handoff-history/HANDOFF-2026-09-06-before-local-context-run.md.
