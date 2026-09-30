#!/usr/bin/env python3
"""Deliver the requested 15:05 status check to the explicitly selected terminal thread."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import subprocess
import time
import uuid
from websockets.sync.client import unix_connect

ROOT = Path(__file__).resolve().parents[1]
THREAD = '01a0f343-c76a-7842-915b-0c111e8e2e28'
SOCKET = '/home/healy/.codex/app-server-control/app-server-control.sock'
STATE = ROOT / 'logs/v6-handover-update-20260930'
DUE = datetime(2026, 9, 30, 20, 5, tzinfo=timezone.utc)
PREFIX = '[Requested September 30 15:05 Central handover update]'
PROMPT = PREFIX + '''
The user explicitly requested an update HERE in this terminal at 3:05 p.m.
Central today about where data migration and V7 stopped and V6 startup.
This is a read-only status check. Do not change, restart or stop any research,
trading or migration job, change permissions/models, or alter scheduled work.
Read docs/CURRENT_STATE.md's September 30 dedicated handover section and actual
receipts. The previous 15:45 V6 schedule is superseded by the 15:01 dedicated
handover. Read logs/v6-handover-update-20260930/runtime.json for dispatch-time
host service/journal evidence; use it without new host permission requests if
fresh. Combine that with nn_meta/validation/v6-focus-20260930/{progress,
paused-services,service-exit}.json when present and
incubator/continual-v6/r3/latest-run.json.
Report: (1) actual migration files/bytes moved and remaining, stopped/complete
status and storage; (2) V7 quote windows completed, original discovery's retained
cumulative wave results versus its per-pass count, replay stage and whether the
controllers stopped/checkpointed; (3) whether V6 actually started, start time,
selected workers/memory allocation and catch-up progress from 325/449 symbols.
Use v7-mrha-payload-migration-20260929-r1, v7-frontier-capture-20260930-r0,
v7-execution-recovery-20260929-r0, v7-execution-campaign-20260928-r1/waves,
and v7-required-inputs-20260930-r0 under nn_meta/validation as applicable.
Distinguish an in-progress checkpoint drain from failure. If still draining,
say so honestly; do not claim V6 started based on the timer. Explain specific
errors/blockers if any. Keep the report concise and include the observation
time. Do not claim increased CPU threads prove higher speed: current catch-up
concurrency is memory-limited and the incubation method is unchanged.
'''


class Rpc:
    def __init__(self):
        self.context = unix_connect(SOCKET, uri='ws://localhost', open_timeout=10,
                                    max_size=64 * 1024**2)
        self.connection = self.context.__enter__()
        self.number = 0
        self.call('initialize', {'clientInfo': {'name': 'v6-handover-update', 'version': '1.0'},
                                'capabilities': {'experimentalApi': True}})
        self.connection.send('{"method":"initialized","params":{}}')

    def call(self, method, params):
        self.number += 1
        number = self.number
        self.connection.send(json.dumps(dict(id=number, method=method, params=params)))
        end = time.monotonic() + 45
        while time.monotonic() < end:
            reply = json.loads(self.connection.recv(timeout=max(0, end - time.monotonic())))
            if reply.get('id') != number:
                continue
            if 'error' in reply:
                raise RuntimeError(method + ': ' + str(reply['error']))
            return reply['result']
        raise TimeoutError(method)

    def close(self):
        self.context.__exit__(None, None, None)


def save(path, document):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(document, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


def capture_runtime():
    units = ['healys-v6-focus-20260930.service', 'healys-v6-continual.service',
             'healys-v7-required-discovery-20260930.service',
             'healys-v7-required-frontier-20260930.service',
             'healys-v7-discovery-20260930.service', 'healys-v7-frontier-20260930.service',
             'healys-v7-mrha-migration-v2-20260929.service']
    document = dict(observed_at=datetime.now(timezone.utc).isoformat(), services={})
    for unit in units:
        result = subprocess.run(['systemctl', '--user', 'show', unit, '-p', 'ActiveState',
            '-p', 'SubState', '-p', 'Result', '-p', 'ExecMainStatus', '-p', 'ExecMainStartTimestamp',
            '-p', 'MemoryCurrent', '-p', 'MemoryMax', '-p', 'CPUQuotaPerSecUSec'],
            capture_output=True, text=True, timeout=10)
        document['services'][unit] = dict(returncode=result.returncode, output=result.stdout, error=result.stderr)
    result = subprocess.run(['journalctl', '--user', *[arg for unit in units for arg in ('-u', unit)],
        '--since', '-20 minutes', '-n', '80', '--no-pager'], capture_output=True, text=True, timeout=15)
    document['journal'] = dict(returncode=result.returncode, output=result.stdout, error=result.stderr)
    save(STATE / 'runtime.json', document)


def dispatch(rpc, state, check=False):
    thread = rpc.call('thread/read', {'threadId': THREAD, 'includeTurns': False})['thread']
    if thread['id'] != THREAD or thread['cwd'] != str(ROOT):
        raise ValueError('Refusing delivery to another terminal/project')
    queued = rpc.call('thread/queue/list', {'threadId': THREAD, 'limit': 100})['data']
    ours = [item for item in queued if any(part.get('text', '').startswith(PREFIX) for part in item['input'])]
    if check:
        return dict(target_verified=True, thread_id=THREAD, status=thread['status'], message_sent=False)
    if state.get('submitted'):
        return state
    if not ours and state.get('queued'):
        # A resume or the user may already have consumed/removed this submission.
        # Never recreate a duplicate merely because its queue entry is gone.
        state.update(submitted=True, outcome='previous_queue_entry_consumed_or_removed')
        save(STATE / 'state.json', state)
        return state
    capture_runtime()
    if not ours:
        key = str(uuid.uuid5(uuid.NAMESPACE_URL, THREAD + '/v6-handover/2026-09-30T20:05Z'))
        item = rpc.call('thread/queue/add', dict(threadId=THREAD, clientUserMessageId=key,
            input=[dict(type='text', text=PROMPT)]))['queuedSubmission']
        ours = [item]
        state.update(queued=True, queued_at=datetime.now(timezone.utc).isoformat(), queue_id=item['id'])
        save(STATE / 'state.json', state)
    thread = rpc.call('thread/read', {'threadId': THREAD, 'includeTurns': False})['thread']
    status = thread['status']['type']
    if status not in {'idle', 'notLoaded'}:
        return state
    if status == 'notLoaded':
        rpc.call('thread/resume', {'threadId': THREAD})
    current = rpc.call('thread/queue/list', {'threadId': THREAD, 'limit': 100})['data']
    if ours[0]['id'] in {item['id'] for item in current}:
        result = rpc.call('thread/queue/start', {'threadId': THREAD, 'queuedSubmissionId': ours[0]['id']})
        state['turn_id'] = result.get('turn', {}).get('id')
    state.update(submitted=True, submitted_at=datetime.now(timezone.utc).isoformat())
    save(STATE / 'state.json', state)
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if not args.check and datetime.now(timezone.utc) < DUE:
        raise ValueError('The requested update is not due yet')
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        path = STATE / 'state.json'
        state = json.loads(path.read_text()) if path.exists() else dict(thread_id=THREAD, due=DUE.isoformat())
        if state['thread_id'] != THREAD:
            raise ValueError('Saved update target differs')
        if state.get('submitted') and not args.check:
            return
        rpc = Rpc()
        try:
            result = dispatch(rpc, state, check=args.check)
            print(json.dumps(result))
            if not args.check and not result.get('submitted'):
                raise SystemExit(75)  # systemd retries while this terminal is busy.
        finally:
            rpc.close()


if __name__ == '__main__':
    main()
