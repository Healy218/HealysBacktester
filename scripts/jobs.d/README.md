# Reboot-recovery job descriptors

`scripts/boot_restart.sh` runs at every Windows logon (auto-logon is on, so
that means every reboot including BSODs) via the "HealysBacktester WF
AutoRestart" scheduled task. Register/re-register that task with
`scripts/register_boot_restart.ps1` (committed so the registration is
reproducible, not folklore). It globs every `scripts/jobs.d/*.sh` file,
sources each in an isolated subshell, and for each job: if it's already
running, do nothing; if it finished cleanly, do nothing; otherwise relaunch.

**Observability (2026-07-22):** every dispatcher run appends `dispatcher
START/END` to `logs/boot_restart.log` and, unless `BOOT_RESTART_HEARTBEAT=0`,
sends ONE Telegram summary per boot (`🔄 boot_restart @ …: N relaunched, …`).
So a missing heartbeat means the scheduled task did not fire — it no longer
looks the same as "ran and had nothing to do."

**Done semantics (2026-07-22):** a job is "done" only when its per-run exit
marker `scripts/.jobstate/<JOB_ID>.exit` contains `0`. The dispatcher empties
that marker at (re)launch and the launch script writes the real exit code on
completion, so:

- empty marker → launched but never completed (crash) → **relaunch**
- `0` → finished cleanly → **skip**
- non-zero → finished with an error → **relaunch (retry)**

This replaced `grep -q "X-EXIT:" some.log`, which matched failure markers too
AND matched a stale marker from a previous run forever (permanently blocking
the restart of any re-run).

To register a new long-running background job, add a file here setting these
variables (all plain shell — `JOB_DONE_CHECK`/`JOB_PRELAUNCH`/`JOB_LAUNCH_CMD`
are `eval`'d, so you can write real shell, not just a single command):

- `JOB_NAME` (required) — human string, goes in the Telegram notification.
- `JOB_ID` (recommended) — slug for the per-run exit marker
  (`scripts/.jobstate/<JOB_ID>.exit`); defaults to the descriptor's file name.
  Your `JOB_LAUNCH_CMD`'s target script should write its exit code to
  `${JOB_EXIT_MARKER:-scripts/.jobstate/<JOB_ID>.exit}` on completion (see
  `scripts/run_v4_finalize.sh` for the one-liner) — the dispatcher exports
  `JOB_EXIT_MARKER` before launching.
- `JOB_PROC_PATTERN` (required) — a `pgrep -f` pattern matching the job's
  running process(es). If it matches anything, the job is assumed alive.
- `JOB_DONE_CHECK` (optional, legacy) — a shell snippet that exits 0 when the
  job is already finished. Overrides the exit-marker check. Prefer the marker
  for new jobs; a log grep must match the SUCCESS marker only (e.g.
  `grep -q "WF-EXIT:0"`), never a bare prefix that also matches failures.
- `JOB_PRELAUNCH` (optional) — runs right before relaunch, e.g. to validate/
  quarantine checkpoint files. The last line of its output folds into the
  notification.
- `JOB_LAUNCH_CMD` (required) — the command that (re)starts the job. Must
  background itself (`setsid nohup ... &`); the dispatcher does not wait.

See `v31_walkforward.sh` for checkpoint validation (still on the legacy
done-check), or `v4_finalize.sh` / `v4_full_run.sh` for the marker-based form.

Test a descriptor without waiting for a real reboot:
`bash scripts/boot_restart.sh` — it's idempotent and safe to run any time. But
a manual run is NOT a substitute for a real reboot test of the logon trigger.
