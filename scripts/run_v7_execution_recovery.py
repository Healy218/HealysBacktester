#!/usr/bin/env python3
"""Resume unchanged cohort workers under a separately bound recovery controller."""
import argparse
from collections import deque
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def capacity(root, workers, reserve=10_000_000_000):
    # Generated databases share the host disk with acquisition. Reserve writes
    # for every active slice in addition to the authorized free-space floor.
    free = shutil.disk_usage(root).free
    if free < reserve + workers * 512 * 1024**2:
        raise ValueError('Execution disk reserve reached; checkpoints preserved')
    return free


def empty_job(jobs):
    """An absent quote index is valid only for a verified zero-demand queue."""
    from nn_meta.v7.storage import verify
    verify(jobs)
    report = json.loads((jobs / 'report.json').read_text())
    if report['proposals'] or report['distinct_horizons']:
        return False
    binding = json.loads((jobs / 'binding.json').read_text())
    demand = Path(binding['demand'])
    verify(demand)
    with sqlite3.connect((jobs / 'jobs.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
        if db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]:
            raise ValueError('Empty queue report differs from actual jobs')
    with sqlite3.connect((demand / 'demand.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
        if db.execute('SELECT COUNT(*) FROM selections').fetchone()[0]:
            raise ValueError('Empty queue has frozen selections')
    return True


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['plan', 'base-index', 'entry-root', 'references', 'review', 'hours',
                 'blackouts', 'parent-state', 'state']:
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--workers', type=int, required=True)
    p.add_argument('--slice-seconds', type=int, default=600)
    p.add_argument('--max-seconds', type=int, default=21600)
    a = p.parse_args()
    from nn_meta.v7.storage import sha, verify, identity, transaction, receipt
    from incubator.continual.storage import write
    if not 1 <= a.workers <= 2 or not 30 <= a.slice_seconds <= 1800 or a.max_seconds < 30:
        p.error('Bounded worker, slice and campaign budgets required')
    for name, value in vars(a).items():
        if isinstance(value, Path):
            setattr(a, name, value.resolve())
    if a.state == a.parent_state or not a.state.is_relative_to(ROOT / 'nn_meta/validation'):
        p.error('Separate recovery state required')
    a.state.mkdir(parents=True, exist_ok=True)
    (a.state / 'logs').mkdir(exist_ok=True)
    locks = []
    for path in [a.state / 'lock', a.parent_state / 'lock']:
        lock = path.open('a'); fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB); locks.append(lock)
    old = json.loads((a.parent_state / 'declaration.json').read_text())
    if (old['plan'], old['base_index'], old['entry_root']) != tuple(str(x) for x in [a.plan, a.base_index, a.entry_root]):
        raise ValueError('Recovery differs from frozen parent inputs')
    inputs = dict(old['inputs'])
    inputs[str(a.parent_state / 'declaration.json')] = sha(a.parent_state / 'declaration.json')
    inputs[str(Path(__file__))] = sha(__file__)
    policy = ROOT / 'docs/specs/V7_CAPTURE_STORAGE_V7_20260927.json'
    inputs[str(policy)] = sha(policy)
    for path in [a.base_index, a.references, a.review, a.hours, a.blackouts]:
        verify(path)
        if old['inputs'].get(str(path / 'complete.json')) != sha(path / 'complete.json'):
            raise ValueError('Recovery input differs from parent campaign')
    if any(sha(path) != digest for path, digest in inputs.items()):
        raise ValueError('Frozen recovery source changed')
    declaration = dict(schema='v7-execution-recovery-v1', inputs=inputs,
                       wave_root=str(a.parent_state / 'waves'), securities=old['securities'],
                       reserve_bytes=10_000_000_000, per_worker_write_reserve=512 * 1024**2,
                       preserves_original_wave_contracts=True)
    anchor = a.state / 'declaration.json'
    if anchor.exists() and json.loads(anchor.read_text()) != declaration:
        raise ValueError('Recovery contract changed; use a new controller revision')
    write(anchor, declaration)
    old_progress = a.parent_state / 'progress.json'
    if not (a.state / 'parent-stopped-progress.json').exists():
        write(a.state / 'parent-stopped-progress.json', json.loads(old_progress.read_text()))
    write(old_progress, {**json.loads(old_progress.read_text()), 'status': 'stopped',
                        'active_securities': [], 'successor': str(a.state),
                        'stop_reason': 'Prior controller stopped at its generated-store cap; recovery owns continuation',
                        'observed_at': datetime.now(timezone.utc).isoformat()})
    pending = deque(old['securities']); active = {}; completed = set(); failed = {}; empty = set()
    began = time.monotonic(); deadline = began + a.max_seconds; terminal = 'failed'; failure = None
    stopping = False
    def stop(signum, frame):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
    def progress(status):
        write(a.state / 'progress.json', dict(status=status, campaign_identity=identity(declaration),
              updated_at=datetime.now(timezone.utc).isoformat(), securities_required=len(old['securities']),
              securities_discovered=len(completed), empty_securities=sorted(empty), failed_securities=failed,
              active_securities=list(active), queued_securities=len(pending), error=failure,
              elapsed_seconds=time.monotonic()-began, local_free_bytes=shutil.disk_usage(a.state).free,
              full_execution_coverage=False, research_ready=False))
    try:
        while pending or active:
            capacity(a.state, a.workers)
            if any(sha(path) != digest for path, digest in inputs.items() if path.endswith('.py')):
                raise ValueError('Recovery runtime changed')
            available = len(pending)
            while pending and len(active) < a.workers and time.monotonic() < deadline and available and not stopping:
                available -= 1; sid = pending.popleft(); jobs = a.plan / 'jobs' / sid
                root = a.parent_state / 'waves' / sid; meter = root / 'progress.json'
                if meter.exists() and json.loads(meter.read_text()).get('status') == 'discovered':
                    completed.add(sid); continue
                if not (jobs / 'complete.json').exists():
                    pending.append(sid); continue
                expected = json.loads((jobs / 'report.json').read_text())
                if expected['proposals'] == 0 and empty_job(jobs):
                    output = a.state / 'empty' / sid
                    binding = dict(security_id=sid, jobs_sha256=sha(jobs / 'complete.json'),
                                   campaign_identity=identity(declaration))
                    if output.exists(): verify(output, expected_identity=identity(binding))
                    else:
                        with transaction(output) as temp:
                            write(temp / 'report.json', dict(binding=binding, status='no_proposals', proposals=0,
                                  distinct_horizons=0, pending_requests=0, numerical_labels=0))
                            receipt(temp, dict(identity=identity(binding)))
                    empty.add(sid); completed.add(sid); continue
                remaining = int(deadline - time.monotonic())
                if remaining < 30: pending.appendleft(sid); break
                command = [sys.executable, str(ROOT / 'scripts/discover_v7_execution_wave_v2.py')]
                for name in ['plan', 'base_index', 'entry_root', 'references', 'review', 'hours', 'blackouts']:
                    command += ['--' + name.replace('_', '-'), str(getattr(a, name))]
                command += ['--output', str(root), '--security', sid, '--max-seconds', str(min(a.slice_seconds, remaining))]
                stream = (a.state / 'logs' / (sid + '.log')).open('a')
                process = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT, cwd=ROOT,
                          env={**os.environ, 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1', 'NUMBA_NUM_THREADS': '1'})
                active[sid] = process, stream
            for sid, (process, stream) in list(active.items()):
                code = process.poll()
                if code is None: continue
                stream.close(); del active[sid]
                meter = a.parent_state / 'waves' / sid / 'progress.json'
                status = json.loads(meter.read_text()).get('status') if meter.exists() else None
                if code: failed[sid] = dict(exit_code=code, log=str(a.state / 'logs' / (sid + '.log')))
                elif status == 'discovered': completed.add(sid)
                else: pending.append(sid)
            progress('draining' if stopping or time.monotonic() >= deadline else 'running')
            if stopping: break
            if time.monotonic() >= deadline and not active: break
            if not active and pending:
                planner = json.loads((a.plan / 'progress.json').read_text())
                if planner.get('status') != 'running' and not any(
                        (a.plan / 'jobs' / sid / 'complete.json').exists() for sid in pending): break
            if pending or active: time.sleep(5)
        terminal = 'failed' if failed else ('discovered' if len(completed) == len(old['securities']) else 'checkpointed')
        if any(sha(path) != digest for path, digest in inputs.items()):
            raise ValueError('Recovery bound input changed')
    except BaseException as exc:
        failure = f'{type(exc).__name__}: {exc}'; terminal = 'failed'
        raise
    finally:
        for process, _ in active.values():
            if process.poll() is None: process.terminate()
        for sid, (process, stream) in list(active.items()):
            try: process.wait(timeout=30)
            except subprocess.TimeoutExpired: process.kill(); process.wait()
            stream.close()
            path = a.parent_state / 'waves' / sid / 'progress.json'
            if path.exists():
                doc = json.loads(path.read_text())
                if doc.get('status') == 'running':
                    write(path, {**doc, 'status': 'interrupted', 'terminal_controller': str(a.state),
                                 'observed_at': datetime.now(timezone.utc).isoformat()})
        active.clear(); progress(terminal)
    if failed: raise SystemExit(1)


if __name__ == '__main__':
    main()
