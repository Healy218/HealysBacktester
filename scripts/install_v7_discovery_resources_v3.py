#!/usr/bin/env python3
"""Drain and replace only discovery scheduling, retaining every optimized wave."""
from datetime import datetime,timezone
import json
from pathlib import Path
import os
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from incubator.continual.storage import write
from nn_meta.v7.storage import sha
from scripts.v7_discovery_resources_v3 import admission
from scripts.lab_hourly_watch import v7_work
STATE=ROOT/'nn_meta/validation/v7-required-inputs-20261002-perf-r0'
EVIDENCE=ROOT/'nn_meta/validation/v7-discovery-resources-20261002-r3'
UNIT='healys-v7-required-discovery-20260930.service'


def control(*args):return subprocess.check_output(['systemctl','--user',*args],text=True)

def main():
    EVIDENCE.mkdir(exist_ok=True)
    if (EVIDENCE/'deployment.json').exists():raise ValueError('Already installed')
    old=json.loads((STATE/'discovery-campaign/declaration.json').read_text())
    for p,h in old['inputs'].items():
        if sha(p)!=h:raise ValueError('Bound source changed: '+p)
    before=dict(observed_at=datetime.now(timezone.utc).isoformat(),service=control('cat',UNIT),
        work=v7_work({})['original_discovery'],admission=admission(12),
        declaration_sha256=sha(STATE/'discovery-campaign/declaration.json'),
        authorization='2026-10-02 user: put as many workers as we can on this and reevaluate the time')
    write(EVIDENCE/'before.json',before)
    control('stop','--no-block',UNIT)
    last=0
    while control('show',UNIT,'-p','ActiveState','--value').strip() not in ['inactive','failed']:
        if time.monotonic()-last>30:print('Discovery draining its current bounded slice',flush=True);last=time.monotonic()
        time.sleep(2)
    stopped=json.loads((STATE/'discovery-campaign/progress.json').read_text())
    if stopped['status']!='checkpointed' or stopped.get('failed_securities'):raise ValueError('Unexpected stopped state')
    if before['declaration_sha256']!=sha(STATE/'discovery-campaign/declaration.json'):raise ValueError('Declaration changed')
    write(EVIDENCE/'stopped.json',dict(progress=stopped,work=v7_work({})['original_discovery']))
    target=Path('/run/user')/str(os.getuid())/'systemd/user'/(UNIT+'.d')/'zzz-resources-v3.conf'
    source=ROOT/'deploy/systemd'/(UNIT+'.d')/target.name
    if target.exists() and target.read_text()!=source.read_text():raise ValueError('Conflicting installed resource revision')
    target.write_text(source.read_text());control('daemon-reload')
    started=datetime.now(timezone.utc).isoformat()
    baseline=v7_work({})['original_discovery']
    control('start',UNIT)
    write(EVIDENCE/'deployment.json',dict(installed_at=started,work_baseline=baseline,admission=admission(12),
        unchanged_declaration_sha256=before['declaration_sha256'],
        service=control('show',UNIT,'-p','ActiveState','-p','ExecStart','-p','MemoryMax'),dropin=str(target),dropin_sha256=sha(target)))
    print(json.dumps(dict(installed_at=started,admission=admission(12))),flush=True)

if __name__=='__main__':main()
