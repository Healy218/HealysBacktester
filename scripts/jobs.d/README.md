# Reboot-recovery job descriptors

`scripts/boot_restart.sh` is meant to run at every Windows logon (auto-logon
is on, so that means every reboot including BSODs) via the hand-registered
"HealysBacktester WF AutoRestart" scheduled task. CAVEAT (2026-07-22): the
logon-trigger path has never passed a logged real-reboot test — the task was
only ever test-fired manually — and the dispatcher currently writes no log
of its own runs, so a silent boot proves nothing either way. See
"Reboot-recovery job system" in `V4_OUTLINE.md` for the diagnosis and the
hardening queue. It globs every `scripts/jobs.d/*.sh`
file, sources each one in an isolated subshell, and for each job: if it's
already running, do nothing; if it already finished cleanly, do nothing;
otherwise relaunch it and send one Telegram notification.

To register a new long-running background job, add a file here setting these
variables (all are plain shell — `JOB_DONE_CHECK`/`JOB_PRELAUNCH`/
`JOB_LAUNCH_CMD` are `eval`'d, so you can write real shell, not just a single
command):

- `JOB_NAME` (required) — human string, goes in the Telegram notification.
- `JOB_PROC_PATTERN` (required) — a `pgrep -f` pattern matching the job's
  running process(es). If this matches anything, the dispatcher assumes the
  job is already alive and does nothing.
- `JOB_DONE_CHECK` (optional) — a shell snippet that exits 0 when the job has
  already finished (e.g. `grep -q "MY-JOB-EXIT:" my_job.log`). Without this,
  a finished job with no process running would get relaunched forever.
- `JOB_PRELAUNCH` (optional) — runs right before relaunch, e.g. to validate/
  quarantine checkpoint files so a half-written state file can't wedge a
  retry loop. The last line of its output is folded into the notification.
- `JOB_LAUNCH_CMD` (required) — the command that (re)starts the job. Must
  background itself (`setsid nohup ... &`), since the dispatcher does not
  wait for it.

See `v31_walkforward.sh` for an example with checkpoint validation, or
`v4_full_run.sh` for the simplest possible case (no checkpointing — v4's
ablation/walk-forward run has none yet, so a restart means starting over
from scratch, not resuming; that's a real gap worth closing in
`nn_meta/v4_evaluate.py` itself at some point, not something this dispatcher
can paper over).

Test a descriptor without waiting for a real reboot:
`bash scripts/boot_restart.sh` — it's idempotent and safe to run any time.
