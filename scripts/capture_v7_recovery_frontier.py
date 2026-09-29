#!/usr/bin/env python3
"""Freeze actual pending requests, then capture resumable packs from that snapshot."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone
import fcntl
import json
import multiprocessing
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def subtract(window, intervals):
    cursor, end = window['start_ns'], window['end_ns']
    for lo, hi in sorted(intervals):
        if hi <= cursor or lo >= end: continue
        if lo > cursor: yield {**window, 'start_ns': cursor, 'end_ns': min(lo, end)}
        cursor = max(cursor, min(hi, end))
    if cursor < end: yield {**window, 'start_ns': cursor, 'end_ns': end}


def snapshot(parent, previous, output):
    from nn_meta.v7.storage import sha, verify, identity, transaction, receipt
    from nn_meta.v7.quotes import capture_union
    from incubator.continual.storage import write
    parent, previous, output = map(lambda p: Path(p).resolve(), (parent, previous, output))
    if output.exists(): return verify(output)
    lock = (parent / 'lock').open('a'); fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    verify(previous)
    old = json.loads((parent / 'declaration.json').read_text())
    inputs = {str(parent / 'declaration.json'): sha(parent / 'declaration.json'),
              str(previous / 'complete.json'): sha(previous / 'complete.json'), str(Path(__file__)): sha(__file__)}
    observations = []; requests = {}; links = []; windows = {}; kinds = Counter()
    for path in sorted((parent / 'waves').glob('*/securities/*/wave.sqlite3')):
        wave = path.parents[2]; sid = path.parent.name
        guard = (wave / 'lock').open('a'); fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        declaration = json.loads((wave / 'declaration.json').read_text())
        binding = json.loads((path.parent / 'binding.json').read_text())
        index = wave / 'indexes' / sid
        if binding['campaign_identity'] != identity(declaration) or binding['quote_index_sha256'] != sha(index / 'complete.json'):
            raise ValueError('Wave checkpoint binding differs')
        if sid not in old['securities']: raise ValueError('Foreign checkpoint security')
        inputs.update(declaration['inputs']); inputs[str(index / 'complete.json')] = sha(index / 'complete.json')
        verify(index)
        # An interrupted writer can leave a hot rollback journal. Let SQLite
        # recover it under both controller and wave locks before a read-only
        # snapshot; immutable=1 would silently ignore that recovery evidence.
        recovery = dict(database_before_sha256=sha(path))
        for suffix in ['-journal', '-wal']:
            sidecar = Path(str(path) + suffix)
            if sidecar.exists(): recovery[suffix] = dict(bytes=sidecar.stat().st_size, sha256=sha(sidecar))
        with sqlite3.connect(path.as_uri() + '?mode=rw', uri=True) as recovered:
            if recovered.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                raise ValueError('Checkpoint SQLite integrity check failed')
        before = sha(path)
        with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
            extracted = [json.loads(row[0]) for row in db.execute('SELECT request FROM pending ORDER BY request_id')]
            cohorts = db.execute('SELECT COUNT(*) FROM cohorts').fetchone()[0]
        if sha(path) != before: raise ValueError('Wave changed while freezing actual requests')
        observations.append(dict(security_id=sid, database=str(path), observed_sha256=before,
                                 cohorts=cohorts, pending=len(extracted), requests_sha256=identity(extracted),
                                 binding=binding, declaration=declaration, sqlite_recovery=recovery))
        with sqlite3.connect((index / 'index.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
            for request in extracted:
                key = request['request_id']
                if key in requests and requests[key] != request: raise ValueError('Conflicting pending request identity')
                requests[key] = request; links.append([sid, key]); kinds[request['kind']] += 1
                if request['provider'] != 'massive' or request['kind'] not in ('quotes', 'trades'): continue
                scope = {k: request[k] for k in ['contract', 'kind', 'start_ns', 'end_ns']}
                intervals = db.execute('SELECT start_ns,end_ns FROM ranges WHERE contract=? AND kind=? '
                                       'AND start_ns<? AND end_ns>? ORDER BY start_ns',
                                       (scope['contract'], scope['kind'], scope['end_ns'], scope['start_ns']))
                for part in subtract(scope, intervals):
                    rid = identity(part); windows[rid] = dict(part, request_id=rid)
        guard.close()
    # These source-state hashes are observations, not mutable dependencies of
    # the sealed request snapshot. The complete extracted requests are retained.
    if any(sha(path) != digest for path, digest in inputs.items()): raise ValueError('Snapshot source changed')
    union = capture_union(windows.values(), max_span_ns=900_000_000_000)
    binding = dict(schema='v7-recovery-request-snapshot-v1', inputs=inputs,
                   parent=str(parent), previous_index=str(previous),
                   source_state_observations=observations, captures_sha256=identity(union['captures']))
    report = dict(waves=len(observations), pending_rows=len(links), distinct_requests=len(requests),
                  kinds=dict(kinds), capture_windows=len(union['captures']),
                  non_tick_requests=sum(r['kind'] not in ('quotes', 'trades') for r in requests.values()),
                  observed_at=datetime.now(timezone.utc).isoformat(), full_execution_coverage=False)
    with transaction(output) as temp:
        for name, doc in [('binding.json', binding), ('report.json', report), ('requests.json', requests),
                          ('security-requests.json', links), ('capture-plan.json', union)]:
            write(temp / name, doc)
        receipt(temp, dict(identity=identity(binding), research_ready=False))
    print(json.dumps(report), flush=True)
    return report


def batch_items(items, size=24):
    for offset in range(0, len(items), size): yield items[offset:offset + size]


def capture(plan, previous, output, state, index_output, workers, max_seconds):
    from nn_meta.v7.storage import sha, verify, identity, transaction, receipt
    from nn_meta.v7.packed_quote_index import write_index
    from scripts.capture_v7_joined_sample import worker
    from scripts.download_v7_data import tree_bytes, TASK_RESERVATION
    from incubator.continual.storage import write
    plan, previous, output, state, index_output = [Path(p).resolve() for p in [plan, previous, output, state, index_output]]
    verify(plan); verify(previous)
    origin = json.loads((plan / 'binding.json').read_text())
    if origin['inputs'].get(str(previous / 'complete.json')) != sha(previous / 'complete.json'):
        raise ValueError('Snapshot index differs')
    for path, digest in origin['inputs'].items():
        if sha(path) != digest: raise ValueError('Snapshot immutable input changed')
    items = json.loads((plan / 'capture-plan.json').read_text())['captures']
    sources = [Path(__file__), ROOT / 'scripts/capture_v7_joined_sample.py', ROOT / 'scripts/download_v7_data.py',
               ROOT / 'nn_meta/v7/packed_quotes.py', ROOT / 'nn_meta/v7/packed_quote_index.py',
               ROOT / 'options/data/massive_ticks.py', ROOT / 'docs/specs/V7_CAPTURE_STORAGE_V7_20260927.json']
    inputs = {str(p): sha(p) for p in sources}
    inputs[str(plan / 'complete.json')] = sha(plan / 'complete.json')
    inputs[str(previous / 'complete.json')] = sha(previous / 'complete.json')
    binding = dict(schema='v7-recovery-frontier-capture-v1', inputs=inputs, output=str(output), batch_size=24)
    output.mkdir(parents=True, exist_ok=True); state.mkdir(parents=True, exist_ok=True)
    lock = (state / 'lock').open('a'); fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    budget = ROOT / 'nn_meta/data_v7'
    acquisition = (budget / '.recovery-frontier.lock').open('a')
    fcntl.flock(acquisition, fcntl.LOCK_EX | fcntl.LOCK_NB)
    declaration = state / 'declaration.json'
    if declaration.exists() and json.loads(declaration.read_text()) != binding:
        raise ValueError('Capture controller contract changed')
    write(declaration, binding)
    queue = []; packs = []; completed = 0; failed = []; attempts = 0; active = {}
    for batch in batch_items(items):
        pack_binding = dict(parent=binding, captures=batch); key = identity(pack_binding)
        existing = [p for p in output.glob(key + '-*') if '.partial-' not in p.name and (p / 'complete.json').exists()]
        if len(existing) > 1: raise ValueError('Ambiguous completed pack attempts')
        if existing:
            verify(existing[0], expected_identity=key); packs.append(existing[0]); completed += len(batch)
        else: queue.append((batch, pack_binding, key))
    began = time.monotonic(); deadline = began + max_seconds; stopping = False; terminal = 'failed'; error = None
    def stop(signum, frame):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
    def progress(status):
        write(state / 'progress.json', dict(status=status, updated_at=datetime.now(timezone.utc).isoformat(),
              capture_windows_required=len(items), capture_windows_complete=completed, completed_packs=len(packs),
              active_batches=len(active), queued_batches=len(queue), failed_batches=failed, error=error,
              workers=workers, elapsed_seconds=time.monotonic()-began,
              snapshot=str(plan), index_output=str(index_output), full_execution_coverage=False, research_ready=False))
    try:
        with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn'), max_tasks_per_child=1) as pool:
            while queue or active:
                while queue and len(active) < workers and time.monotonic() < deadline and not stopping:
                    # Local reserve includes all concurrently reserved acquisition writes.
                    quota = json.loads((budget / 'quota.json').read_text())
                    inflight = sum(quota['reservations'].values()) + (len(active) + 1) * TASK_RESERVATION
                    if shutil.disk_usage(output).free < 10_000_000_000 + inflight:
                        stopping = True; error = 'Local disk reserve reached; remaining snapshot retained'; break
                    batch, pack_binding, key = queue.pop(0)
                    destination = output / (key + '-' + uuid.uuid4().hex)
                    task = pool.submit(worker, (batch, str(destination), str(budget), pack_binding))
                    active[task] = batch, destination; attempts += 1
                if not active: break
                done, _ = wait(active, timeout=5, return_when=FIRST_COMPLETED)
                for task in done:
                    batch, destination = active.pop(task)
                    try: result = task.result()
                    except Exception as exc:
                        result = dict(ok=False, pack=str(destination), error_type=type(exc).__name__, reason='Worker failed; no coverage inferred')
                    with transaction(state / 'attempts' / uuid.uuid4().hex) as temp:
                        write(temp / 'report.json', result); receipt(temp, dict(identity=identity(result)))
                    if result['ok']: packs.append(destination); completed += len(batch)
                    else: failed.append({k: result.get(k) for k in ['pack', 'error_type', 'reason']})
                progress('draining' if stopping or time.monotonic() >= deadline else 'capturing')
                if not active and (stopping or time.monotonic() >= deadline): break
        if any(sha(path) != digest for path, digest in inputs.items()): raise ValueError('Capture source changed')
        with sqlite3.connect((previous / 'index.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
            prior = [Path(row[0]) for row in db.execute('SELECT path FROM packs ORDER BY id')]
        index_binding = dict(schema='v7-recovery-frontier-index-v1', inputs=inputs,
                             packs={str(p): sha(p / 'complete.json') for p in prior + sorted(packs)})
        if index_output.exists(): verify(index_output, expected_identity=identity(index_binding))
        else: write_index(index_output, prior + sorted(packs), binding=index_binding)
        terminal = 'failed' if failed else ('captured_snapshot' if completed == len(items) else 'checkpointed')
        write(state / 'index-receipt.json', dict(path=str(index_output), sha256=sha(index_output / 'complete.json'),
              captured_windows=completed, required_windows=len(items), retained_bytes=sum(tree_bytes(p) for p in packs),
              full_execution_coverage=False))
    except BaseException as exc:
        error = type(exc).__name__ + ': capture controller stopped; inspect retained receipts'
        terminal = 'failed'; raise
    finally: progress(terminal)
    if failed: raise SystemExit(1)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['snapshot', 'capture'])
    for name in ['parent', 'plan', 'previous-index', 'output', 'state', 'index-output']:
        p.add_argument('--' + name, type=Path)
    p.add_argument('--workers', type=int, default=1)
    p.add_argument('--max-seconds', type=int, default=21600)
    a = p.parse_args()
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    if not a.output or not a.previous_index: p.error('Output and previous index required')
    if a.mode == 'snapshot':
        if not a.parent or not a.output.resolve().is_relative_to(ROOT / 'nn_meta/validation'):
            p.error('Parent and separate validation snapshot required')
        snapshot(a.parent, a.previous_index, a.output)
    else:
        if (not all([a.plan, a.state, a.index_output]) or not 1 <= a.workers <= 4 or a.max_seconds < 30
                or not a.output.resolve().is_relative_to(ROOT / 'nn_meta/data_v7')
                or not a.state.resolve().is_relative_to(ROOT / 'nn_meta/validation')
                or not a.index_output.resolve().is_relative_to(ROOT / 'nn_meta/validation')):
            p.error('Bounded workers/time and acquisition/validation destinations required')
        capture(a.plan, a.previous_index, a.output, a.state, a.index_output, a.workers, a.max_seconds)


if __name__ == '__main__':
    main()
