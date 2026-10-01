# Handoff — September 30, 2026 — hourly watcher armed; V6 build issue found

## Selected task and automation

Complete V6 r4 through September 30, then automatically restore V7 and storage.
User is away overnight and requested a health check HERE every hour at :00 Central.
`healys-lab-hourly-watch.timer` is enabled/active; first scheduled slot is
**October 1 00:00 Central**, then hourly. Persistent=false, accuracy one second.
`healys-lab-hourly-watch.service` runs `scripts/lab_hourly_watch.py`; busy chat
retries every minute, without interrupting an active turn or accumulating reports.
Exact verified thread: `01a0f343-c76a-7842-915b-0c111e8e2e28`.
The older V7 hourly updater is bound to another conversation and was not changed.

## Watcher evidence and boundaries

`logs/lab-hourly-watch/` contains host service/journal/storage snapshots and
per-hour evidence; `state.json` records dispatch only after the first due run.
`--check` verified the exact target without sending a message. Five dispatch
checks passed (deduplication, busy chat, resume race, wrong target, cancellation).
Installed units passed systemd verification. No research process was restarted.
The watcher observes/diagnoses and reports here; it does not change frozen
sources, restart research, trade, or send external messages. Set `stopped=true`
in its state to cancel. Host evidence should avoid fresh overnight permissions.

## New specific build blocker — investigation remains

At **23:36:47 Central**, host snapshot showed V6 running, 115/449 symbols complete,
with CRSP error `ValueError: Daily parent artifact inputs differ`.
Other symbols continue; after the pass, any symbol errors prevent training and
keep competitors paused. Do not report the pipeline as healthy merely because
its service is active. Successful checkpoints remain intact.
Read `logs/lab-hourly-watch/crsp-input-mismatch.json`: a read-only reproduction
found unchanged raw/adjusted prefix hashes at September 28 19:45, but extending
through September 30 adds a second `tv_rating` proposal occurrence (ordinal 1)
at that old timestamp. Parent batch contains ordinal 0 plus `tv_setup`; current
batch adds that occurrence. The strict inherited batch declaration rejects it.
No contract bypass, artifact relabeling, producer edit or restart was performed.
Investigate a versioned repair preserving old candidate/label identities and
completed symbols; do not mutate source-bound producers during this active run.

## Selected runtime and completion boundary

`healys-v6-continual.service` runs `scripts/v6_daily_dedicated_20260930.py` via
temporary runtime `90-dedicated-r4.conf`; dedicated restart was **23:18:23 Central**.
Root `incubator/continual-v6/r4`; config `deploy/incubator-continual-v6-r4.json`.
Five autosized data workers, 16 training threads, 25/26-GiB high/max, no CPU quota.
Read `latest-run.json`/`resources.json` and run receipts for current status.
Successful full build automatically prepares arrays, trains 40 members, evaluates,
seals/verifies the candidate, removes the temporary override, restores timers and
starts V7 discovery/frontier and MRHA migration. Diagnostic rejection retains the
new freeze. No paper/live model deployment. Existing 08:00 Central cutoff remains.
A failed/incomplete run keeps checkpoints and paused jobs for investigation.
Evidence: `nn_meta/validation/v6-daily-update-20260930-r4/dedicated/`.

## Retained context and next checks

r4 preserves frozen September 28 stock prefixes, appends September 29–30 bars,
and references 231,323 prior r3 seals plus r2 ancestry. Never repeat completed
captures. Earlier r3 September 28 candidate completed at 22:40:47, 40 members,
122 verified files; training 35m29s, evaluation/freeze 5m36s.
V7 frontier's prior stop exceeded three minutes/SIGKILL: inspect health after
restoration. Discovery stopped cleanly; migration checkpointed at 268,618 files,
202,885,222,673 logical bytes. Keep MRHA mounted. Preserve unrelated dirty work.
CLI: `./venv/bin/python scripts/watch_v6_incubator.py --follow`.
[State](docs/CURRENT_STATE.md) · [Daily update](docs/reviews/2026-09-30-v6-two-day-update.md).
