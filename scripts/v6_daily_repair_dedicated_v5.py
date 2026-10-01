#!/usr/bin/env python3
"""Finish the bound two-symbol recovery, then restore the saved V7/storage plan."""
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
from incubator.continual.storage import sha, verify, write
from scripts import v6_focus_20260930 as focus
from scripts.v6_focus_workers_20260930 import resource_plan

STATE = ROOT/'nn_meta/validation/v6-daily-repair-20261001-r5'
RESEARCH = ROOT/'incubator/continual-v6/r5'
CONFIG = ROOT/'deploy/incubator-continual-v6-r5.json'
UNIT = 'healys-v6-continual.service'
PAUSE = ROOT/'nn_meta/validation/v6-daily-update-20260930-r4/dedicated/pause-plan.json'
DROPS = ['90-dedicated-r4.conf','95-dedicated-r5.conf']


def read(path): return json.loads(Path(path).read_text())


def unchanged_symbols():
    before = read(STATE/'prepared.json')['parent_symbol_seals']
    for name,digest in before.items():
        if sha(ROOT/'incubator/continual-v6/r4'/name) != digest:
            raise ValueError('Original completed symbol seal changed')
    return len(before)


def bind():
    from scripts.run_v6_continual_v5 import runtime_sources
    if (STATE/'bound.json').exists(): raise ValueError('Operational binding already exists')
    files = [Path(__file__),CONFIG,PAUSE,ROOT/'scripts/v6_focus_20260930.py',
             ROOT/'scripts/v6_focus_workers_20260930.py',
             *[ROOT/'deploy/systemd/healys-v6-continual.service.d'/name for name in DROPS]]
    write(STATE/'bound.json',dict(files={str(p):sha(p) for p in files},sources=runtime_sources(),
          preserved_symbols=unchanged_symbols(),bound_at=datetime.now(timezone.utc).isoformat()))


def run():
    from scripts.run_v6_continual_v5 import runtime_sources
    bound = read(STATE/'bound.json')
    if bound['sources'] != runtime_sources(): raise ValueError('Recovery producer changed')
    for name,digest in bound['files'].items():
        if sha(name) != digest: raise ValueError('Bound recovery operation changed: '+name)
    plan = read(PAUSE)
    for name in plan['active_services']:
        if name != UNIT and focus.properties(name)['ActiveState'] in {'active','activating','deactivating'}:
            raise ValueError('Competing job still active: '+name)
    resources = resource_plan(3584)
    resources['workers'] = min(5,resources['workers'])
    command = ['bash',str(ROOT/'scripts/run_v6_continual_v5.sh'),'--config',str(CONFIG),
               '--through','2026-09-30','--max-seconds','43200','--workers',str(resources['workers']),
               '--threads',str(resources['training_threads'])]
    write(RESEARCH/'resources.json',dict(resources=resources,phase='dedicated_daily_recovery_running',
          updated_at=datetime.now(timezone.utc).isoformat(),evidence=str(STATE)))
    focus.report('incubator_running',resources=resources,command=command,through='2026-09-30',
                 auto_restore=True,preserved_symbols=unchanged_symbols())
    result = subprocess.run(command,cwd=ROOT,check=False)
    latest = read(RESEARCH/'latest-run.json');write(STATE/'incubator-result.json',latest)
    if result.returncode or latest.get('status') not in {'candidate_frozen','candidate_already_frozen'}:
        focus.report('needs_review',returncode=result.returncode,run=latest)
        raise RuntimeError('Recovery incomplete; successful checkpoints retained and competitors paused')
    if latest['through'] != '2026-09-30' or latest['scope'] != 'full_universe':
        raise ValueError('Recovery completion scope differs')
    candidate = RESEARCH/'runs/2026-09-30/candidate';verify(candidate)
    focus.report('candidate_complete',candidate_sha256=sha(candidate/'complete.json'),
                 verdict=latest.get('verdict'),preserved_symbols=unchanged_symbols())
    for name in DROPS:
        override = Path(os.environ['XDG_RUNTIME_DIR'])/'systemd/user'/f'{UNIT}.d'/name
        expected = ROOT/'deploy/systemd/healys-v6-continual.service.d'/name
        if override.exists():
            if override.read_bytes() != expected.read_bytes(): raise ValueError('Runtime override changed')
            override.unlink()
    focus.ctl('daemon-reload')
    focus.restore(plan)
    write(RESEARCH/'resources.json',dict(resources=resources,phase='completed_competitors_restored',
          updated_at=datetime.now(timezone.utc).isoformat(),evidence=str(STATE)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind',action='store_true');args=parser.parse_args()
    STATE.mkdir(parents=True,exist_ok=True);focus.STATE=STATE
    with (STATE/'lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.bind: bind()
        else: run()


if __name__ == '__main__': main()
