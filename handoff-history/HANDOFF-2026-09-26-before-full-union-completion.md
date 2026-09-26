# Handoff — 2026-09-26 — demand running; union audit queued; stale alerts stopped

Read TODO first. Previous handoff:
`handoff-history/HANDOFF-2026-09-26-before-capture-preparation.md`.
Main is operational. Preserve the extensive unrelated dirty/untracked work.

## User direction and current gate

The user requested starting option captures and training, a separate-terminal
progress bar, and stopping hourly finished-build alerts. Advance the required
capture/training dependencies without relabeling incomplete stages as ready.
V7-1 and V7-2 are complete; V7-3 is active. Actual provider captures and training
have not launched: demand, full union, storage forecast and later execution,
assembly/fold/trial/resource/readiness gates remain prerequisites.

All 1,773 frozen stores, completion gates, daily context and original historical
loader proofs remain preserved. The user-approved exact Linux 7.2.6 → 7.2.7
exception is backed by four byte-identical demand/export replays. All 546
pre-reboot demand checkpoints survived and have now been revalidated/reused.
The run is generating the remaining securities. At the saved follow-up,
550/591 were complete, with four workers and no failures; use current progress.
Do not edit either demand scheduler, recovery source or bound inputs while active.

## Running demand and queued union audit

Demand service: `healys-v7-entry-demand-recovery-20260925.service`.
Invocation: `9a07064bbccd4f91aedd75e46580fd3a`.
Root: `nn_meta/validation/v7-3-scheduler-20260925`.
Active meter/log: `kernel-recovery/progress.json` and `kernel-recovery/controller.log`.
Root `progress.json` remains the failed strict-runtime restart, not current state.
Four workers / one inner thread, 400% CPU, 14/16 GiB memory high/max, no swap.

Union service: `healys-v7-entry-union-20260926.service`.
Invocation: `ceded52087f74d238c957df81eb1305b`.
It is waiting for all 591 demand checkpoints before starting a read-only audit.
Script: `scripts/audit_v7_capture_union.py`.
Status: `nn_meta/validation/v7-3-entry-union-20260926.status.json`.
Output when complete: `nn_meta/validation/v7-3-entry-union-20260926`.
Log: `logs/v7-entry-union-20260926.log`.
One CPU, 3/4 GiB memory high/max, no swap, AF_UNIX only, file-descriptor limit 4096.
It verifies checkpoint/declaration/export identities and hashes, streams sorted
request tables through a global union, checks every request's interval coverage,
and preserves no-contract/no-fresh outcomes in its summary. It writes a small
census rather than duplicating request tables. No provider requests or training
are chained to this service. Do not change its source while queued/running.
Both services are transient; user-manager shutdown/reboot requires recovery.

## Progress terminal and retired alerts

A Konsole tab was opened with the read-only demand viewer:
`./venv/bin/python scripts/watch_v7_demand.py --follow`.
It separately shows saved checkpoint presence and verified/completed work in the
current invocation, active workers, failures, storage and stale/stopped state.
Ctrl-C closes the viewer without stopping the background job. The old
`scripts/watch_v7_catalog.py --follow` tracks the completed catalog, not demand.
No `v7_training_progress.py` exists in this checkout; no separate training job
was found in the process inspection.

The repeated completed-build notifications were on the HOME box. Both
`healys-v6-progress.timer` and `healys-v7-catalog-progress.timer` are persistently
disabled and inactive; their oneshot services were stopped. Hetzner timers/cron
were inspected and no equivalent hourly build notifier was found there.
Live scanners, feed health, dashboard, V6 paper and incubator services remain.

## Budget, evidence and next steps

Demand cap: 140 GiB; prior stress forecast 128.81 GB. Keep 100 GiB free and the
640 GB project budget. Acquisition quota remains 250 GB; recorded used quota
was 68.97 GB. Counts alone do not forecast provider bytes. Once the union audit
finishes, inspect its coverage/counts and produce a measured capture storage
forecast; then capture required windows under the remaining budget. Dated
option hours/references and entry/mark/exit/roll/delivery paths remain V7-3 work.
Training remains gated through integrated execution, assembly and full readiness.

Review: `docs/reviews/2026-09-26-v7-capture-preparation.md`.
Evidence: `nn_meta/validation/v7-capture-preparation-20260926`.
Prior preservation/kernel recovery:
`docs/reviews/2026-09-25-v7-3-crash-recovery.md`.
Full tests: **2,415 passed, 18 subtests, 20 warnings**, 123.33 seconds.
Four focused monitor/union tests passed; incomplete-demand preflight correctly
exited without starting a union or capture. Service/timer/terminal states checked.

V6 Alpaca fresh scanning/submission, incubator daily health/outcomes and October 2
Massive renewal recommendation remain separate carried-forward work.
