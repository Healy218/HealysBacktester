#!/usr/bin/env python3
"""Continue exact V7 discovery/capture/replay epochs without an overall cutoff.

Publishes a closure candidate only after the full original queue and its pending
successor chain finish. Evidence review still owns gate closure. Unknown provider
admissions and unsupported requests are explicit blockers, never exclusions.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from incubator.continual.storage import write
from nn_meta.v7.storage import sha, verify

V = ROOT / 'nn_meta/validation'
D = ROOT / 'nn_meta/data_v7'
STATE = V / 'v7-required-inputs-20260930-r0'
ORIGINAL = V / 'v7-execution-campaign-20260928-r1'
RECOVERY = V / 'v7-execution-recovery-20260929-r0'
JOBS = V / 'v7-full-execution-plan-20260928'
POLICY = V / 'v7-contract-blackouts-20260929-held-approved'
ALTERNATES = V / 'v7-held-reference-admission-20260929-r1'
INITIAL = V / 'v7-pending-replay-campaign-20260929-20260929T233047Z'


def terminal(doc, mode):
    """Never infer completion from a service exit or a partial counter."""
    if any(doc.get(k) for k in ('failed', 'failed_securities', 'failed_batches', 'error')) or doc.get('status') == 'failed':
        raise RuntimeError('Explicit ' + mode + ' failure; inspect retained receipts')
    fields = {'capture': ('captured_snapshot', 'capture_windows_complete', 'capture_windows_required'),
              'discovery': ('discovered', 'securities_discovered', 'securities_required'),
              'replay': ('replayed_pending', 'securities_replayed', 'securities_required')}
    status, done, required = fields[mode]
    if doc.get('status') == status:
        if doc[done] != doc[required]:
            raise ValueError('False ' + mode + ' completion count')
        return True
    if doc.get('status') != 'checkpointed':
        raise ValueError('Expected stopped ' + mode + ' checkpoint')
    return False


class Controller:
    def __init__(self, mode):
        self.mode = mode
        self.root = STATE / mode
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = (self.root / 'lock').open('a')
        fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.stopping = False
        self.child = None
        scripts = ['finish_v7_required_inputs.py', 'reconcile_v7_frontier_v2.py',
                   'capture_v7_recovery_frontier.py', 'plan_v7_held_references.py',
                   'run_v7_reference_campaign.py', 'audit_v7_reference_campaign_v2.py',
                   'combine_v7_reference_epochs.py', 'plan_v7_pending_replay.py',
                   'run_v7_pending_campaign.py', 'replay_v7_pending_wave.py',
                   'continue_v7_inputs_20260930.sh', 'run_v7_execution_recovery.py']
        self.binding = dict(overall_time_limit=None, mode=mode,
                            sources={str(ROOT / 'scripts' / n): sha(ROOT / 'scripts' / n) for n in scripts})
        anchor = self.root / 'binding.json'
        if anchor.exists() and json.loads(anchor.read_text()) != self.binding:
            raise ValueError('Supervisor changed; use a new bound revision')
        write(anchor, self.binding)
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)

    def stop(self, *_):
        self.stopping = True
        if self.child and self.child.poll() is None:
            self.child.terminate()

    def report(self, phase, **details):
        write(self.root / 'progress.json', dict(phase=phase, updated_at=datetime.now(timezone.utc).isoformat(),
              overall_time_limit=None, gate_complete=False, **details))

    def check(self):
        if self.stopping:
            raise InterruptedError('Requested stop; checkpoints retained')
        if any(sha(p) != h for p, h in self.binding['sources'].items()):
            raise ValueError('Bound continuation source changed')

    def wait_unit(self, unit):
        self.report('waiting_for_existing_service', unit=unit)
        while True:
            self.check()
            state = subprocess.run(['systemctl', '--user', 'show', unit, '-p', 'ActiveState', '--value'],
                                   capture_output=True, text=True, check=True).stdout.strip()
            if state not in ('active', 'activating', 'deactivating'):
                return
            time.sleep(15)

    def capacity(self):
        while True:
            self.check()
            fields = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
            if int(fields['MemAvailable'].split()[0]) * 1024 >= 6 * 1024**3 and shutil.disk_usage(ROOT).free >= 20_000_000_000:
                return
            self.report('waiting_for_resources')
            time.sleep(30)

    def run(self, script, *arguments):
        self.capacity()
        self.report('executing', script=script, arguments=list(map(str, arguments)))
        self.child = subprocess.Popen([sys.executable, '-u', str(ROOT / 'scripts' / script), *map(str, arguments)],
             cwd=ROOT, env={**os.environ, 'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1', 'NUMBA_NUM_THREADS': '1'})
        code = self.child.wait()
        self.child = None
        self.check()
        if code:
            raise RuntimeError(script + ' exited ' + str(code))

    def workers(self, mb, cap):
        result = subprocess.run(['bash', '-c', 'source scripts/lib/autosize.sh; autosize_workers "$1" 16384',
                                 'v7-workers', str(mb)], cwd=ROOT, capture_output=True, text=True, check=True)
        return min(cap, int(result.stdout.strip()))

    def capture(self, snapshot, quotes, state, output, initial=False):
        if initial:
            self.wait_unit('healys-v7-frontier-20260930.service')
        state.mkdir(parents=True, exist_ok=True)
        while True:
            meter = state / 'progress.json'
            if meter.exists():
                doc = json.loads(meter.read_text())
                if terminal(doc, 'capture'):
                    index = json.loads((state / 'index-receipt.json').read_text())
                    path = Path(index['path'])
                    verify(path)
                    if sha(path / 'complete.json') != index['sha256'] or index['captured_windows'] != index['required_windows']:
                        raise ValueError('Capture index receipt differs')
                    return path
            history = state / 'supervised-passes'
            history.mkdir(exist_ok=True)
            n = len(list(history.glob('*.json'))) + 1
            attempt = history / f'{n:05d}.json'
            write(attempt, dict(previous=json.loads(meter.read_text()) if meter.exists() else None,
                               created_at=datetime.now(timezone.utc).isoformat()))
            self.run('capture_v7_recovery_frontier.py', 'capture', '--plan', snapshot, '--previous-index', quotes,
                     '--output', output, '--state', state, '--index-output', state / f'index-{n:05d}',
                     '--workers', self.workers(1024, 2), '--max-seconds', 14400)

    def discovery(self):
        self.wait_unit('healys-v7-discovery-20260930.service')
        while not terminal(json.loads((RECOVERY / 'progress.json').read_text()), 'discovery'):
            self.capacity()
            # The existing launcher verifies all frozen parent inputs and retains original waves.
            self.report('original_discovery')
            self.child = subprocess.Popen(['bash', str(ROOT / 'scripts/continue_v7_inputs_20260930.sh'), 'discovery'], cwd=ROOT)
            code = self.child.wait()
            self.child = None
            self.check()
            if code:
                raise RuntimeError('Original discovery exited ' + str(code))
        self.report('full_original_discovery_complete')

    def replay(self, parent, plan, quotes, references, campaign):
        if not plan.exists():
            self.run('plan_v7_pending_replay.py', '--parent', parent, '--jobs', JOBS, '--output', plan)
        verify(plan)
        report = json.loads((plan / 'report.json').read_text())
        if not report['securities']:
            return None
        while True:
            meter = campaign / 'progress.json'
            if meter.exists() and terminal(json.loads(meter.read_text()), 'replay'):
                return campaign
            self.run('run_v7_pending_campaign.py', '--plan', JOBS, '--replay-plan', plan,
                     '--base-index', quotes, '--entry-root', D / 'entry-campaign-20260927',
                     '--references', references, '--review', V / 'v7-reference-rename-review-20260928',
                     '--hours', V / 'v7-dated-hours-20260927', '--blackouts', POLICY,
                     '--state', campaign, '--workers', self.workers(3072, 1), '--slice-seconds', 300,
                     '--max-seconds', 14400)

    def epoch(self, parent, quotes, references, number, scope):
        directory = STATE / 'epochs' / f'{number:05d}'
        directory.mkdir(parents=True, exist_ok=True)
        selected = directory / 'selection.json'
        binding = dict(parent=str(parent), quotes=str(quotes), references=str(references), scope=scope)
        if selected.exists() and json.loads(selected.read_text()) != binding:
            raise ValueError('Epoch selection changed')
        write(selected, binding)
        raw, snapshot = directory / 'raw', directory / 'frontier'
        if not raw.exists():
            self.run('capture_v7_recovery_frontier.py', 'snapshot', '--parent', parent,
                     '--previous-index', quotes, '--output', raw)
        self.run('reconcile_v7_frontier_v2.py', '--raw', raw, '--quotes', quotes,
                 '--references', references, '--output', snapshot)
        report = json.loads((snapshot / 'report.json').read_text())
        if report['unsupported_requests']:
            raise RuntimeError('Actual non-option inputs need their existing specialized consumer: ' + str(snapshot / 'unsupported-requests.json'))
        if report['original_pending_rows'] and not report['capture_windows'] and not report['reference_requests']:
            parent_inputs = json.loads((parent / 'declaration.json').read_text())['inputs']
            if all(parent_inputs.get(str(p / 'complete.json')) == sha(p / 'complete.json') for p in (quotes, references)):
                raise RuntimeError('Replay still requests fully captured inputs in the same epoch: ' + str(snapshot))
        if report['reference_requests']:
            demand = directory / 'reference-demand'
            self.run('plan_v7_held_references.py', '--snapshot', snapshot, '--output', demand)
            reference_state = directory / 'reference-campaign'
            self.run('run_v7_reference_campaign.py', '--plan', demand,
                     '--output', D / 'required-inputs-20260930' / f'{number:05d}' / 'references',
                     '--state', reference_state, '--workers', self.workers(64, 4))
            audit = directory / 'reference-audit'
            if not audit.exists():
                self.run('audit_v7_reference_campaign_v2.py', '--campaign', reference_state,
                         '--blackouts', POLICY, '--output', audit)
            verify(audit)
            if not json.loads((audit / 'report.json').read_text())['admitted_under_existing_exclusions']:
                raise RuntimeError('New exact reference failures require alternate recovery/adjudication: ' + str(audit))
            combined = directory / 'reference-epoch'
            if not combined.exists():
                self.run('combine_v7_reference_epochs.py', '--audit', references, '--audit', audit,
                         '--alternate-review', ALTERNATES, '--output', combined)
            references = combined
        if report['capture_windows']:
            quotes = self.capture(snapshot, quotes, directory / 'capture',
                                  D / 'required-inputs-20260930' / f'{number:05d}' / 'quotes')
        next_parent = self.replay(parent, directory / 'replay-plan', quotes, references, directory / 'replay')
        result = dict(parent=str(next_parent) if next_parent else None, quotes=str(quotes),
                      references=str(references), scope=scope)
        write(directory / 'result.json', result)
        return next_parent, quotes, references

    def frontier(self):
        quotes = self.capture(V / 'v7-recovery-frontier-20260930-r0',
                              V / 'v7-frontier-quote-index-20260929-evening-r0',
                              V / 'v7-frontier-capture-20260930-r0', D / 'execution-recovery-20260930-r0', initial=True)
        references = V / 'v7-reference-epoch-20260930-r0'
        verify(references)
        parent = self.replay(INITIAL, V / 'v7-pending-replay-plan-20260930-r0', quotes, references,
                             STATE / 'initial-replay')
        scope = 'initial_93'
        number = 1
        while True:
            self.check()
            if parent is None:
                if scope == 'full_591':
                    # Migration completion is checked explicitly; no inferred storage closure.
                    migration = json.loads((V / 'v7-mrha-payload-migration-20260929-r1/progress.json').read_text())
                    if migration['status'] != 'complete' or migration['files_moved'] != migration['files_required']:
                        self.report('waiting_for_storage_reconciliation', migration=migration)
                        time.sleep(30)
                        continue
                    self.report('closure_candidate_ready', quote_index=str(quotes), reference_epoch=str(references),
                                completed_epochs=number - 1, full_original_discovery=str(RECOVERY))
                    return
                while not terminal_or_running(json.loads((RECOVERY / 'progress.json').read_text()), 'discovery'):
                    self.report('waiting_for_full_original_discovery')
                    self.check()
                    time.sleep(30)
                parent = ORIGINAL
                scope = 'full_591'
            directory = STATE / 'epochs' / f'{number:05d}'
            if (directory / 'result.json').exists():
                result = json.loads((directory / 'result.json').read_text())
                expected = json.loads((directory / 'selection.json').read_text())
                if expected != dict(parent=str(parent), quotes=str(quotes), references=str(references), scope=scope):
                    raise ValueError('Retained epoch lineage differs')
                parent = Path(result['parent']) if result['parent'] else None
                quotes, references = Path(result['quotes']), Path(result['references'])
            else:
                parent, quotes, references = self.epoch(parent, quotes, references, number, scope)
            number += 1


def terminal_or_running(doc, mode):
    if doc.get('status') in ('running', 'draining'):
        if any(doc.get(k) for k in ('failed', 'failed_securities', 'error')):
            raise RuntimeError('Concurrent discovery reports a failure')
        return False
    return terminal(doc, mode)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=('discovery', 'frontier'))
    a = p.parse_args()
    c = Controller(a.mode)
    try:
        getattr(c, a.mode)()
    except InterruptedError:
        c.report('stopped')
    except BaseException as exc:
        c.report('blocked', error=type(exc).__name__ + ': ' + str(exc))
        raise
    finally:
        if c.child and c.child.poll() is None:
            c.child.terminate()
            try:
                c.child.wait(timeout=60)
            except subprocess.TimeoutExpired:
                c.child.kill()
                c.child.wait()


if __name__ == '__main__':
    main()
