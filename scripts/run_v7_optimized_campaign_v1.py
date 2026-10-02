#!/usr/bin/env python3
"""Versioned optimized scheduling with a single selected wave per security."""
import argparse
from collections import deque
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from incubator.continual.storage import write
from nn_meta.v7.storage import sha, verify
from scripts.run_v7_execution_recovery_v2 import empty_job
from scripts.v7_discovery_resources_v2 import worker_limit

SOURCES = ['scripts/run_v7_optimized_campaign_v1.py', 'scripts/run_v7_execution_recovery_v2.py',
           'scripts/v7_discovery_resources_v2.py', 'scripts/lib/autosize.sh',
           'scripts/discover_v7_execution_wave_v4.py', 'scripts/replay_v7_pending_wave_v3.py',
           'nn_meta/v7/checkpoint_clone_v1.py', 'nn_meta/v7/wave_performance_v1.py']


def read(path):
    return json.loads(Path(path).read_text())


def select_wave(state, sid, destination):
    """Atomically change one view; never add parent and successor counts together."""
    link = state / 'waves' / sid
    temporary = link.with_name(sid + '.next')
    if temporary.is_symlink(): temporary.unlink()
    temporary.symlink_to(destination.resolve(), target_is_directory=True)
    temporary.replace(link)


def prepare(state, config_path):
    config = read(config_path)
    mode = config['mode']
    args = config['arguments']
    parent = Path(config['parent']) if config.get('parent') else None
    securities = config['securities']
    if len(set(securities)) != len(securities): raise ValueError('Duplicate securities')
    inputs = {str(ROOT/p): sha(ROOT/p) for p in SOURCES}
    inputs[str(config_path)] = sha(config_path)
    for name in ['base-index', 'references', 'review', 'hours', 'blackouts'] + (['replay-plan'] if mode == 'replay' else []):
        path = Path(args[name]); verify(path)
        inputs[str(path/'complete.json')] = sha(path/'complete.json')
    jobs = Path(args['plan'])
    inputs[str(jobs/'declaration.json')] = sha(jobs/'declaration.json')
    if not set(securities).issubset(set(read(jobs/'declaration.json')['securities'])):
        raise ValueError('Foreign job security')
    if parent:
        old = read(parent/'declaration.json')
        if old['securities'] != securities: raise ValueError('Parent security scope changed')
        for path, digest in old['inputs'].items():
            if sha(path) != digest: raise ValueError('Parent input changed: ' + path)
        inputs[str(parent/'declaration.json')] = sha(parent/'declaration.json')
        # Full scientific input equality is checked again during each wave import.
        if mode == 'replay' and old['arguments'] != args: raise ValueError('Replay arguments changed')
        if mode == 'discovery' and any(old[k] != args[k.replace('_','-')] for k in ['plan','base_index','entry_root']):
            raise ValueError('Discovery scope changed')
    declaration = dict(schema='v7-optimized-campaign-v1', mode=mode, inputs=inputs,
                       securities=securities, arguments=args, parent=str(parent) if parent else None,
                       wave_selection='one atomic symlink per security; completed predecessors retained',
                       disk_reserve_bytes=20_000_000_000, worker_policy='v7_discovery_resources_v2')
    anchor = state/'declaration.json'
    if anchor.exists() and read(anchor) != declaration: raise ValueError('Campaign changed; new revision required')
    for name in ['waves','revisions','logs','empty']: (state/name).mkdir(parents=True, exist_ok=True)
    write(anchor, declaration)
    if parent:
        for sid in securities:
            old_wave = parent/'waves'/sid
            link = state/'waves'/sid
            if old_wave.exists() and not link.exists(): select_wave(state, sid, old_wave)
    for path in config.get('empty_roots', []):
        for receipt in Path(path).glob('*/report.json'):
            if receipt.parent.name not in securities: raise ValueError('Foreign empty security')
            verify(receipt.parent)
            if read(receipt)['status'] != 'no_proposals': raise ValueError('Unverified empty security')
            link = state/'empty'/receipt.parent.name
            if not link.exists(): link.symlink_to(receipt.parent.resolve(), target_is_directory=True)
    return declaration


