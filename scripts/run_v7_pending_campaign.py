#!/usr/bin/env python3
"""Bounded sequential slices over a frozen actual-pending replay plan."""
import argparse
from collections import deque
from datetime import datetime,timezone
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from nn_meta.v7.storage import verify,sha,identity
from incubator.continual.storage import write


def main():
    p=argparse.ArgumentParser()
    names=['plan','replay-plan','base-index','entry-root','references','review','hours','blackouts','state']
    for n in names:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--workers',type=int,required=True);p.add_argument('--max-seconds',type=int,default=7200)
    p.add_argument('--slice-seconds',type=int,default=300);a=p.parse_args()
    if a.workers!=1 or a.max_seconds<30 or not 30<=a.slice_seconds<=600:p.error('One autosized worker and bounded slices required for V6 coexistence')
    for n in names:setattr(a,n.replace('-','_'),getattr(a,n.replace('-','_')).resolve())
    if not a.state.is_relative_to(ROOT/'nn_meta/validation'):p.error('Separate validation state required')
    a.state.mkdir(parents=True,exist_ok=True);(a.state/'logs').mkdir(exist_ok=True)
    lock=(a.state/'lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    inputs={str(x):sha(x) for x in [Path(__file__).resolve(),ROOT/'scripts/replay_v7_pending_wave.py']}
    for n in ['replay_plan','base_index','references','review','hours','blackouts']:
        root=getattr(a,n);verify(root);inputs[str(root/'complete.json')]=sha(root/'complete.json')
    securities=sorted(x.stem for x in a.replay_plan.glob('BBG*.json'))
    declaration=dict(schema='v7-pending-replay-campaign-v1',inputs=inputs,securities=securities,
        arguments={n:str(getattr(a,n.replace('-','_'))) for n in names if n!='state'})
    anchor=a.state/'declaration.json'
    if anchor.exists() and json.loads(anchor.read_text())!=declaration:raise ValueError('New inputs require a new epoch')
    write(anchor,declaration);queue=deque(securities);complete=set();failed={};active=None;stopping=False
    began=time.monotonic();deadline=began+a.max_seconds;reason=None
    def stop(*_):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    def progress(status):
        write(a.state/'progress.json',dict(status=status,updated_at=datetime.now(timezone.utc).isoformat(),
            securities_required=len(securities),securities_replayed=len(complete),queued=len(queue),
            active_security=active[0] if active else None,failed=failed,stop_reason=reason,
            elapsed_seconds=time.monotonic()-began,full_execution_coverage=False))
    try:
        while queue or active:
            memory={k:int(v.split()[0])*1024 for k,v in (line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())}
            if shutil.disk_usage(a.state).free<20_000_000_000 or memory['MemAvailable']<6*1024**3:
                reason='Coexistence memory/disk reserve';stopping=True
            if stopping or time.monotonic()>=deadline:
                if not active:break
            if not active and queue and not stopping:
                if any(sha(path)!=h for path,h in inputs.items()):raise ValueError('Campaign input changed')
                sid=queue.popleft();wave=a.state/'waves'/sid;meter=wave/'progress.json'
                if meter.exists() and json.loads(meter.read_text()).get('status')=='replayed_pending':
                    complete.add(sid);continue
                remaining=int(deadline-time.monotonic())
                if remaining<30:queue.appendleft(sid);break
                command=[sys.executable,str(ROOT/'scripts/replay_v7_pending_wave.py')]
                for n in names:
                    if n!='state':command+=['--'+n,str(getattr(a,n.replace('-','_')))]
                command+=['--output',str(wave),'--security',sid,'--max-seconds',str(min(a.slice_seconds,remaining))]
                stream=(a.state/'logs'/(sid+'.log')).open('a')
                proc=subprocess.Popen(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,
                    env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','NUMBA_NUM_THREADS':'1'})
                active=(sid,proc,stream)
            if active:
                sid,proc,stream=active
                if stopping and proc.poll() is None:proc.terminate()
                code=proc.poll()
                if code is not None:
                    stream.close();active=None
                    meter=a.state/'waves'/sid/'progress.json'
                    status=json.loads(meter.read_text()).get('status') if meter.exists() else None
                    if code and not stopping:failed[sid]=code
                    elif status=='replayed_pending':complete.add(sid)
                    else:queue.append(sid)
            progress('draining' if stopping or time.monotonic()>=deadline else 'running')
            time.sleep(5)
    except BaseException as exc:
        reason=type(exc).__name__+': '+str(exc)
        failed['controller']=reason
        raise
    finally:
        if active:
            sid,proc,stream=active
            if proc.poll() is None:proc.terminate()
            try:proc.wait(timeout=45)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
            stream.close();active=None
        progress('failed' if failed else ('replayed_pending' if len(complete)==len(securities) else 'checkpointed'))
    if failed:raise SystemExit(1)


if __name__=='__main__':main()
