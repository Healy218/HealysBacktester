#!/usr/bin/env python3
"""Deliver top-of-hour lab health checks to the user's explicitly bound terminal."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.v6_handover_update_20260930 import Rpc, save

THREAD = '01a0f343-c76a-7842-915b-0c111e8e2e28'
STATE = ROOT / 'logs/lab-hourly-watch'
PREFIX = '[Requested hourly V6, V7 and storage health check]'
PROMPT = PREFIX + '''
The user requested a watcher every hour at :00 America/Chicago in THIS terminal
while away overnight. Read TODO.md, HANDOFF.md and the relevant CURRENT_STATE
sections, then inspect current receipts. Report HERE concisely with observation
time, progress since the preceding check, and specific errors or stalls.

The selected V6 update is r5, through September 30 (adding September 29-30).
This supersedes failed r4: its 447 completed symbols are preserved; CRSP/MTUM
were repaired by appending new occurrences without changing old seals.
Read incubator/continual-v6/r5/{latest-run,resources,service-exit}.json where
present, runs/2026-09-30/status.json, per-symbol progress, training-plan.json,
member receipts and candidate/{evaluation,complete}.json when present. The
dedicated controller evidence is nn_meta/validation/v6-daily-repair-20261001-r5/{progress,incubator-result,restored-services}.json. Verify the sequence
build -> prepare arrays -> 40-member training -> evaluation -> final sealed
candidate -> restoration of paused V7/storage services and timers. An adverse
diagnostic verdict does not discard the new freeze or block restoration after
valid completion. No automatic paper/live model deployment is authorized.

While V6 is building/training, the paused V7/migration services are EXPECTED.
After its verified freeze, check both healys-v7-required-discovery-20260930 and
healys-v7-required-frontier-20260930 plus healys-v7-mrha-migration-v2-20260929.
Use nn_meta/validation/v7-required-inputs-20260930-r0/{discovery,frontier},
v7-mrha-payload-migration-20260929-r1, v7-execution-campaign-20260928-r1/waves,
v7-frontier-capture-20260930-r0 and v7-execution-recovery-20260929-r0 as relevant.
Distinguish retained cumulative results from per-pass counts. Report migration
files/bytes moved/remaining and actual storage. A completed job need not run.
The frontier previously hit a stop timeout; check resumed health rather than
mistaking its historical SIGKILL for a new failure. Preserve checkpoints.

Read the supplied dispatch-time runtime snapshot for host service/journal and
storage observations; use it without new host permissions if sufficiently fresh.
It and earlier hourly snapshots live in logs/lab-hourly-watch. Stale receipts
alone do not prove health; check worker/member activity before calling a stall.
Do not infer memory exhaustion from low CPU: build has five mostly single-thread
workers, training 16 threads, service max 26 GiB; concurrency sizing is conservative.

This watcher observes and diagnoses; it does not stop/restart jobs, change frozen
sources, alter permissions/models, or submit trading orders. Automatic pipeline
and restoration remain owned by the existing dedicated controller. If blocked,
record the exact cause and report it here; do not claim a fix or completion.
Do not send Slack/email/Telegram. If the user cancels this watcher, set
stopped=true in logs/lab-hourly-watch/state.json. Otherwise keep hourly checks.
'''

UNITS = [
    'healys-v6-continual.service', 'healys-v6-continual.timer',
    'healys-v7-required-discovery-20260930.service',
    'healys-v7-required-frontier-20260930.service',
    'healys-v7-mrha-migration-v2-20260929.service',
    'healys-cache-backup.timer', 'healys-cache-backup.service',
    'healys-archive-pull.timer', 'healys-archive-pull.service',
]


def command(args, timeout=15):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return dict(returncode=result.returncode, output=result.stdout, error=result.stderr)
    except subprocess.TimeoutExpired:
        return dict(returncode=None, error='Observation command timed out')


def capture_runtime(slot):
    result = dict(observed_at=datetime.now(timezone.utc).isoformat(), services={})
    properties = ['ActiveState', 'SubState', 'Result', 'ExecMainStatus',
                  'ExecMainStartTimestamp', 'MemoryCurrent', 'MemoryPeak',
                  'MemoryMax', 'CPUUsageNSec', 'CPUQuotaPerSecUSec',
                  'NextElapseUSecRealtime', 'ControlGroup']
    for unit in UNITS:
        result['services'][unit] = command(['systemctl', '--user', 'show', unit,
                                            *[a for p in properties for a in ('-p', p)]])
    result['journal'] = command(['journalctl', '--user',
        *[a for u in UNITS if u.endswith('.service') for a in ('-u', u)],
        '--since', '-70 minutes', '-n', '100', '--no-pager'])
    result['storage'] = command(['df', '-B1', '--output=source,target,size,used,avail'])
    result['memory'] = Path('/proc/meminfo').read_text()
    receipts = [
        'incubator/continual-v6/r5/latest-run.json',
        'incubator/continual-v6/r5/resources.json',
        'nn_meta/validation/v6-daily-repair-20261001-r5/progress.json',
        'nn_meta/validation/v7-required-inputs-20260930-r0/discovery/progress.json',
        'nn_meta/validation/v7-required-inputs-20260930-r0/frontier/progress.json',
        'nn_meta/validation/v7-mrha-payload-migration-20260929-r1/progress.json',
    ]
    result['receipts'] = {}
    for name in receipts:
        try:
            result['receipts'][name] = json.loads((ROOT / name).read_text())
        except (OSError, ValueError) as exc:
            result['receipts'][name] = dict(observation_error=str(exc))
    target = STATE / f'runtime-{slot}.json'
    save(target, result)
    save(STATE / 'runtime.json', result)
    return target


def dispatch(rpc, state, now, check=False):
    thread = rpc.call('thread/read', {'threadId': THREAD, 'includeTurns': False})['thread']
    if thread['id'] != THREAD or thread['cwd'] != str(ROOT):
        raise ValueError('Refusing delivery to a different thread/project')
    queue = rpc.call('thread/queue/list', {'threadId': THREAD, 'limit': 100})['data']
    ours = [q for q in queue if any(p.get('text', '').startswith(PREFIX) for p in q['input'])]
    if check:
        return dict(target_verified=True, thread_id=THREAD, status=thread['status'],
                    pending_updates=len(ours), message_sent=False)
    slot = int(now) // 3600 * 3600
    # Recover an existing queued check after a crash without accumulating a backlog.
    if not ours and state.get('last_slot', -1) < slot:
        snapshot = capture_runtime(slot)
        due = datetime.fromtimestamp(slot, timezone.utc).isoformat()
        item = rpc.call('thread/queue/add', dict(threadId=THREAD,
            clientUserMessageId=str(uuid.uuid5(uuid.NAMESPACE_URL, THREAD + '/lab-hourly/' + due)),
            input=[dict(type='text', text=PROMPT + '\nScheduled slot UTC: ' + due +
                        '\nRuntime snapshot: ' + str(snapshot))]))['queuedSubmission']
        ours = [item]
        state.update(last_slot=slot, queued_at=datetime.now(timezone.utc).isoformat(),
                     queue_id=item['id'], submitted_count=state.get('submitted_count', 0) + 1)
        save(STATE / 'state.json', state)
    if not ours:
        state['pending'] = False
        save(STATE / 'state.json', state)
        return dict(pending=False, message_sent=False)
    # An older pending observation serves this slot too; do not flood a busy chat.
    state['last_slot'] = max(slot, state.get('last_slot', slot))
    status = rpc.call('thread/read', {'threadId': THREAD, 'includeTurns': False})['thread']['status']['type']
    if status == 'notLoaded':
        rpc.call('thread/resume', {'threadId': THREAD})
        status = rpc.call('thread/read', {'threadId': THREAD, 'includeTurns': False})['thread']['status']['type']
    state['pending'] = True
    if status == 'idle':
        current = rpc.call('thread/queue/list', {'threadId': THREAD, 'limit': 100})['data']
        if ours[0]['id'] in {q['id'] for q in current}:
            # Refresh host evidence if delivery waited behind an active user turn.
            capture_runtime(slot)
            reply = rpc.call('thread/queue/start', {'threadId': THREAD, 'queuedSubmissionId': ours[0]['id']})
            state.update(started_at=datetime.now(timezone.utc).isoformat(),
                         turn_id=reply.get('turn', {}).get('id'))
        state['pending'] = False
    save(STATE / 'state.json', state)
    return dict(thread_id=THREAD, pending=state['pending'], last_slot=state['last_slot'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Verify target; send nothing')
    parser.add_argument('--snapshot', action='store_true', help='Capture host evidence; send nothing')
    args = parser.parse_args()
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        path = STATE / 'state.json'
        state = json.loads(path.read_text()) if path.exists() else dict(thread_id=THREAD, cwd=str(ROOT))
        if state['thread_id'] != THREAD or state['cwd'] != str(ROOT):
            raise ValueError('Watcher target differs')
        if args.snapshot:
            print(capture_runtime('preflight'))
            return
        if state.get('stopped') and not args.check:
            return
        rpc = Rpc()
        try:
            result = dispatch(rpc, state, time.time(), check=args.check)
            print(json.dumps(result))
            if result.get('pending'):
                raise SystemExit(75)
        finally:
            rpc.close()


if __name__ == '__main__':
    main()
