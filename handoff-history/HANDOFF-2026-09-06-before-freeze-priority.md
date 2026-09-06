# Handoff — v6 pipeline resumed after reboot

September 6, 2026, resumed at 17:04:27 UTC. Main checkout, source commit
522d9c7. User returned and requested continuing to the v6 freeze. Resumed
both exact commands from the saved resume.json with approved host network
access. Local research assumptions, all TV13/tick scope and deferred external
comparison remain unchanged.

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
