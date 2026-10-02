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
LEGACY_PREFIX = '[Requested hourly V6, V7 and storage health check]'
PREFIX = '[Requested hourly V6 paper and V7-3 progress]'
PROMPT = PREFIX + '''
The user requested updates every hour at :00 America/Chicago in THIS terminal.
Read TODO.md, HANDOFF.md and the relevant CURRENT_STATE sections, then inspect
current receipts. Report concisely with observation time, changes since the
preceding check, and specific failures or resource waits.

REPORTING SCOPE (user revised October 2):
1. V6 Alpaca PAPER: scanner completion, duration/deadline, held-quote monitoring,
   broker/account observations and actual orders/fills when supported by receipts.
   Report scanner failures even when broker polling succeeds. Read the snapshot's
   paper_receipts, scanner_journal and paper_journal, plus the current receipts at
   /home/healy/Coding/HealysV6/nn_meta/live/v6_alpaca_paper/ and the read-only
   /tmp/v6-alpaca-paper-monitor-latest.json. Separate pending retries from terminal
   failures; enabled timers alone do not prove successful scans.
2. V7 gate 7-3: lead with cumulative work, using snapshot v7_work and its deltas.
   Show retained discovery cohorts and horizon-target assessments (plain language:
   decision groups processed and execution scenarios assessed), plus their change
   since the previous observation. Then show finished securities including
   verified empty-demand cases, partially processed securities and workers.
   These scenario counts INCLUDE pending-input outcomes; they are NOT completed
   labels or proof of gate closure. Do not present a full-discovery percentage
   without a verified matching denominator. Per-process pass counters reset and
   must NEVER be the headline progress figure. Report current capture/replay stage
   separately. Each replay re-evaluates a subset; NEVER add original discovery
   and replay-round counts together as unique completed work. For a replay with
   a frozen denominator, report assessed horizon-targets / required targets.
3. V6 INCUBATOR: show only while actually building/preparing/training/evaluating/
   freezing, or if failed/blocked/incomplete and needing attention. Use snapshot
   incubator_visibility and current r5/latest-run.json's selected run directory,
   its status, training-plan, member receipts and candidate evaluation/complete.
   Once successfully frozen, omit routine completion updates entirely. An adverse
   diagnostic verdict alone does not discard the freeze or constitute pipeline
   failure. Do not repeat successful overnight completion every hour.
4. Omit the completed storage migration and routine storage/free-space summaries.
   Mention storage only for a NEW error or space constraint affecting active work.

Selected V7 controllers: healys-v7-required-discovery-20260930 and
healys-v7-required-frontier-20260930. State under nn_meta/validation/:
v7-required-inputs-20260930-r0/{discovery,frontier,epochs},
v7-execution-recovery-20260929-r0 and
v7-execution-campaign-20260928-r1/waves. Preserve completed captures and all
checkpoints. The original discovery resource scheduler now has dynamic admission:
up to four overnight, two weekdays 07:00-21:00 Central; zero new admissions is a
memory-reserve wait, not lost work. Existing slices may still be active. Read
actual resource receipts; do not reuse historical dedicated V6 worker counts.

Use the supplied runtime snapshot if fresh; runtime.json may contain a newer
observation if this request waited behind a user turn. Hourly snapshots live in
logs/lab-hourly-watch. Check worker/member activity before calling a stall. Label
observation times and delta baselines honestly; no invented percentage or ETA.

This watcher observes and diagnoses. Do not stop/restart jobs, alter frozen
sources, permissions/models, or submit trading orders. No automatic paper/live
model deployment is authorized. If blocked, record the exact cause and report it;
do not claim a fix or completion. Do not send Slack/email/Telegram. If cancelled,
set stopped=true in logs/lab-hourly-watch/state.json; otherwise keep hourly checks.
'''

UNITS = [
    'healys-v6-continual.service', 'healys-v6-continual.timer',
    'healys-v7-required-discovery-20260930.service',
    'healys-v7-required-frontier-20260930.service',
    'healys-v6-alpaca-scanner.service', 'healys-v6-alpaca-scanner.timer',
    'healys-v6-alpaca-orders.service', 'healys-v6-alpaca-orders.timer',
    'healys-v6-alpaca-paper-monitor.timer',
]
PAPER = ROOT.parent / 'HealysV6/nn_meta/live/v6_alpaca_paper'


