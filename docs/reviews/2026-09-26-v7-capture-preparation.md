# V7 capture preparation and monitoring — September 26, 2026

The user requested option captures/training, a separate terminal progress bar,
and an end to the hourly completed-build alerts. The saved catalog/freeze and
kernel-equivalence recovery remain unchanged. Demand recovery finished reusing
the 546 preserved checkpoints and is now generating new demand. At the saved
follow-up: 550/591 complete, four workers, zero failures.

Actual provider captures and training have not started. Full demand and its
actual request union must precede capture sizing. Complete option paths,
integrated execution outcomes, full assembled rows/folds/trials and the resource/
readiness gates remain prerequisites for training. No completion claim was made
from the pilot, checkpoint presence, or the 7-2 catalog meter.

## Capture preparation queued

`scripts/audit_v7_capture_union.py` defaults to failing closed when full demand
is incomplete. Its explicit `--wait` mode polls the exact recovery progress and
only begins after all 591 are complete. It checks original/recovery checkpoint
identities, declaration/export identities, hashes, runtime admission and frozen
parents. Sorted read-only SQLite cursors are merged globally by contract/day.
Bounded groups go through the existing capture-union algorithm; every request's
interval membership is checked. The result retains raw/unique request counts,
contract/day counts, capture counts, total seconds per quote/trade kind and
no-contract/no-fresh selection outcomes. Full execution coverage is not claimed.

The output is a small census, with no copied request tables, provider downloads,
model execution or large generated stores. This is an input to the next measured
capture-volume forecast, not permission to spend the full acquisition ceiling.
Recorded quota: 68,973,021,525 used of 250,000,000,000 bytes. Demand retains its
140 GiB cap, 100 GiB disk reserve and 640 GB total-project budget.

Service `healys-v7-entry-union-20260926.service`, invocation
`ceded52087f74d238c957df81eb1305b`, was verified active/waiting. It has 100% CPU,
3/4 GiB memory high/max, zero swap, AF_UNIX-only sockets and 4096 file descriptors.
It waits without starting heavy work alongside the four demand workers.

```bash
./venv/bin/python scripts/audit_v7_capture_union.py \
  --demand nn_meta/validation/v7-3-scheduler-20260925 \
  --completion nn_meta/validation/v7-2-completion-20260925 \
  --kernel-proof nn_meta/validation/v7-3-kernel-equivalence-20260925 \
  --output nn_meta/validation/v7-3-entry-union-20260926 --wait
```

This command is already running as a bounded user service; do not launch a
second copy. Status: `nn_meta/validation/v7-3-entry-union-20260926.status.json`.
Log: `logs/v7-entry-union-20260926.log`. The service is transient and needs
restarting after user-manager shutdown/reboot. The existing runtime/proof
requirements still apply.

## Terminal and retired notifications

The requested Konsole tab is open with:

```bash
./venv/bin/python scripts/watch_v7_demand.py --follow
```

It reads the active recovery meter, separates saved receipts from current-run
verification/completion, and reports worker failures, storage and stale/stopped
state. Partial/foreign checkpoint directories never count. It sends no alerts
and launches no compute. Closing it leaves the demand job running.

The old `watch_v7_catalog.py --follow` observes the completed catalog. There is
no `v7_training_progress.py` in this checkout. No separate training process was
found in the targeted process check.

The stale hourly notifications came from home, not the Hetzner server. Both
`healys-v6-progress.timer` (completed V6 cash-repair campaign) and
`healys-v7-catalog-progress.timer` (1,773/1,773 catalog) were disabled with
`systemctl --user disable --now`; their oneshot services were stopped.
Both were then verified inactive/disabled. Hetzner timer/cron inspection found
no equivalent hourly build notifier. No scanner/feed/health/publisher job was
changed.

## Verification

Four focused monitor/union tests pass, covering saved-versus-revalidated counts,
partial exclusion, stale stopped progress, cross-security request deduplication,
quote/trade separation, cell-boundary coverage and corrupted request rejection.
The full suite passes **2,415 tests and 18 subtests**, with 20 warnings, in
123.33 seconds. The real incomplete-demand preflight exited 2 without launching
union/capture work; both services, disabled timers and terminal process were
checked. Checkpoint evidence: `nn_meta/validation/v7-capture-preparation-20260926`.
