#!/usr/bin/env python3
"""Install and resume the explicitly authorized, validated V7 successor."""
import argparse
from datetime import datetime,timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.run_v7_optimized_campaign_v1 import read
from nn_meta.v7.storage import sha
from incubator.continual.storage import write
STATE=ROOT/'nn_meta/validation/v7-required-inputs-20261002-perf-r0'
UNITS={mode:f'healys-v7-required-{mode}-20260930.service' for mode in ['discovery','frontier']}


def control(*args):return subprocess.check_output(['systemctl','--user',*args],text=True)


def preflight():
    proof=read(STATE/'canary-validation/complete.json')
    if not proof['all_equal'] or proof['parity_sha256']!=sha(STATE/'canary-validation/parity.json'):
        raise ValueError('Missing canary parity')
    for campaign in [STATE/'discovery-campaign',STATE/'epochs/00001/replay']:
        doc=read(campaign/'declaration.json')
        for p,h in doc['inputs'].items():
            if sha(p)!=h:raise ValueError('Campaign source changed: '+p)
        progress=read(campaign/'progress.json')
        if progress['status']!='checkpointed' or progress.get('failed_securities'):
            raise ValueError('Campaign not at a healthy checkpoint')
    return dict(observed_at=datetime.now(timezone.utc).isoformat(),canary=proof,
        adoption_sha256=sha(STATE/'adoption.json'))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apply',action='store_true');a=p.parse_args()
    proof=preflight()
    if not a.apply:print(json.dumps(proof));return
    lock=(STATE/'install.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if (STATE/'deployment.json').exists():raise ValueError('Already deployed; inspect receipt')
    before={}
    for mode,unit in UNITS.items():
        active=control('show',unit,'-p','ActiveState','--value').strip()
        if active not in ['inactive','failed']:raise ValueError('Predecessor still active')
        before[unit]=control('cat',unit)
    write(STATE/'deployment-before.json',dict(**proof,units=before))
    for mode,unit in UNITS.items():
        target=Path('/run/user')/str(os.getuid())/'systemd/user'/(unit+'.d')/'zz-optimized-v1.conf'
        source=ROOT/'deploy/systemd'/(unit+'.d')/target.name
        if target.exists() and target.read_text()!=source.read_text():raise ValueError('Different installed revision')
        target.parent.mkdir(parents=True,exist_ok=True);target.write_text(source.read_text())
    control('daemon-reload')
    # Select the matching receipts before workers start, preserving the same cumulative baseline.
    write(ROOT/'logs/lab-hourly-watch/v7-selection.json',dict(required=str(STATE),discovery=str(STATE/'discovery-campaign'),
        initial_replay=str(ROOT/'nn_meta/validation/v7-required-inputs-20260930-r0/initial-replay'),
        adoption_sha256=sha(STATE/'adoption.json')))
    control('start',*UNITS.values())
    write(STATE/'deployment.json',dict(**proof,installed_at=datetime.now(timezone.utc).isoformat(),
        services={unit:control('show',unit,'-p','ActiveState','-p','SubState','-p','ExecStart','-p','MemoryMax','-p','TimeoutStopUSec') for unit in UNITS.values()}))
    print((STATE/'deployment.json').read_text())

if __name__=='__main__':main()
