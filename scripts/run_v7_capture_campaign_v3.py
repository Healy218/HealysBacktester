#!/usr/bin/env python3
"""Version 3: concurrent HTTP with retained original campaign and immutable v2 packs.

No source rebuild or training claim. Each completed batch is reusable by assembly;
limits pause dispatch and drain in-flight work without discarding completed packs.
"""
import argparse
from concurrent.futures import wait,FIRST_COMPLETED
from datetime import datetime,timezone
import fcntl
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import time
import uuid
import signal
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def missing_ranges(db,contract,kind,start,end):
    cursor=start
    for lo,hi in db.execute('SELECT start_ns,end_ns FROM ranges WHERE contract=? AND kind=? AND start_ns<? AND end_ns>? ORDER BY start_ns',(contract,kind,end,start)):
        if lo>cursor:yield cursor,min(lo,end)
        cursor=max(cursor,min(hi,end))
    if cursor<end:yield cursor,end


def batches(audit,existing,batch_size):
    from itertools import groupby
    from nn_meta.v7.storage import verify,sha,identity
    from scripts.audit_v7_contiguous_captures import ranges
    verify(audit);verify(existing)
    declared=json.loads((audit/'binding.json').read_text())
    census=json.loads((audit/'report.json').read_text())
    with sqlite3.connect((existing/'index.sqlite3').as_uri()+'?mode=ro&immutable=1',uri=True) as known:
        for sid in declared['securities']:
            parent=Path(declared['demand_root'])/'demand'/sid
            expected=census['inputs'][str(parent/'complete.json')]
            if sha(parent/'complete.json')!=expected:raise ValueError('Frozen demand changed')
            verify(parent)
            source=dict(security_id=sid,demand=str(parent),receipt_sha256=expected)
            items=[]
            with sqlite3.connect((parent/'demand.sqlite3').as_uri()+'?mode=ro&immutable=1',uri=True) as db:
                db.execute('PRAGMA cache_size=-1024')
                # Scan the covering index once, grouping kind within each dated contract.
                rows=db.execute('SELECT contract,date,kind,start_ns,end_ns FROM requests ORDER BY contract,date,kind,start_ns,end_ns')
                for (contract,day,kind),group in groupby(rows,key=lambda r:r[:3]):
                    for _,_,lo,hi in ranges((r[0],r[1],r[3],r[4]) for r in group):
                        for start,end in missing_ranges(known,contract,kind,lo,hi):
                            item=dict(contract=contract,kind=kind,start_ns=start,end_ns=end)
                            items.append(dict(item,capture_id=identity(item)))
                            if len(items)==batch_size:
                                yield source,items;items=[]
                if items:yield source,items


def pack_binding(source, items, campaign_identity, source_hashes):
    return dict(schema='v7-parallel-campaign-packed-batch-v1', campaign_identity=campaign_identity,
                source=source, captures=items, sources=source_hashes)


def reuse(destination, binding, legacy):
    from nn_meta.v7.storage import identity, verify
    if not destination.exists():
        return False
    actual = json.loads((destination/'binding.json').read_text())
    old = dict(binding, schema='v7-campaign-packed-batch-v1', sources=legacy['sources'])
    prior = dict(binding, sources=legacy.get('parallel_sources'))
    if actual not in (binding, old, prior):
        raise ValueError('Retained pack does not match the original or versioned producer')
    verify(destination, expected_identity=identity(actual))
    return True


