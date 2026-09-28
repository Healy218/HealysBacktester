#!/usr/bin/env python3
"""Acquire the already sealed exact reference demand in resumable immutable packs."""
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import sys
import threading
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nn_meta.v7.storage import sha,identity,verify,transaction,receipt
from nn_meta.v7.packed_references import query,write_pack,MAX_RESPONSE
from scripts.download_v7_data import save,quota_update,tree_bytes,TASK_RESERVATION
from scripts.v7_capture_storage import RESERVE

LOCAL=threading.local()


def fetch(item):
    import requests
    contract,day,old=item
    if old:
        path=Path(old);m=verify(path)
        return contract,day,m['http_status'],(path/'response.json').read_bytes(),dict(
            query=m['query'],retrieved_at=m['retrieved_at'],original_receipt_sha256=sha(path/'complete.json'),
            original_path=str(path),historical_publication_vintage_verified=False)
    if not hasattr(LOCAL,'session'):LOCAL.session=requests.Session()
    q=query(contract,day)
    for attempt in range(5):
        try:
            r=LOCAL.session.get('https://api.massive.com'+q['path'],params=q['params'],
                headers={'Authorization':'Bearer '+os.environ['MASSIVE_API_KEY']},timeout=30,
                allow_redirects=False,stream=True)
        except requests.RequestException:
            if attempt==4:raise RuntimeError('Reference transport failed') from None
            time.sleep(2**attempt);continue
        with r:
            if r.status_code in (429,500,502,503,504) and attempt<4:
                time.sleep(2**attempt);continue
            if r.status_code not in (200,404):raise RuntimeError('Reference HTTP '+str(r.status_code))
            body=b''
            for chunk in r.iter_content(8192):
                body+=chunk
                if len(body)>MAX_RESPONSE:raise ValueError('Reference response exceeds bounded size')
            return contract,day,r.status_code,body,dict(query=q,retrieved_at=datetime.now(timezone.utc).isoformat(),
                historical_publication_vintage_verified=False)
    raise RuntimeError('Reference retries exhausted')