def command(state, config, sid, seconds, max_cohorts=0):
    mode = config['mode']
    script = 'discover_v7_execution_wave_v4.py' if mode == 'discovery' else 'replay_v7_pending_wave_v3.py'
    args = [sys.executable, '-u', str(ROOT/'scripts'/script)]
    for key, value in config['arguments'].items(): args += ['--'+key, value]
    args += ['--output', str(state/'revisions'/sid), '--security', sid,
             '--max-seconds', str(seconds), '--max-cohorts', str(max_cohorts)]
    if config.get('parent'):
        parent = Path(config['parent'])/'waves'/sid
        if (parent/'declaration.json').exists(): args += ['--checkpoint-from', str(parent)]
    return args


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--slice-seconds', type=int, default=600)
    parser.add_argument('--max-seconds', type=int, default=21600)
    parser.add_argument('--max-cohorts', type=int, default=0)
    parser.add_argument('--only-security', action='append')
    parser.add_argument('--prepare-only', action='store_true')
    a = parser.parse_args(); a.state=a.state.resolve(); a.config=a.config.resolve()
    if not a.state.is_relative_to(ROOT/'nn_meta/validation') or not 1 <= a.workers <= 4 or not 30 <= a.slice_seconds <= 1800:
        parser.error('Separate validation state and bounded workers/slices required')
    config = read(a.config)
    a.state.mkdir(parents=True, exist_ok=True)
    locks=[]
    for directory in [a.state, *map(Path, config.get('exclusive_roots', []))]:
        lock=(directory/'lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);locks.append(lock)
    declaration=prepare(a.state,a.config)
    if a.prepare_only: return
    mode=config['mode']; terminal='discovered' if mode=='discovery' else 'replayed_pending'
    selected=a.only_security or config['securities']
    if not set(selected).issubset(set(config['securities'])): parser.error('Foreign canary security')
    completed=set();empty=set(p.name for p in (a.state/'empty').iterdir());failed={}
    for sid in config['securities']:
        meter=a.state/'waves'/sid/'progress.json'
        if sid in empty or (meter.exists() and read(meter).get('status')==terminal): completed.add(sid)
    queue=deque(sid for sid in selected if sid not in completed)
    active={};stopping=False;reason=None;admitted=0;began=time.monotonic();deadline=began+a.max_seconds
    def stop(*_):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    def report(status):
        write(a.state/'progress.json',dict(status=status,updated_at=datetime.now(timezone.utc).isoformat(),
            securities_required=len(config['securities']),securities_discovered=len(completed) if mode=='discovery' else None,
            securities_replayed=len(completed) if mode=='replay' else None,empty_securities=sorted(empty),
            active_securities=list(active),admitted_workers=admitted,worker_ceiling=a.workers,
            queued_securities=len(queue),failed_securities=failed,error=reason if failed else None,
            resource_wait=reason if not failed else None,elapsed_seconds=time.monotonic()-began,
            full_execution_coverage=False,research_ready=False,canary=bool(a.only_security)))
    try:
        while queue or active:
            free=shutil.disk_usage(a.state).free
            reason='disk reserve' if free < 20_000_000_000 + (len(active)+1)*512*1024**2 else None
            admitted=worker_limit(min(a.workers,1) if mode=='replay' else a.workers)
            if not admitted and not reason: reason='memory reserve'
            while queue and len(active)<admitted and not reason and not stopping and time.monotonic()<deadline:
                if any(sha(p)!=h for p,h in declaration['inputs'].items()): raise ValueError('Campaign input changed')
                sid=queue.popleft();jobs=Path(config['arguments']['plan'])/'jobs'/sid
                if mode=='discovery' and read(jobs/'report.json')['proposals']==0 and empty_job(jobs):
                    from nn_meta.v7.storage import transaction,receipt
                    out=a.state/'empty'/sid
                    if not out.exists():
                        with transaction(out) as t:
                            write(t/'report.json',dict(status='no_proposals',security_id=sid,jobs_sha256=sha(jobs/'complete.json')))
                            receipt(t,dict(research_ready=False))
                    empty.add(sid);completed.add(sid);continue
                remaining=int(deadline-time.monotonic())
                if remaining<30:queue.appendleft(sid);break
                stream=(a.state/'logs'/(sid+'.log')).open('a')
                proc=subprocess.Popen(command(a.state,config,sid,min(a.slice_seconds,remaining),a.max_cohorts),
                    cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,
                    env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','NUMBA_NUM_THREADS':'1'})
                active[sid]=(proc,stream)
            for sid,(proc,stream) in list(active.items()):
                code=proc.poll()
                revision=a.state/'revisions'/sid
                # Publish only a bound imported/created checkpoint with a durable progress receipt.
                if (revision/'progress.json').exists():select_wave(a.state,sid,revision)
                if code is None:continue
                stream.close();del active[sid]
                meter=revision/'progress.json'
                if code:failed[sid]=dict(exit_code=code,log=str(a.state/'logs'/(sid+'.log')))
                elif meter.exists() and read(meter).get('status')==terminal:completed.add(sid)
                elif not a.only_security:queue.append(sid)
            report('draining' if stopping or time.monotonic()>=deadline else 'running')
            if failed: raise RuntimeError('Wave failed; checkpoints retained')
            if stopping or (time.monotonic()>=deadline and not active):break
            if queue or active:time.sleep(2)
    except BaseException as exc:
        reason=f'{type(exc).__name__}: {exc}';failed.setdefault('controller',reason);raise
    finally:
        # Let bounded slices finish rather than injecting SIGKILL into imports.
        if active: report('draining')
        for sid,(proc,stream) in active.items():
            code=proc.wait();stream.close()
            revision=a.state/'revisions'/sid
            if (revision/'progress.json').exists():select_wave(a.state,sid,revision)
            if code:failed[sid]=dict(exit_code=code)
            elif (revision/'progress.json').exists() and read(revision/'progress.json').get('status')==terminal:completed.add(sid)
        active.clear()
        report('failed' if failed else terminal if len(completed)==len(config['securities']) else 'checkpointed')
    if failed:raise SystemExit(1)

if __name__=='__main__':main()
