#!/usr/bin/env python3
"""Same frozen entry queue and fast I/O, with authorized local/MRHA capacity."""
import argparse
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone
import fcntl
import json
import multiprocessing
from pathlib import Path
import shutil
import signal
import sys
import time
import uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def reuse(destination,binding,parents):
    from nn_meta.v7.storage import verify,identity
    if not destination.exists():return False
    actual=json.loads((destination/'binding.json').read_text())
    allowed=[binding]+[dict(binding,schema=schema,sources=sources) for schema,sources in parents]
    if actual not in allowed:raise ValueError('Retained pack producer or scope changed')
    verify(destination,expected_identity=identity(actual))
    return True


def acquire(job):
    from nn_meta.v7.storage import sha
    from nn_meta.v7.packed_quotes_v2 import write_pack
    from scripts.v7_parallel_capture_v5 import entries,stats
    from scripts.v7_capture_storage import physical_bytes,publish_locator,verify_mount
    from scripts.download_v7_data import quota_update,save
    logical,physical=Path(job['logical']),Path(job['physical'])
    if any(sha(p)!=h for p,h in job['binding']['sources'].items()):
        raise ValueError('Frozen producer changed')
    if reuse(logical,job['binding'],job['parents']):
        return dict(status='reused',pack=str(logical),bytes=0,requests=len(job['items']))
    external=logical!=physical
    if external:verify_mount(job['mount'],job['mount_uuid'])
    already=reuse(physical,job['binding'],job['parents']) if external else False
    token=uuid.uuid4().hex;began=time.monotonic();before=stats();failures=[]
    quota_update(Path(job['budget']),reserve=token)
    roots=list(dict.fromkeys([logical,physical]))
    prior={p:set(p.parent.glob(p.name+'.partial-*')) for p in roots}
    previous=sum(physical_bytes(p) for p in roots)
    stream=entries(job['items'],failures,job['io_threads'])
    ok=False;error=None
    try:
        if not already:write_pack(physical,stream,binding=job['binding'])
        if external:
            verify_mount(job['mount'],job['mount_uuid'])
            publish_locator(logical,physical)
        ok=True
    except Exception as exc:
        reason=str(exc)
        error=dict(type=type(exc).__name__,reason=reason if reason.startswith(('Massive ticks HTTP ','Massive tick transport','Too many captures','Pack byte bound','Packed capture exceeds','Authorized overflow')) else 'Capture/storage verification failed')
    finally:
        stream.close()
        used=sum(physical_bytes(p) for p in roots)-previous
        used+=sum(physical_bytes(part) for p in roots for part in p.parent.glob(p.name+'.partial-*') if part not in prior[p])
        quota_update(Path(job['budget']),finish=(token,used))
        after=stats()
        report=dict(status='completed' if ok else 'failed',pack=str(logical),physical_pack=str(physical),
            tier=job['tier'],bytes=used,requests=len(job['items']),seconds=time.monotonic()-began,
            io_threads=job['io_threads'],split_attempts=failures,error=error,
            recovered_external_pack=already,http={k:after[k]-before[k] for k in before})
        save(Path(job['attempts'])/(token+'.json'),report)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('audit','existing-index','output','state','overflow-mount'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--parent-state',type=Path,action='append',required=True)
    p.add_argument('--workers',type=int,required=True)
    p.add_argument('--io-threads',type=int,required=True)
    p.add_argument('--max-batches',type=int,default=0)
    p.add_argument('--force-overflow-batches',type=int,default=0,help='Retain a bounded number of real new packs on MRHA to validate routing')
    a=p.parse_args()
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    from nn_meta.v7.storage import sha,identity,verify,transaction,receipt
    from scripts.run_v7_capture_campaign_v3 import batches,pack_binding
    from scripts.v7_parallel_capture_v5 import initialize
    from scripts.v7_capture_storage import RESERVE,physical_bytes,route,verify_mount,expand_quota
    from scripts.download_v7_data import TASK_RESERVATION,save
    for name in ('audit','existing_index','output','state','overflow_mount'):
        setattr(a,name,getattr(a,name).resolve())
    budget=ROOT/'nn_meta/data_v7'
    if (not a.output.is_relative_to(budget) or not a.state.is_relative_to(ROOT/'nn_meta/validation')
            or not 1<=a.workers<=4 or not 1<=a.io_threads<=32 or min(a.max_batches,a.force_overflow_batches)<0):
        p.error('Bounded paths and workers required')
    policy_path=ROOT/'docs/specs/V7_CAPTURE_STORAGE_20260927.json'
    policy=json.loads(policy_path.read_text())
    if policy['local_reserve_bytes']!=RESERVE or policy['overflow_reserve_bytes']!=RESERVE:
        raise ValueError('Storage reserve policy drift')
    mount=verify_mount(a.overflow_mount,policy['overflow_uuid'])
    external=a.overflow_mount/policy['overflow_relative_root']
    a.state.mkdir(parents=True,exist_ok=True)
    locks=[]
    for state in [a.state,*a.parent_state]:
        lock=(state/'controller.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);locks.append(lock)
    parents=[];declarations=[];source_hashes={}
    for state in a.parent_state:
        verify(state/'declaration')
        d=json.loads((state/'declaration/declaration.json').read_text())
        if (d['audit']!=str(a.audit) or d['existing_index']!=str(a.existing_index)
                or d['output']!=str(a.output) or d['batch_size']!=32):
            raise ValueError('Parent scope changed')
        if any(sha(q)!=h for q,h in d['sources'].items()):raise ValueError('Parent producer changed')
        schema='v7-campaign-packed-batch-v1' if d['schema']=='v7-full-entry-capture-campaign-v1' else 'v7-parallel-campaign-packed-batch-v1'
        parents.append((schema,d['sources']));declarations.append(d);source_hashes.update(d['sources'])
    original=declarations[0];original_id=identity(original)
    if original['schema']!='v7-full-entry-capture-campaign-v1':raise ValueError('Original campaign must be first parent')
    if any(d.get('parent_campaign_identity')!=original_id for d in declarations[1:]):
        raise ValueError('Parent ancestry changed')
    for q in (Path(__file__),ROOT/'scripts/v7_capture_storage.py',ROOT/'scripts/v7_parallel_capture_v5.py',ROOT/'scripts/run_v7_capture_campaign_v4.py',ROOT/'scripts/run_v7_capture_campaign_v3.py',policy_path):
        source_hashes[str(q)]=sha(q)
    declaration=dict(schema='v7-full-entry-storage-campaign-v1',parent_campaign_identity=original_id,
        parents=[identity(d) for d in declarations],audit=str(a.audit),existing_index=str(a.existing_index),
        audit_sha256=sha(a.audit/'complete.json'),existing_sha256=sha(a.existing_index/'complete.json'),
        output=str(a.output),overflow_root=str(external),overflow_mount=str(a.overflow_mount),
        overflow_uuid=policy['overflow_uuid'],batch_size=32,sources=source_hashes,storage_policy=policy,
        scope=original['scope'],ready_for_training=False)
    run_id=identity(declaration)
    if (a.state/'declaration').exists():verify(a.state/'declaration',expected_identity=run_id)
    else:
        with transaction(a.state/'declaration') as temp:
            save(temp/'declaration.json',declaration);receipt(temp,dict(identity=run_id))
    external.mkdir(parents=True,exist_ok=True)
    a.output.mkdir(parents=True,exist_ok=True)
    headroom=max(0,shutil.disk_usage(budget).free-RESERVE)+max(0,shutil.disk_usage(external).free-RESERVE)
    amended=expand_quota(budget,headroom,authorization=policy['authorization'])
    invocation=uuid.uuid4().hex
    save(a.state/'invocations'/(invocation+'.json'),dict(campaign_identity=run_id,workers=a.workers,
        io_threads=a.io_threads,max_batches=a.max_batches,force_overflow_batches=a.force_overflow_batches,
        quota_amendment=amended,mount=mount,started_at=datetime.now(timezone.utc).isoformat()))
    charged=physical_bytes(a.output)+physical_bytes(external)
    completed=reused=requests=reused_requests=external_completed=0
    pending={};stop=None;last=None;finished=False;shutdown=[];capture_began=None
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda signum,frame:shutdown.append(signum))
    began=time.monotonic();iterator=iter(batches(a.audit,a.existing_index,32));meter=a.state/'progress.json'
    def progress(status):
        save(meter,dict(campaign_identity=run_id,status=status,updated_at=datetime.now(timezone.utc).isoformat(),
            completed_batches_this_run=completed,reused_batches_this_run=reused,requests_this_run=requests,
            reused_requests=reused_requests,external_batches_this_run=external_completed,workers=a.workers,io_threads=a.io_threads,
            capture_seconds=0 if capture_began is None else time.monotonic()-capture_began,retained_campaign_bytes=charged,
            local_free_bytes=shutil.disk_usage(budget).free,overflow_free_bytes=shutil.disk_usage(external).free,
            disk_reserve_bytes=RESERVE,capacity_mode='live_free_space_with_MRHA_overflow',pending=len(pending),
            elapsed_seconds=time.monotonic()-began,last=last,stop_reason=stop,
            full_entry_coverage=finished and stop is None,training_started=False))
    progress('resuming')
    with ProcessPoolExecutor(max_workers=a.workers,mp_context=multiprocessing.get_context('spawn'),
            initializer=initialize,initargs=(a.io_threads,)) as pool:
        while not finished or pending:
            if shutdown:stop='requested_drain';finished=True
            while not finished and len(pending)<a.workers:
                if a.max_batches and completed+len(pending)>=a.max_batches:stop='dispatch_limit';finished=True;break
                try:source,items=next(iterator)
                except StopIteration:finished=True;break
                key=identity(dict(source=source,captures=items));logical=a.output/source['security_id']/key
                binding=pack_binding(source,items,original_id,source_hashes)
                if reuse(logical,binding,parents):
                    reused+=1;reused_requests+=len(items)
                    if reused%256==0:progress('resuming')
                    if shutdown:stop='requested_drain';finished=True;break
                    continue
                outside=external/source['security_id']/key
                force=(external_completed+sum(t=='external' for t in pending.values())<a.force_overflow_batches) or outside.exists()
                tier=route(shutil.disk_usage(budget).free,shutil.disk_usage(external).free,list(pending.values()),TASK_RESERVATION,force_external=force)
                if tier is None:stop='disk_reserve_guard';finished=True;break
                quota=json.loads((budget/'quota.json').read_text())
                if quota['used_bytes']+sum(quota['reservations'].values())+TASK_RESERVATION>quota['limit_bytes']:
                    stop='acquisition_quota_guard';finished=True;break
                if tier=='external':verify_mount(a.overflow_mount,policy['overflow_uuid'])
                if capture_began is None:capture_began=time.monotonic()
                job=dict(logical=str(logical),physical=str(outside if tier=='external' else logical),budget=str(budget),
                    binding=binding,parents=parents,items=items,io_threads=a.io_threads,attempts=str(a.state/'attempts'),
                    tier=tier,mount=str(a.overflow_mount),mount_uuid=policy['overflow_uuid'])
                pending[pool.submit(acquire,job)]=tier
            if pending:
                done,_=wait(pending,timeout=15,return_when=FIRST_COMPLETED)
                for future in done:
                    tier=pending.pop(future);last=future.result()
                    if last['status']=='reused':reused+=1;reused_requests+=last['requests']
                    else:
                        charged+=last['bytes']
                        if last['status']=='completed':
                            completed+=1;requests+=last['requests'];external_completed+=int(tier=='external')
                        else:stop=last['error'];finished=True
                progress('draining' if stop else 'running')
            elif not finished:raise RuntimeError('No campaign progress')
    progress('paused' if stop else 'entry_capture_complete')
    save(a.state/'runs'/(invocation+'.json'),json.loads(meter.read_text()))
    return 2 if stop not in (None,'dispatch_limit','requested_drain') else 0


if __name__=='__main__':raise SystemExit(main())
