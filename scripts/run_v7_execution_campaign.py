#!/usr/bin/env python3
"""Fair, bounded process slices over all 591 immutable execution job stores."""
import argparse
from collections import deque
from datetime import datetime,timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['plan','base-index','entry-root','references','review','hours','blackouts','state']:
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--workers',type=int,required=True)
    p.add_argument('--slice-seconds',type=int,default=600)
    p.add_argument('--max-seconds',type=int,default=28800)
    a=p.parse_args()
    from nn_meta.v7.storage import sha,verify,identity
    from nn_meta.v7.execution_jobs import guard
    from incubator.continual.storage import write
    if not 1<=a.workers<=4 or not 30<=a.slice_seconds<=1800 or a.max_seconds<30:
        p.error('Measured worker/slice/campaign bounds required')
    for name,value in vars(a).items():
        if isinstance(value,Path):setattr(a,name,value.resolve())
    if not a.state.is_relative_to(ROOT/'nn_meta/validation'):p.error('Use separate campaign state')
    plan=json.loads((a.plan/'declaration.json').read_text());securities=plan['securities']
    inputs={str(a.plan/'declaration.json'):sha(a.plan/'declaration.json'),str(Path(__file__).resolve()):sha(__file__),
            str(ROOT/'scripts/discover_v7_execution_wave.py'):sha(ROOT/'scripts/discover_v7_execution_wave.py')}
    for path in [a.base_index,a.references,a.review,a.hours,a.blackouts]:
        verify(path);inputs[str(path/'complete.json')]=sha(path/'complete.json')
    declaration=dict(schema='v7-full-execution-campaign-v1',inputs=inputs,securities=securities,
                     plan=str(a.plan),base_index=str(a.base_index),entry_root=str(a.entry_root))
    a.state.mkdir(parents=True,exist_ok=True);(a.state/'logs').mkdir(exist_ok=True)
    lock=(a.state/'lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if (a.state/'declaration.json').exists() and json.loads((a.state/'declaration.json').read_text())!=declaration:
        raise ValueError('Campaign inputs changed; start another frozen epoch')
    write(a.state/'declaration.json',declaration)
    pending=deque(securities);active={};completed=set();failed={};last={}
    began=time.monotonic();deadline=began+a.max_seconds
    last_guard=began
    def progress(status):
        write(a.state/'progress.json',dict(status=status,campaign_identity=identity(declaration),
            updated_at=datetime.now(timezone.utc).isoformat(),securities_required=len(securities),
            securities_discovered=len(completed),failed_securities=failed,active_securities=list(active),
            queued_securities=len(pending),last=last,elapsed_seconds=time.monotonic()-began,
            full_execution_coverage=False,research_ready=False))
    progress('running')
    try:
        while pending or active:
            if time.monotonic()-last_guard>=30:
                guard(a.state,max_bytes=20_000_000_000,reserve_bytes=20_000_000_000)
                last_guard=time.monotonic()
            available=len(pending)
            while pending and len(active)<a.workers and time.monotonic()<deadline and available:
                available-=1;sid=pending.popleft();root=a.state/'waves'/sid
                meter=root/'progress.json'
                if meter.exists() and json.loads(meter.read_text()).get('status')=='discovered':
                    completed.add(sid);continue
                if not (a.plan/'jobs'/sid/'complete.json').exists():
                    pending.append(sid);continue
                remaining=int(deadline-time.monotonic())
                if remaining<30:pending.appendleft(sid);break
                command=[sys.executable,str(ROOT/'scripts/discover_v7_execution_wave.py')]
                for name in ['plan','base_index','entry_root','references','review','hours','blackouts']:
                    command+=['--'+name.replace('_','-'),str(getattr(a,name))]
                command+=['--output',str(root),'--security',sid,'--max-seconds',str(min(a.slice_seconds,remaining))]
                stream=(a.state/'logs'/(sid+'.log')).open('a')
                process=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT,
                    env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','NUMBA_NUM_THREADS':'1'},cwd=ROOT)
                active[sid]=(process,stream)
            for sid,(process,stream) in list(active.items()):
                code=process.poll()
                if code is None:continue
                stream.close();del active[sid]
                root=a.state/'waves'/sid;meter=root/'progress.json'
                last=json.loads(meter.read_text()) if meter.exists() else dict(security_id=sid)
                if code:
                    failed[sid]=dict(exit_code=code,log=str(a.state/'logs'/(sid+'.log')))
                elif last.get('status')=='discovered':completed.add(sid)
                else:pending.append(sid)
            progress('running')
            if time.monotonic()>=deadline and not active:break
            if not active and pending:
                planner=a.plan/'progress.json'
                if planner.exists() and json.loads(planner.read_text()).get('status')!='running':break
            if active or pending:time.sleep(5)
        if any(sha(path)!=digest for path,digest in inputs.items()):raise ValueError('Campaign bound inputs changed')
        progress('discovered' if len(completed)==len(securities) else 'checkpointed')
    finally:
        for process,stream in active.values():
            if process.poll() is None:process.terminate()
        for process,stream in active.values():
            try:process.wait(timeout=30)
            except subprocess.TimeoutExpired:process.kill();process.wait()
            stream.close()


if __name__=='__main__':main()
