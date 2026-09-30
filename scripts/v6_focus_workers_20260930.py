#!/usr/bin/env python3
"""Resume the dedicated V6 run with a separately recorded data-worker budget."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import v6_focus_20260930 as focus
from incubator.continual.storage import identity, sha, verify, write

REVISION = focus.STATE / 'worker-revisions/r1'


def resource_plan(worker_mib, available_workers=None, cpus=None):
    if worker_mib < 3584:
        raise ValueError('Worker budget is below the measured revision floor')
    if available_workers is None:
        available_workers = int(subprocess.check_output(['bash', '-c',
            'source scripts/lib/autosize.sh; autosize_workers "$1" 4096',
            'v6-focus-workers', str(worker_mib)], cwd=ROOT, text=True).strip())
    cpus = cpus or len(os.sched_getaffinity(0))
    count = min(available_workers, cpus, (focus.MEMORY_MIB - 2048) // worker_mib)
    memory = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    available = int(memory['MemAvailable'].split()[0]) // 1024
    if count < 1 or available < worker_mib + 4096:
        raise ValueError('Insufficient memory for dedicated V6 restart')
    return dict(workers=count, worker_mib=worker_mib, host_reserve_mib=4096,
                parent_reserve_mib=2048, training_threads=cpus,
                memory_max_mib=focus.MEMORY_MIB, available_mib=available)


def snapshot(config, through):
    root = Path(config['root'])
    return {str(path): sha(path) for path in sorted((root/'runs'/through/'symbols').glob('*/complete.json'))}


def prepare():
    config, through, _ = focus.preflight()
    run = json.loads((Path(config['root'])/'latest-run.json').read_text())
    if run.get('training_started') or run.get('stage') != 'candidates_and_labels':
        raise ValueError('Worker change is only selected for the data stage')
    if (REVISION/'before.json').exists():
        raise ValueError('Revision already prepared; inspect its evidence')
    before = dict(observed_at=datetime.now(timezone.utc).isoformat(), run=run,
                  completed_symbols=snapshot(config, through),
                  focus=json.loads((focus.STATE/'progress.json').read_text()),
                  sources={str(Path(__file__).resolve()):sha(__file__),
                           str(ROOT/'scripts/v6_focus_20260930.py'):sha(ROOT/'scripts/v6_focus_20260930.py')})
    write(REVISION/'before.json', before)
    print(json.dumps(dict(prepared=True, completed_symbols=len(before['completed_symbols']), through=through)))


def run(worker_mib, auto_restore):
    config, through, _ = focus.preflight()
    before = json.loads((REVISION/'before.json').read_text())
    for name, digest in before['sources'].items():
        if sha(name) != digest:
            raise ValueError('Prepared resource wrapper changed')
    for name, digest in before['completed_symbols'].items():
        if sha(name) != digest:
            raise ValueError('A previously completed symbol seal changed')
    plan = json.loads((focus.STATE/'pause-plan.json').read_text())
    for name in plan['active_services']:
        if focus.properties(name)['ActiveState'] in {'active', 'activating', 'deactivating'}:
            raise ValueError('Competing job restarted: ' + name)
    for name in plan['timers']:
        if focus.properties(name)['ActiveState'] == 'active':
            raise ValueError('Competing timer restarted: ' + name)
    resources = resource_plan(worker_mib)
    root = Path(config['root'])
    invocation = root/'invocations'/(identity(config)+'.json')
    if not invocation.exists() or json.loads(invocation.read_text()) != config:
        raise ValueError('Original pinned invocation is not preserved')
    preserved = snapshot(config, through)
    write(REVISION/'restart.json', dict(observed_at=datetime.now(timezone.utc).isoformat(),
          resources=resources, through=through, completed_symbols=preserved,
          previous_seals_unchanged=True, sources=before['sources']))
    command = ['bash', str(ROOT/'scripts/run_v6_continual_v3.sh'), '--config', str(invocation),
               '--through', through, '--max-seconds', '86400', '--workers', str(resources['workers']),
               '--threads', str(resources['training_threads'])]
    focus.report('incubator_running', resources=resources, command=command,
                 resource_revision=str(REVISION), auto_restore=auto_restore,
                 candidate_complete=False, preserved_symbols=len(preserved))
    result = subprocess.run(command, cwd=ROOT, check=False)
    latest = json.loads((root/'latest-run.json').read_text())
    write(focus.STATE/'incubator-result.json', latest)
    if (result.returncode or latest.get('status') not in {'candidate_frozen','candidate_already_frozen'}
            or latest.get('scope') != 'full_universe' or latest.get('through') != through):
        focus.report('needs_review', returncode=result.returncode, incubator_status=latest.get('status'))
        raise RuntimeError('V6 candidate is incomplete; competing jobs remain paused')
    candidate=root/'runs'/through/'candidate'
    verify(candidate)
    focus.report('candidate_complete',candidate_complete=True,candidate=str(candidate),
                 candidate_sha256=sha(candidate/'complete.json'),verdict=latest.get('verdict'))
    if auto_restore:
        focus.restore(plan)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--worker-mib',type=int,default=3584)
    parser.add_argument('--auto-restore',action='store_true')
    args=parser.parse_args()
    if args.prepare:
        prepare()
        return
    with (focus.STATE/'lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            run(args.worker_mib,args.auto_restore)
        except Exception as exc:
            focus.report('failed',error=f'{type(exc).__name__}: {exc}')
            raise


if __name__=='__main__':
    main()
