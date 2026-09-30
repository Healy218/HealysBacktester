#!/usr/bin/env python3
"""Resume a frozen finite replay queue across checkpoint slices without an overall cutoff."""
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
sys.path.insert(0,str(ROOT))
from incubator.continual.storage import write
from nn_meta.v7.storage import sha

STATE = ROOT / 'nn_meta/validation/v7-until-complete-20260929-r0'
PREVIOUS_UNIT = 'healys-v7-pending-overnight-20260929.service'


def decision(progress):
    if progress.get('failed') or progress.get('status') == 'failed':
        return 'failed'
    if progress.get('status') == 'replayed_pending':
        if progress['securities_replayed'] != progress['securities_required']:
            raise ValueError('Completion count differs')
        return 'complete'
    if progress.get('status') == 'checkpointed':
        return 'continue'
    raise ValueError('Expected a stopped campaign receipt')


def available():
    fields=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
    return int(fields['MemAvailable'].split()[0])*1024 >= 6*1024**3 and shutil.disk_usage(ROOT).free >= 20_000_000_000


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,required=True);args=parser.parse_args()
    if args.workers != 1:parser.error('One autosized worker required during coexistence')
    selected=json.loads((ROOT/'nn_meta/validation/v7-evening-continuation-20260929-r0/selected-replay.json').read_text())
    campaign=Path(selected['campaign']);declaration_path=campaign/'declaration.json'
    declaration=json.loads(declaration_path.read_text())
    STATE.mkdir(parents=True,exist_ok=True)
    lock=(STATE/'lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    binding=dict(campaign=str(campaign),declaration_sha256=sha(declaration_path),consumer_sha256=sha(__file__),
                 previous_unit=PREVIOUS_UNIT,overall_time_limit=None,checkpoint_slice_seconds=14400)
    anchor=STATE/'binding.json'
    if anchor.exists() and json.loads(anchor.read_text())!=binding:raise ValueError('Continuation inputs changed')
    write(anchor,binding)
    stopping=False;child=None;passes=0
    def stop(*_):
        nonlocal stopping
        stopping=True
        if child and child.poll() is None:child.terminate()
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    def report(phase,error=None):
        write(STATE/'progress.json',dict(phase=phase,updated_at=datetime.now(timezone.utc).isoformat(),
            campaign=str(campaign),continuation_passes=passes,overall_time_limit=None,error=error,
            full_execution_coverage=False))
    try:
        report('waiting_for_active_replay')
        while not stopping:
            running=subprocess.run(['systemctl','--user','show',PREVIOUS_UNIT,'-p','ActiveState','--value'],
                                   check=True,capture_output=True,text=True).stdout.strip()
            if running not in ('active','activating','deactivating'):break
            time.sleep(15)
        while not stopping:
            if sha(declaration_path)!=binding['declaration_sha256']:raise ValueError('Campaign declaration changed')
            progress=json.loads((campaign/'progress.json').read_text());next_step=decision(progress)
            if next_step=='failed':raise RuntimeError('Campaign failed; preserve evidence rather than retrying blindly')
            if next_step=='complete':report('complete');return
            if not available():
                report('waiting_for_resources');time.sleep(30);continue
            # Existing controller verifies all bound inputs and owns the campaign lock.
            command=[sys.executable,'-u',str(ROOT/'scripts/run_v7_pending_campaign.py')]
            for key,value in declaration['arguments'].items():command+=['--'+key,value]
            command+=['--state',str(campaign),'--workers',str(args.workers),'--slice-seconds','300','--max-seconds','14400']
            report('pending_replay');passes+=1
            child=subprocess.Popen(command,cwd=ROOT,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
            code=child.wait();child=None
            if stopping:break
            if code:raise RuntimeError('Pending replay exited '+str(code))
            # Re-enter until all frozen pending securities finish. No overall clock cutoff.
        report('stopped')
    except BaseException as exc:
        report('failed',type(exc).__name__+': '+str(exc));raise
    finally:
        if child and child.poll() is None:
            child.terminate()
            try:child.wait(timeout=60)
            except subprocess.TimeoutExpired:child.kill();child.wait()


if __name__=='__main__':main()
