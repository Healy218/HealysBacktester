#!/usr/bin/env python3
"""Apply the prior dedicated allocation to the pinned V6 r4 two-day update."""
import argparse
from datetime import datetime,timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from incubator.continual.storage import sha,identity,verify,write
from scripts import v6_focus_20260930 as focus
from scripts.v6_focus_workers_20260930 import resource_plan

STATE=ROOT/'nn_meta/validation/v6-daily-update-20260930-r4/dedicated'
RESEARCH=ROOT/'incubator/continual-v6/r4'
UNIT='healys-v6-continual.service'
DROPIN='90-dedicated-r4.conf'


def read(path):return json.loads(Path(path).read_text())


def binding():
    from scripts.run_v6_continual_v4 import runtime_sources
    config=read(ROOT/'deploy/incubator-continual-v6-r4.json')
    run=read(RESEARCH/'latest-run.json')
    if run['through']!='2026-09-30' or run['scope']!='full_universe':raise ValueError('Unexpected daily scope')
    contract=read(RESEARCH/'contract.json')
    if contract['sources']!=runtime_sources() or identity(contract)!=run['contract_identity']:
        raise ValueError('Frozen r4 producer changed')
    dec=read(RESEARCH/'runs'/run['through']/'declaration.json')
    if sha(Path(dec['snapshot'])/'manifest.json')!=dec['snapshot_sha256']:raise ValueError('Snapshot changed')
    config=dict(config,bootstrap_snapshot=dict(path=dec['snapshot'],sha256=dec['snapshot_sha256'],through=run['through']))
    return config,run


def seals():
    result={}
    for p in sorted((RESEARCH/'runs/2026-09-30/symbols').glob('*/complete.json')):
        verify(p.parent);result[str(p)]=sha(p)
    return result


def selected_resources(previous, available=None):
    plan=resource_plan(3584,available_workers=available)
    # Match the prior measured selected worker count, subject to shared autosizing.
    plan['workers']=min(plan['workers'],previous['workers'])
    return plan


def prepare():
    _,run=binding()
    if run.get('training_started') or run['stage']!='candidates_and_labels':
        raise ValueError('This allocation change must precede training')
    if (STATE/'pause-plan.json').exists():raise ValueError('Dedicated pause already prepared; inspect receipts')
    prior=read(ROOT/'nn_meta/validation/v6-focus-20260930/worker-revisions/r1/restart.json')['resources']
    write(STATE/'before.json',dict(observed_at=datetime.now(timezone.utc).isoformat(),run=run,
          seals=seals(),prior_resources=prior,sources={str(Path(__file__).resolve()):sha(__file__),
          str(ROOT/'scripts/v6_focus_20260930.py'):sha(ROOT/'scripts/v6_focus_20260930.py'),
          str(ROOT/'scripts/v6_focus_workers_20260930.py'):sha(ROOT/'scripts/v6_focus_workers_20260930.py')}))
    plan=focus.inventory();write(STATE/'pause-plan.json',plan)
    focus.pause(plan)
    write(STATE/'stopped-run.json',read(RESEARCH/'latest-run.json'))
    exit_path=RESEARCH/'service-exit.json'
    if exit_path.exists():write(STATE/'prior-service-exit.json',read(exit_path))
    write(STATE/'preserved.json',dict(seals=seals()))
    print(json.dumps(dict(paused=True,completed_symbols=len(read(STATE/'preserved.json')['seals']))),flush=True)


def run():
    config,previous_run=binding()
    before=read(STATE/'before.json')
    for name,digest in before['sources'].items():
        if sha(name)!=digest:raise ValueError('Dedicated operational wrapper changed')
    for name,digest in read(STATE/'preserved.json')['seals'].items():
        if sha(name)!=digest:raise ValueError('Completed daily symbol seal changed')
    plan=read(STATE/'pause-plan.json')
    for name in plan['active_services']:
        if name==UNIT:continue
        if focus.properties(name)['ActiveState'] in {'active','activating','deactivating'}:
            raise ValueError('Competing batch job still running: '+name)
    for name in plan['timers']:
        if focus.properties(name)['ActiveState']=='active':raise ValueError('Competing timer still active: '+name)
    resources=selected_resources(before['prior_resources'])
    invocation=RESEARCH/'invocations'/(identity(config)+'.json')
    if invocation.exists() and read(invocation)!=config:raise ValueError('Pinned invocation changed')
    if not invocation.exists():write(invocation,config)
    command=['bash',str(ROOT/'scripts/run_v6_continual_v4.sh'),'--config',str(invocation),
             '--through','2026-09-30','--max-seconds','43200','--workers',str(resources['workers']),
             '--threads',str(resources['training_threads'])]
    write(RESEARCH/'resources.json',dict(resources=resources,phase='dedicated_daily_running',
          updated_at=datetime.now(timezone.utc).isoformat(),evidence=str(STATE)))
    focus.report('incubator_running',resources=resources,command=command,prior_run=previous_run,
                 through='2026-09-30',auto_restore=True)
    result=subprocess.run(command,cwd=ROOT,check=False)
    latest=read(RESEARCH/'latest-run.json');write(STATE/'incubator-result.json',latest)
    if result.returncode or latest.get('status') not in {'candidate_frozen','candidate_already_frozen'}:
        focus.report('needs_review',returncode=result.returncode,run=latest)
        raise RuntimeError('Daily update incomplete; retained checkpoints and paused competitors')
    if latest.get('through')!='2026-09-30' or latest.get('scope')!='full_universe':
        raise ValueError('Completed candidate scope differs')
    candidate=RESEARCH/'runs/2026-09-30/candidate';verify(candidate)
    focus.report('candidate_complete',candidate_sha256=sha(candidate/'complete.json'),verdict=latest.get('verdict'))
    override=Path(os.environ['XDG_RUNTIME_DIR'])/'systemd/user'/f'{UNIT}.d'/DROPIN
    expected=ROOT/'deploy/systemd/healys-v6-continual.service.d'/DROPIN
    if override.exists():
        if override.read_bytes()!=expected.read_bytes():raise ValueError('Temporary override changed; review before restoration')
        override.unlink()
    focus.ctl('daemon-reload')
    focus.restore(plan)
    write(RESEARCH/'resources.json',dict(resources=resources,phase='completed_competitors_restored',
          updated_at=datetime.now(timezone.utc).isoformat(),evidence=str(STATE)))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true')
    args=parser.parse_args()
    STATE.mkdir(parents=True,exist_ok=True)
    focus.STATE=STATE
    with (STATE/'lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.prepare:prepare()
        else:run()


if __name__=='__main__':main()