def acquire(job):
    source,items,destination_text,budget_text,campaign_identity,source_hashes,attempts_text,legacy,io_threads=job
    from nn_meta.v7.storage import sha
    from nn_meta.v7.packed_quotes_v2 import write_pack
    from scripts.v7_parallel_capture_v3 import entries,stats
    from scripts.download_v7_data import quota_update,tree_bytes,save
    destination,budget=Path(destination_text),Path(budget_text)
    binding=pack_binding(source,items,campaign_identity,source_hashes)
    if any(sha(p)!=h for p,h in source_hashes.items()):raise ValueError('Capture producer changed')
    if reuse(destination,binding,legacy):
        return dict(status='reused',pack=str(destination),bytes=tree_bytes(destination),requests=len(items))
    attempt=uuid.uuid4().hex;failures=[];began=time.monotonic();before=stats()
    quota_update(budget,reserve=attempt)
    prior=set(destination.parent.glob(destination.name+'.partial-*'))
    ok=False;error=None
    stream=entries(items,failures,io_threads)
    try:
        write_pack(destination,stream,binding=binding);ok=True
    except Exception as exc:
        error=dict(type=type(exc).__name__,reason=str(exc) if str(exc).startswith(('Massive ticks HTTP ','Massive tick transport','Too many captures','Pack byte bound','Packed capture exceeds')) else 'Capture/verification failed')
    finally:
        stream.close()
        used=tree_bytes(destination) if destination.exists() else 0
        used+=sum(tree_bytes(p) for p in destination.parent.glob(destination.name+'.partial-*') if p not in prior)
        quota_update(budget,finish=(attempt,used))
        after=stats()
        report=dict(status='completed' if ok else 'failed',pack=str(destination),bytes=used,requests=len(items),
                    seconds=time.monotonic()-began,split_attempts=failures,error=error,
                    io_threads=io_threads,http={k:after[k]-before[k] for k in before})
        save(Path(attempts_text)/(attempt+'.json'),report)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('audit','existing-index','output','state'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--workers',type=int,required=True)
    p.add_argument('--io-threads',type=int,required=True)
    p.add_argument('--legacy-state',type=Path,required=True)
    p.add_argument('--parallel-parent',type=Path,required=True)
    p.add_argument('--batch-size',type=int,default=32)
    p.add_argument('--max-new-bytes',type=int,required=True)
    p.add_argument('--max-batches',type=int,default=0,help='Optional bounded dispatch; zero processes full demand')
    a=p.parse_args()
    from nn_meta.v7.runtime import configure_threads,worker_pool
    configure_threads(1)
    from nn_meta.v7.storage import sha,identity,verify,receipt,transaction
    from scripts.download_v7_data import save,TASK_RESERVATION
    for name in ('audit','existing_index','output','state'):setattr(a,name,getattr(a,name).resolve())
    budget=ROOT/'nn_meta/data_v7'
    if (not a.output.is_relative_to(budget) or not a.state.is_relative_to(ROOT/'nn_meta/validation')
            or not 1<=a.batch_size<=64 or not 1<=a.workers<=4 or not 1<=a.io_threads<=16 or a.max_batches<0):p.error('Bounded full-universe capture paths/workers required')
    capacity_path=ROOT/'docs/specs/V7_CAPTURE_CAPACITY_20260926.json'
    capacity=json.loads(capacity_path.read_text())
    # Includes the historical MRHA archive and post-inventory planning overhead.
    project_baseline_ceiling=490_000_000_000
    if not TASK_RESERVATION<=a.max_new_bytes<=capacity['project_limit_bytes']-project_baseline_ceiling:
        p.error('New allocation must fit the preserved total-project ceiling')
    a.state.mkdir(parents=True,exist_ok=True);a.output.mkdir(parents=True,exist_ok=True)
    lock=(a.state/'controller.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    a.legacy_state=a.legacy_state.resolve()
    legacy_lock=(a.legacy_state/'controller.lock').open('a')
    fcntl.flock(legacy_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    verify(a.legacy_state/'declaration')
    legacy=json.loads((a.legacy_state/'declaration/declaration.json').read_text())
    legacy_id=identity(legacy)
    a.parallel_parent=a.parallel_parent.resolve()
    parent_lock=(a.parallel_parent/'controller.lock').open('a')
    fcntl.flock(parent_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    verify(a.parallel_parent/'declaration')
    parent=json.loads((a.parallel_parent/'declaration/declaration.json').read_text())
    if parent['parent_campaign_identity']!=legacy_id:
        raise ValueError('Parallel parent does not bind the original campaign')
    if any(sha(q)!=h for q,h in parent['sources'].items()):
        raise ValueError('Prior parallel producer changed')
    legacy['parallel_sources']=parent['sources']
    if (legacy['audit']!=str(a.audit) or legacy['existing_index']!=str(a.existing_index)
            or legacy['output']!=str(a.output) or legacy['batch_size']!=a.batch_size
            or legacy['max_new_bytes']!=a.max_new_bytes):
        raise ValueError('Resume must preserve the original scope, batch keys and capacity')
    if any(sha(q)!=h for q,h in legacy['sources'].items()):
        raise ValueError('Original frozen producer changed')
    sources=[Path(__file__),ROOT/'scripts/v7_parallel_capture_v3.py',ROOT/'scripts/v7_parallel_capture.py',ROOT/'scripts/run_v7_capture_campaign_v2.py',ROOT/'scripts/run_v7_capture_campaign.py',ROOT/'nn_meta/v7/runtime.py',capacity_path,*[ROOT/q for q in ('nn_meta/v7/packed_quotes.py','nn_meta/v7/packed_quotes_v2.py',
        'nn_meta/v7/storage.py','options/data/massive_ticks.py','scripts/capture_v7_joined_sample.py',
        'scripts/audit_v7_contiguous_captures.py','scripts/download_v7_data.py')]]
    source_hashes={str(q):sha(q) for q in sources}
    declaration=dict(schema='v7-full-entry-parallel-campaign-v2',parent_campaign_identity=legacy_id,parallel_parent_identity=identity(parent),leaf_rows_bound=50000,maximum_io_threads_per_worker=16,audit=str(a.audit),audit_sha256=sha(a.audit/'complete.json'),
        existing_index=str(a.existing_index),existing_sha256=sha(a.existing_index/'complete.json'),
        output=str(a.output),batch_size=a.batch_size,max_new_bytes=a.max_new_bytes,
        disk_reserve_bytes=capacity['disk_reserve_bytes'],project_baseline_ceiling_bytes=project_baseline_ceiling,
        project_limit_bytes=capacity['project_limit_bytes'],sources=source_hashes,
        authorization='User directed speeding up the running download as much as possible on 2026-09-27; preserve scope, completed data, CPU threads and storage limits.',
        scope='All 591 frozen entry-demand stores; exact union minus immutable existing coverage; execution extensions follow separately',
        ready_for_training=False)
    run_id=identity(declaration)
    if (a.state/'declaration').exists():verify(a.state/'declaration',expected_identity=run_id)
    else:
        with transaction(a.state/'declaration') as temp:
            save(temp/'declaration.json',declaration);receipt(temp,dict(identity=run_id))
    invocation=uuid.uuid4().hex
    save(a.state/'invocations'/(invocation+'.json'),dict(campaign_identity=run_id,
        workers=a.workers,io_threads=a.io_threads,max_batches=a.max_batches,
        started_at=datetime.now(timezone.utc).isoformat()))
    meter=a.state/'progress.json'
    old=json.loads(meter.read_text()) if meter.exists() else {}
    if old.get('campaign_identity',run_id)!=run_id:raise ValueError('Campaign identity changed')
    # Reconcile retained files from the previous attempt exactly once, not per batch.
    from scripts.download_v7_data import tree_bytes
    charged=tree_bytes(a.output);completed=reused=requests=0;pending={};stop=None;last=None
    reused_requests=0;capture_began=None;shutdown=[]
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda signum,frame:shutdown.append(signum))
    began=time.monotonic();iterator=iter(batches(a.audit,a.existing_index,a.batch_size));finished=False
    def progress(status):
        save(meter,dict(campaign_identity=run_id,status=status,updated_at=datetime.now(timezone.utc).isoformat(),
            completed_batches_this_run=completed,reused_batches_this_run=reused,requests_this_run=requests,
            reused_requests=reused_requests,workers=a.workers,io_threads=a.io_threads,
            capture_seconds=0 if capture_began is None else time.monotonic()-capture_began,
            retained_campaign_bytes=charged,max_new_bytes=a.max_new_bytes,pending=len(pending),
            elapsed_seconds=time.monotonic()-began,last=last,stop_reason=stop,
            full_entry_coverage=finished and stop is None,training_started=False))
    progress('running')
    from scripts.v7_parallel_capture_v3 import initialize
    with ProcessPoolExecutor(max_workers=a.workers,mp_context=multiprocessing.get_context('spawn'),
            initializer=initialize,initargs=(a.io_threads,)) as pool:
        while not finished or pending:
            if shutdown:stop='requested_drain';finished=True
            while not finished and len(pending)<a.workers:
                quota=json.loads((budget/'quota.json').read_text())
                inflight=(len(pending)+1)*TASK_RESERVATION
                if (charged+inflight>a.max_new_bytes or shutil.disk_usage(budget).free<capacity['disk_reserve_bytes']+inflight
                        or quota['used_bytes']+sum(quota['reservations'].values())+TASK_RESERVATION>quota['limit_bytes']):
                    stop='capacity_guard';finished=True;break
                if a.max_batches and completed+len(pending)>=a.max_batches:
                    stop='dispatch_limit';finished=True;break
                try:source,items=next(iterator)
                except StopIteration:finished=True;break
                key=identity(dict(source=source,captures=items));destination=a.output/source['security_id']/key
                binding=pack_binding(source,items,legacy_id,source_hashes)
                if reuse(destination,binding,legacy):
                    reused+=1;reused_requests+=len(items)
                    if reused%256==0:progress('resuming')
                    if shutdown:stop='requested_drain';finished=True;break
                    continue
                if capture_began is None:capture_began=time.monotonic()
                job=(source,items,str(destination),str(budget),legacy_id,source_hashes,str(a.state/'attempts'),legacy,a.io_threads)
                pending[pool.submit(acquire,job)]=key
            if pending:
                done,_=wait(pending,timeout=15,return_when=FIRST_COMPLETED)
                for future in done:
                    del pending[future];last=future.result()
                    if last['status']=='reused':reused+=1
                    else:
                        charged+=last['bytes']
                        if last['status']=='completed':completed+=1;requests+=last['requests']
                        else:stop=last['error'];finished=True
                progress('draining' if stop else 'running')
            elif not finished:raise RuntimeError('Campaign made no progress')
    progress('paused' if stop else 'entry_capture_complete')
    save(a.state/'runs'/(invocation+'.json'),json.loads(meter.read_text()))
    print(json.dumps(json.loads(meter.read_text())))
    return 2 if stop not in (None,'dispatch_limit','requested_drain') else 0


if __name__=='__main__':raise SystemExit(main())