def read_receipt(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        return dict(observation_error=str(exc))


def wave_work(root, terminal):
    """One top-level receipt per security; never sum duplicate nested receipts."""
    result = dict(status_counts={}, securities_with_receipts=0,
                  completed_security_ids=[], cohorts_processed=0,
                  horizon_targets_assessed=0, horizon_target_outcomes={},
                  observation_errors=[])
    if not root.exists():
        result['observation_errors'].append(dict(path=str(root), error='Wave root missing'))
    for path in sorted(root.glob('*/progress.json')):
        doc = read_receipt(path)
        if 'observation_error' in doc:
            result['observation_errors'].append(dict(path=str(path), error=doc['observation_error']))
            continue
        result['securities_with_receipts'] += 1
        status = doc.get('status', 'unknown')
        result['status_counts'][status] = result['status_counts'].get(status, 0) + 1
        if status == terminal:
            result['completed_security_ids'].append(path.parent.name)
        result['cohorts_processed'] += doc.get('cohorts_discovered', 0)
        result['horizon_targets_assessed'] += doc.get('distinct_horizon_targets_covered', 0)
        for outcome, count in doc.get('horizon_target_statuses', {}).items():
            result['horizon_target_outcomes'][outcome] = result['horizon_target_outcomes'].get(outcome, 0) + count
    result['completed_securities'] = len(result['completed_security_ids'])
    result['partial_securities'] = result['securities_with_receipts'] - result['completed_securities']
    return result


def work_delta(current, previous):
    if not previous or current.get('observation_errors') or previous.get('observation_errors'):
        return None
    # A negative delta stays visible for investigation, never silently clamped.
    return {key: current[key] - previous[key] for key in
            ['cohorts_processed', 'horizon_targets_assessed', 'completed_securities']}


def v7_work(previous):
    validation = ROOT / 'nn_meta/validation'
    required = validation / 'v7-required-inputs-20260930-r0'
    recovery = validation / 'v7-execution-recovery-20260929-r0'
    original = wave_work(validation / 'v7-execution-campaign-20260928-r1/waves', 'discovered')
    declaration = read_receipt(validation / 'v7-execution-campaign-20260928-r1/declaration.json')
    original['securities_required'] = len(declaration['securities']) if 'securities' in declaration else None
    empty = set()
    for path in (recovery / 'empty').glob('*/report.json'):
        doc = read_receipt(path)
        if doc.get('status') == 'no_proposals' and (path.parent / 'complete.json').exists():
            empty.add(path.parent.name)
    original['verified_empty_securities'] = len(empty)
    original['terminal_securities_including_empty'] = len(empty | set(original['completed_security_ids']))
    original['runtime'] = read_receipt(recovery / 'progress.json')
    old = previous.get('v7_work', {})
    original['delta'] = work_delta(original, old.get('original_discovery'))
    replays = {}
    for key, root, plan in [('initial', required / 'initial-replay',
                             validation / 'v7-pending-replay-plan-20260930-r0')]:
        if (root / 'progress.json').exists():
            replays[key] = (root, plan)
    for epoch in sorted((required / 'epochs').glob('*')):
        if (epoch / 'replay/progress.json').exists():
            replays[epoch.name] = (epoch / 'replay', epoch / 'replay-plan')
    replay_work = {}
    for key, (root, plan) in replays.items():
        summary = wave_work(root / 'waves', 'replayed_pending')
        report = read_receipt(plan / 'report.json')
        summary['required'] = {k: report[k] for k in ['securities', 'selected_cohorts', 'horizon_targets'] if k in report}
        summary['runtime'] = read_receipt(root / 'progress.json')
        summary['delta'] = work_delta(summary, old.get('replays', {}).get(key))
        replay_work[key] = summary
    captures = {}
    for epoch in sorted((required / 'epochs').glob('*')):
        if (epoch / 'capture/progress.json').exists():
            captures[epoch.name] = read_receipt(epoch / 'capture/progress.json')
    return dict(schema='v7-retained-work-v1', original_discovery=original,
                replays=replay_work, captures=captures,
                delta_baseline_at=previous.get('observed_at') if old else None,
                accounting_note='Counts include pending-input outcomes. Never sum discovery and replay rounds as unique work.')


def incubator_visibility(snapshot):
    latest = snapshot['receipts']['incubator/continual-v6/r5/latest-run.json']
    service = snapshot['services'].get('healys-v6-continual.service', {})
    fields = dict(line.split('=', 1) for line in service.get('output', '').splitlines() if '=' in line)
    if latest.get('error') or latest.get('errors') or fields.get('ActiveState') == 'failed':
        return dict(show=True, reason='failure_needs_attention')
    if latest.get('stage') != 'done' and fields.get('ActiveState') in ('active', 'activating'):
        return dict(show=True, reason='incubating', run_dir=latest.get('run_dir'))
    run = Path(latest.get('run_dir', '/nonexistent-incubator-run'))
    if (latest.get('status') in ('candidate_frozen', 'candidate_already_frozen') and
            (run / 'candidate/complete.json').exists() and
            (run / 'candidate/evaluation.json').exists()):
        return dict(show=False, reason='successful_freeze_omit_routine_update')
    return dict(show=True, reason='incomplete_or_unverified_check_receipts')


def paper_receipts():
    result = {}
    for name in ['scanner-dispatch-status.json', 'status.json', 'broker-status.json',
                 'position-monitor-status.json']:
        try:
            doc = json.loads((PAPER / name).read_text())
            result[name] = {k: doc[k] for k in ['status', 'checked_at', 'action',
                'phase', 'error', 'expiry_fallback_errors', 'exhausted_exit_ladders',
                'positions_before', 'data_through', 'elapsed_seconds', 'candidate_rows',
                'exit_errors', 'symbol_results', 'deadline'] if k in doc}
            if isinstance(doc.get('attempts'), list):
                result[name]['attempt_count'] = len(doc['attempts'])
                result[name]['last_attempt'] = doc['attempts'][-1] if doc['attempts'] else None
        except (OSError, ValueError) as exc:
            result[name] = dict(observation_error=str(exc))
    return result


def command(args, timeout=15):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return dict(returncode=result.returncode, output=result.stdout, error=result.stderr)
    except subprocess.TimeoutExpired:
        return dict(returncode=None, error='Observation command timed out')


def previous_observation(slot):
    # Same-slot refreshes must compare with the previous hour, not themselves.
    current = int(slot) if str(slot).isdigit() else int(time.time()) // 3600 * 3600
    candidates = sorted((int(p.stem.removeprefix('runtime-')), p)
        for p in STATE.glob('runtime-*.json')
        if p.stem.removeprefix('runtime-').isdigit() and
        int(p.stem.removeprefix('runtime-')) < current)
    for _, path in reversed(candidates):
        doc = read_receipt(path)
        if 'v7_work' in doc:
            return doc
    return {}


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
    result['paper_journal'] = command(['journalctl', '--user',
        '-u', 'healys-v6-alpaca-scanner.service', '-u', 'healys-v6-alpaca-orders.service',
        '--since', '-70 minutes', '-n', '80', '--no-pager'])
    result['scanner_journal'] = command(['journalctl', '--user',
        '-u', 'healys-v6-alpaca-scanner.service', '--since', '-70 minutes',
        '-n', '100', '--no-pager'])
    result['paper_receipts'] = paper_receipts()
    result['storage'] = command(['df', '-B1', '--output=source,target,size,used,avail'])
    result['memory'] = Path('/proc/meminfo').read_text()
    receipts = [
        'incubator/continual-v6/r5/latest-run.json',
        'incubator/continual-v6/r5/resources.json',
        'incubator/continual-v6/r5/service-exit.json',
        'nn_meta/validation/v7-required-inputs-20260930-r0/discovery/progress.json',
        'nn_meta/validation/v7-required-inputs-20260930-r0/frontier/progress.json',
        'nn_meta/validation/v7-execution-recovery-20260929-r0/progress.json',
    ]
    result['receipts'] = {}
    for name in receipts:
        try:
            result['receipts'][name] = json.loads((ROOT / name).read_text())
        except (OSError, ValueError) as exc:
            result['receipts'][name] = dict(observation_error=str(exc))
    previous = previous_observation(slot)
    result['v7_work'] = v7_work(previous)
    result['incubator_visibility'] = incubator_visibility(result)
    result['reporting_scope'] = dict(paper=True, v7_cumulative_work=True,
        completed_incubator=False, completed_storage=False)
    target = STATE / f'runtime-{slot}.json'
    save(target, result)
    save(STATE / 'runtime.json', result)
    return target


def dispatch(rpc, state, now, check=False):
    thread = rpc.call('thread/read', {'threadId': THREAD, 'includeTurns': False})['thread']
    if thread['id'] != THREAD or thread['cwd'] != str(ROOT):
        raise ValueError('Refusing delivery to a different thread/project')
    queue = rpc.call('thread/queue/list', {'threadId': THREAD, 'limit': 100})['data']
    ours = [q for q in queue if any(p.get('text', '').startswith((PREFIX, LEGACY_PREFIX)) for p in q['input'])]
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
