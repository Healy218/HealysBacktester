"""Run corrected V6 training, execution revalidation and a readiness inventory.

Preview is the default. --launch starts a bounded user systemd service;
--run is its foreground entry point. Existing campaign evidence is preserved.
No stage deploys a scanner or sends a notification.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys

from scripts.research_local import name
from scripts.v6_readiness import sha, read, verified_files

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ('scripts/v6_training_pipeline.py', 'scripts/v6_readiness.py',
           'scripts/continue_v6_training.py', 'scripts/validate_v6_execution.py',
           'nn_meta/execution_validation.py', 'nn_meta/v4_accounting.py')


def write(path, value):
    path = Path(path)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n')
    tmp.replace(path)


def environment(parent, campaign):
    env = dict(os.environ)
    resumed = read(ROOT / 'nn_meta/expanded_inputs' / parent / 'resume.json')['environment']
    final = ROOT / 'nn_meta/expanded_inputs' / parent / 'full-run/final-inputs.json'
    env.update(resumed)
    env.update(NN_META_CAMPAIGN=campaign, NN_META_V6_INPUTS=str(final),
               NN_META_V6_INPUTS_SHA256=final.with_suffix('.sha256').read_text().strip(),
               CUDA_VISIBLE_DEVICES='-1', TF_CPP_MIN_LOG_LEVEL='2',
               MPLCONFIGDIR='/tmp/healys-v6-pipeline-mpl', PYTHONUNBUFFERED='1')
    return env


def commands(parent, campaign, reuse, workers, threads):
    base = ROOT / 'nn_meta/campaigns' / campaign / 'v6'
    validation = ROOT / 'nn_meta/validation' / f'{campaign}-execution'
    python = str(ROOT / 'venv/bin/python')
    return {
        'training': [python, '-m', 'scripts.continue_v6_training', '--parent', parent,
            '--campaign', campaign, '--reuse-completed', reuse, '--repair-neural',
            '--workers', str(workers), '--threads', str(threads), '--run'],
        'execution': [python, '-m', 'scripts.validate_v6_execution', '--campaign-root', str(base),
                      '--output', str(validation)],
        'readiness': [python, '-m', 'scripts.v6_readiness', '--campaign-root', str(base),
                      '--execution-root', str(validation)]}


def training_outputs(base):
    """Do not trust unchanged receipt JSON when its referenced models changed."""
    latest = base / 'runs/continuation/latest.json'
    if read(latest).get('status') != 'complete':
        raise ValueError('training exited without a completion receipt')
    paths = [latest]
    for stage in ('assemble', 'experiments', 'evaluate', 'finalize'):
        path = base / 'runs/continuation' / f'{stage}.json'
        receipt = read(path)
        if receipt.get('returncode') != 0:
            raise ValueError(f'training has no successful {stage} receipt')
        verified_files(ROOT, receipt.get('outputs'))
        paths.append(path)
    return paths


def service_command(args):
    """Keep two complete physical cores free on this eight-core home host."""
    unit = f'healys-{args.campaign}'
    base = ROOT / 'nn_meta/campaigns' / args.campaign / 'v6/runs'
    return ['systemd-run', '--user', '--unit', unit, '--collect',
        '--description', f'V6 repaired training and validation: {args.campaign}',
        '--property=Type=exec', f'--property=WorkingDirectory={ROOT}',
        '--property=CPUQuota=600%', '--property=AllowedCPUs=2-7,10-15',
        '--property=Nice=10', '--property=MemoryMax=24G', '--property=MemorySwapMax=2G',
        '--property=OOMPolicy=stop', '--property=TimeoutStopSec=60',
        f'--property=StandardOutput=append:{base / "training-service.log"}',
        '--property=StandardError=inherit', str(ROOT / 'venv/bin/python'),
        '-m', 'scripts.v6_training_pipeline', '--parent', args.parent,
        '--campaign', args.campaign, '--reuse-completed', args.reuse_completed,
        '--workers', str(args.workers), '--threads', str(args.threads), '--run']


def run(args):
    base = ROOT / 'nn_meta/campaigns' / args.campaign / 'v6'
    records = base / 'runs/pipeline'
    records.mkdir(parents=True, exist_ok=True)
    plan = {'schema': 'v6-training-pipeline-v1', 'campaign': args.campaign,
            'commands': commands(args.parent, args.campaign, args.reuse_completed, args.workers, args.threads),
            'sources': {name: sha(ROOT / name) for name in SOURCES}, 'scanner_promotion': False}
    with (records / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (records / 'plan.json').exists():
            if read(records / 'plan.json') != plan:
                raise ValueError('pipeline code or configuration changed; preserve this run and use a fresh campaign')
        else:
            write(records / 'plan.json', plan)
        env = environment(args.parent, args.campaign)
        status = {'schema': plan['schema'], 'campaign': args.campaign, 'scanner_promotion': False,
                  'started_at': datetime.now(timezone.utc).isoformat(), 'stages': {}}
        try:
            for stage, command in plan['commands'].items():
                for path, digest in plan['sources'].items():
                    if sha(ROOT / path) != digest:
                        raise ValueError(f'pipeline source changed: {path}')
                receipt_path = records / f'{stage}.complete.json'
                if receipt_path.exists():
                    receipt = read(receipt_path)
                    if receipt.get('returncode') == 0:
                        verified_files(ROOT, receipt['outputs'])
                        if stage == 'training':
                            training_outputs(base)
                        status['stages'][stage] = 'complete'
                        continue
                status.update(status='running', stage=stage)
                write(records / 'status.json', status)
                print(f'Start pipeline stage {stage}', flush=True)
                log = records / f'{stage}.log'
                with log.open('w' if stage == 'readiness' else 'a') as stream:
                    result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
                for path, digest in plan['sources'].items():
                    if sha(ROOT / path) != digest:
                        raise ValueError(f'pipeline source changed during {stage}: {path}')
                if result.returncode:
                    raise RuntimeError(f'{stage} failed with exit {result.returncode}; see {log}')
                if stage == 'training':
                    paths = training_outputs(base)
                elif stage == 'execution':
                    output = ROOT / 'nn_meta/validation' / f'{args.campaign}-execution'
                    receipt = read(output / 'complete.json')
                    verified_files(output, receipt['outputs'])
                    paths = [output / 'complete.json', *(output / p for p in receipt['outputs'])]
                else:
                    report = read(log)
                    if report.get('schema') != 'v6-readiness-v1':
                        raise ValueError('readiness stage did not produce an inventory')
                    write(records / 'readiness.json', report)
                    paths = [records / 'readiness.json']
                write(receipt_path, {'returncode': 0,
                      'outputs': {str(p.relative_to(ROOT)): sha(p) for p in paths}})
                status['stages'][stage] = 'complete'
                print(f'Completed pipeline stage {stage}', flush=True)
            status.update(status='complete', stage=None, finished_at=datetime.now(timezone.utc).isoformat(),
                          promotion_status='blocked', readiness=str(records / 'readiness.json'))
        except Exception as exc:
            status.update(status='failed', error=str(exc), failed_at=datetime.now(timezone.utc).isoformat())
            write(records / 'status.json', status)
            raise
        write(records / 'status.json', status)
        print(json.dumps(status), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent', type=name, required=True)
    p.add_argument('--campaign', type=name, required=True)
    p.add_argument('--reuse-completed', type=name, required=True)
    p.add_argument('--workers', type=int, choices=range(1, 5), default=2)
    p.add_argument('--threads', type=int, choices=range(1, 5), default=2)
    group = p.add_mutually_exclusive_group()
    group.add_argument('--launch', action='store_true')
    group.add_argument('--run', action='store_true')
    a = p.parse_args()
    if len({a.parent, a.campaign, a.reuse_completed}) != 3:
        p.error('parent, new campaign and completed reuse campaign must be distinct')
    if a.launch:
        # Verifies all scope-bound training inputs before the durable launch.
        prepare = commands(a.parent, a.campaign, a.reuse_completed, a.workers, a.threads)['training']
        subprocess.run([*prepare[:-1], '--prepare-only'], cwd=ROOT, check=True)
        subprocess.run(service_command(a), cwd=ROOT, check=True)
    elif a.run:
        run(a)
    else:
        print(json.dumps({'preview': True, 'service_command': service_command(a),
            'stages': commands(a.parent, a.campaign, a.reuse_completed, a.workers, a.threads)}, indent=2))


if __name__ == '__main__':
    main()
