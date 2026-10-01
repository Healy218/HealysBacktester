#!/usr/bin/env python3
"""Retry terminal 502 symbol futures beside the pinned September 30 V6 pass."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from incubator.continual.storage import identity, sha, verify, write
from scripts import v6_focus_20260930 as focus

STATE = focus.STATE / 'symbol-retries-r1'
RUN = ROOT / 'incubator/continual-v6/r3'
CUTOFF = datetime(2026, 10, 1, 13, tzinfo=timezone.utc)  # next open minus 30 min
WORKER_MIB = 3584
TRANSIENT = 'TickDataError: Massive ticks HTTP 502'


def read(path):
    return json.loads(Path(path).read_text())


def pending(run, attempts, complete):
    return [e['symbol'] for e in run.get('errors', [])
            if e.get('error') == TRANSIENT and e['symbol'] not in complete
            and attempts.get(e['symbol'], 0) < 3]


def check_binding(run, plan):
    for key in ('started_at', 'through', 'contract_identity', 'run_dir'):
        if run.get(key) != plan['run'].get(key):
            raise ValueError('Main invocation changed: ' + key)


def safe_to_resume(run, complete):
    return (run.get('status') == 'blocked' and bool(run.get('errors'))
            and all(e.get('error') == TRANSIENT and e['symbol'] in complete
                    for e in run['errors']))


def resources_allow(workers, memory_current, available_workers):
    # One additional worker fits both shared autosizing and the combined budget.
    return (available_workers >= 1 and (workers + 1) * WORKER_MIB + 2048 <= focus.MEMORY_MIB
            and memory_current + WORKER_MIB * 1024**2 <= focus.MEMORY_MIB * 1024**2)


def report(phase, **kwargs):
    write(STATE / 'progress.json', dict(phase=phase, updated_at=datetime.now(timezone.utc).isoformat(), **kwargs))


def remaining():
    return (CUTOFF - datetime.now(timezone.utc)).total_seconds()


def preflight():
    from scripts.run_v6_continual_v3 import runtime_sources
    run = read(RUN / 'latest-run.json')
    active = read(focus.STATE / 'progress.json')
    command = active['command']
    config_path = Path(command[command.index('--config') + 1])
    config = read(config_path)
    contract = read(RUN / 'contract.json')
    if contract['sources'] != runtime_sources() or identity(contract) != run['contract_identity']:
        raise ValueError('Frozen runtime identity differs')
    if Path(config['root']) != RUN or run['through'] != '2026-09-28':
        raise ValueError('Unexpected research root/date')
    declaration = read(Path(run['run_dir']) / 'declaration.json')
    if sha(Path(declaration['snapshot']) / 'manifest.json') != declaration['snapshot_sha256']:
        raise ValueError('Snapshot anchor changed')
    if run['stage'] != 'candidates_and_labels' or run['status'] != 'running' or run.get('training_started'):
        raise ValueError('Main run is not in concurrent data preparation')
    if not run.get('errors') or any(e['error'] != TRANSIENT for e in run['errors']):
        raise ValueError('Expected only known terminal HTTP 502 errors')
    if remaining() <= 0:
        raise ValueError('Morning cutoff reached')
    return dict(run=run, config=str(config_path), config_sha256=sha(config_path),
                declaration=declaration, workers=active['resources']['workers'],
                source_sha256=sha(__file__), cutoff=CUTOFF.isoformat())


def child(symbol):
    from scripts.run_v6_continual_v3 import configure, one_symbol, runtime_sources
    plan = read(STATE / 'plan.json')
    run = read(RUN / 'latest-run.json')
    check_binding(run, plan)
    if symbol not in pending(run, {}, set()) or symbol not in plan['declaration']['symbols']:
        raise ValueError('Symbol is not a terminal failed future')
    if sha(plan['config']) != plan['config_sha256'] or sha(__file__) != plan['source_sha256']:
        raise ValueError('Retry invocation changed')
    contract = read(RUN / 'contract.json')
    if contract['sources'] != runtime_sources() or identity(contract) != run['contract_identity']:
        raise ValueError('Frozen runtime changed')
    config = read(plan['config'])
    config['contract_identity'] = run['contract_identity']
    configure(config)
    target = Path(run['run_dir']) / 'symbols' / symbol
    if (target / 'complete.json').exists():
        verify(target)
        return
    seconds = remaining()
    if seconds <= 0:
        raise TimeoutError('Morning cutoff reached')
    one_symbol(config, Path(plan['declaration']['snapshot']), symbol, RUN,
               run['through'], Path(run['run_dir']), time.monotonic() + seconds)
    verify(target)


def run_retries():
    plan = preflight()
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (STATE / 'plan.json').exists():
            raise ValueError('Retry already prepared; inspect its receipts')
        write(STATE / 'plan.json', plan)
        attempts, recovered, retry_after = {}, set(), {}
        while remaining() > 0:
            run = read(RUN / 'latest-run.json')
            check_binding(run, plan)
            complete = {p.parent.name for p in (Path(run['run_dir']) / 'symbols').glob('*/complete.json')}
            queue = pending(run, attempts, complete)
            queue = [s for s in queue if time.monotonic() >= retry_after.get(s, 0)]
            if queue:
                unit = focus.properties(focus.UNIT)
                memory = focus.ctl('show', focus.UNIT, '-p', 'MemoryCurrent', '--value').stdout.strip()
                reserve = 6144  # host + parent; aggregate planned worker budget checked below
                capacity = int(subprocess.check_output(['bash', '-c',
                    'source scripts/lib/autosize.sh; autosize_workers "$1" "$2"',
                    'v6-symbol-retry', str(WORKER_MIB), str(reserve)], cwd=ROOT, text=True).strip())
                memory_current = int(memory) if memory.isdigit() else 0
                available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                                     if line.startswith('MemAvailable:'))) // 1024
                if available < reserve + WORKER_MIB or not resources_allow(plan['workers'], memory_current, capacity):
                    report('waiting_for_memory', attempts=attempts, recovered=sorted(recovered))
                    time.sleep(15)
                    continue
                symbol = queue[0]
                attempts[symbol] = attempts.get(symbol, 0) + 1
                report('retrying', symbol=symbol, attempts=attempts, recovered=sorted(recovered))
                log_path = STATE / f'{symbol}-{attempts[symbol]}.log'
                with log_path.open('w') as log:
                    try:
                        result = subprocess.run([sys.executable, '-u', str(Path(__file__).resolve()), '--symbol', symbol],
                            cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=max(1, remaining()),
                            env={**os.environ, 'OMP_NUM_THREADS':'1', 'OPENBLAS_NUM_THREADS':'1', 'NUMBA_NUM_THREADS':'1'})
                        code = result.returncode
                    except subprocess.TimeoutExpired:
                        code = 124
                write(STATE / f'{symbol}-{attempts[symbol]}.json', dict(symbol=symbol, returncode=code,
                      completed_at=datetime.now(timezone.utc).isoformat(), log=str(log_path)))
                if code == 0:
                    verify(Path(run['run_dir']) / 'symbols' / symbol)
                    recovered.add(symbol)
                else:
                    retry_after[symbol] = time.monotonic() + 120
                continue
            unit = focus.properties(focus.UNIT)
            if unit['ActiveState'] not in {'active', 'activating', 'deactivating'}:
                if safe_to_resume(run, complete):
                    for error in run['errors']:
                        verify(Path(run['run_dir']) / 'symbols' / error['symbol'])
                    # All retry children exited. A fresh supervisor verifies seals,
                    # clears its old in-memory failures, then trains automatically.
                    write(STATE / 'prior-run.json', run)
                    write(STATE / 'prior-focus.json', read(focus.STATE / 'progress.json'))
                    exit_path = focus.STATE / 'service-exit.json'
                    if exit_path.exists():
                        write(STATE / 'prior-service-exit.json', read(exit_path))
                    focus.ctl('start', '--no-block', focus.UNIT)
                    report('supervisor_resume_requested', attempts=attempts, recovered=sorted(recovered))
                    return
                unresolved = pending(run, attempts, complete)
                if not unresolved:
                    report('needs_review', attempts=attempts, recovered=sorted(recovered), run=run)
                    return
            report('waiting', attempts=attempts, recovered=sorted(recovered))
            time.sleep(15)
        report('deadline_reached', attempts=attempts, recovered=sorted(recovered))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbol')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.check:
        plan = preflight()
        print(json.dumps(dict(through=plan['run']['through'], errors=plan['run']['errors'],
                             workers=plan['workers'], sources_verified=True)))
    elif args.symbol:
        child(args.symbol)
    else:
        try:
            run_retries()
        except Exception as exc:
            report('failed', error=f'{type(exc).__name__}: {exc}')
            raise


if __name__ == '__main__':
    main()