def batch_jobs(plan, batch_size, reused):
    doc=json.loads((plan/'report.json').read_text())
    root=plan.with_suffix('.checkpoints')
    for sid,digest in sorted(doc['checkpoints'].items()):
        source=root/sid
        if sha(source/'complete.json')!=digest:raise ValueError('Reference demand receipt changed')
        verify(source)
        with sqlite3.connect((source/'references.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
            cursor=db.execute('SELECT contract,date FROM requests ORDER BY contract,date')
            while rows:=cursor.fetchmany(batch_size):
                items=[(c,d,reused.get((c,d))) for c,d in rows]
                yield sid,digest,items


def acquire(job, pool):
    destination=Path(job['destination']);binding=job['binding'];budget=Path(job['budget'])
    if destination.exists():
        verify(destination,expected_identity=identity(binding))
        return dict(status='reused_pack',**json.loads((destination/'report.json').read_text()),bytes=0)
    if shutil.disk_usage(budget).free<RESERVE+TASK_RESERVATION:
        raise RuntimeError('Local 10 GB free-space reserve reached; explicit overflow routing required')
    token=uuid.uuid4().hex;quota_update(budget,reserve=token)
    before=set(destination.parent.glob(destination.name+'.partial-*'))
    started=time.monotonic();error=None
    try:
        # executor.map preserves the canonical contract/date order in each pack.
        report=write_pack(destination,pool.map(fetch,job['items']),binding)
        return dict(status='captured',**report,bytes=tree_bytes(destination),seconds=time.monotonic()-started)
    except Exception as exc:
        error=dict(type=type(exc).__name__,reason=str(exc) if str(exc).startswith(('Reference ','Local ')) else 'Reference batch failed')
        raise
    finally:
        used=tree_bytes(destination) if destination.exists() else 0
        used+=sum(tree_bytes(p) for p in destination.parent.glob(destination.name+'.partial-*') if p not in before)
        quota_update(budget,finish=(token,used))
        save(Path(job['attempts'])/(token+'.json'),dict(destination=str(destination),bytes=used,
             seconds=time.monotonic()-started,complete=destination.exists(),error=error))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('plan','output','state'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--reuse-root',type=Path,action='append',default=[])
    p.add_argument('--workers',type=int,required=True,help='Bounded I/O concurrency from autosized launcher')
    p.add_argument('--max-batches',type=int,default=0)
    a=p.parse_args()
    for name in ('plan','output','state'):setattr(a,name,getattr(a,name).resolve())
    budget=ROOT/'nn_meta/data_v7'
    if not 1<=a.workers<=64 or a.max_batches<0 or not a.output.is_relative_to(budget) or not a.state.is_relative_to(ROOT/'nn_meta/validation'):
        p.error('Bounded paths/concurrency required')
    from dotenv import load_dotenv
    load_dotenv(ROOT/'.env')
    if not os.environ.get('MASSIVE_API_KEY'):raise ValueError('Massive credentials unavailable')
    a.state.mkdir(parents=True,exist_ok=True)
    with (a.state/'controller.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        verify(a.plan)
        sources={str(q):sha(q) for q in [Path(__file__),ROOT/'nn_meta/v7/packed_references.py',
            ROOT/'nn_meta/v7/storage.py',ROOT/'scripts/download_v7_data.py',ROOT/'scripts/v7_capture_storage.py',
            ROOT/'options/data/provider.py']}
        reused={};receipts={}
        for root in a.reuse_root:
            for path in sorted(root.resolve().glob('*/*/complete.json')):
                m=verify(path.parent);q=m.get('query',{})
                if not q.get('path','').startswith('/v3/reference/options/contracts/O:'):continue
                key=(q['path'].split('O:')[-1],q['params']['as_of'])
                if key not in reused:reused[key]=str(path.parent)
                receipts[str(path)]=sha(path)
        declaration=dict(schema='v7-exact-reference-campaign-v1',plan=str(a.plan),plan_sha256=sha(a.plan/'complete.json'),
            output=str(a.output),sources=sources,reused_receipts=receipts,batch_size=256,
            admission='Exact original standard-contract checks; unknown failures are not new blackouts',
            storage='Local packs; stop before 10 GB reserve; preserve shared allocation and reservations')
        campaign=identity(declaration)
        if (a.state/'declaration').exists():verify(a.state/'declaration',expected_identity=campaign)
        else:
            with transaction(a.state/'declaration') as temp:
                save(temp/'declaration.json',declaration);receipt(temp,dict(identity=campaign))
        stop=[]
        for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda n,f:stop.append('requested_drain'))
        totals=dict(responses=0,standard=0,unavailable_404=0,nonstandard=0,reused=0)
        completed=reused_packs=new_responses=new_bytes=0;began=time.monotonic();last=None;finished=False
        expected=json.loads((a.plan/'report.json').read_text())['contract_dates']
        def progress(status):
            save(a.state/'progress.json',dict(campaign_identity=campaign,status=status,
                updated_at=datetime.now(timezone.utc).isoformat(),expected_contract_dates=expected,
                **totals,completed_batches_this_run=completed,reused_packs=reused_packs,
                new_responses_this_run=new_responses,new_bytes_this_run=new_bytes,
                workers=a.workers,elapsed_seconds=time.monotonic()-began,last=last,
                local_free_bytes=shutil.disk_usage(budget).free,stop_reason=stop[0] if stop else None,
                full_reference_capture=finished and not stop and totals['responses']==expected,
                all_references_admitted=finished and not stop and totals['standard']==expected,
                training_started=False))
        progress('starting')
        try:
            with ThreadPoolExecutor(max_workers=a.workers) as pool:
                for sid,digest,items in batch_jobs(a.plan,256,reused):
                    if stop:break
                    if any(sha(q)!=h for q,h in sources.items()):raise ValueError('Reference producer changed')
                    scope=dict(security_id=sid,demand_receipt_sha256=digest,pairs=[(c,d) for c,d,_ in items])
                    binding=dict(campaign_identity=campaign,scope=scope,requests=len(items))
                    destination=a.output/sid/identity(scope)
                    last=acquire(dict(destination=str(destination),binding=binding,items=items,budget=str(budget),attempts=str(a.state/'attempts')),pool)
                    for key in totals:totals[key]+=last[key]
                    if last['status']=='reused_pack':reused_packs+=1
                    else:completed+=1;new_responses+=last['responses'];new_bytes+=last['bytes']
                    progress('running')
                    if a.max_batches and completed>=a.max_batches:stop.append('dispatch_limit');break
                else:finished=True
        except Exception as exc:
            stop.append(type(exc).__name__+': '+(str(exc) if str(exc).startswith(('Reference ','Local ')) else 'Acquisition/verification failed'))
            progress('failed');raise
        progress('complete' if finished else 'paused')
        print(json.dumps(dict(status='complete' if finished else 'paused',**totals,stop_reason=stop[0] if stop else None)))
        return 0


if __name__=='__main__':raise SystemExit(main())
