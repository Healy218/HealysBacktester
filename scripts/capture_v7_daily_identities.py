"""Capture full-window daily listed identities with four bounded workers at most."""
from pathlib import Path
import argparse
import gzip
import json
import os
import sys
import time
import uuid
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def capture(task):
    import requests
    from dotenv import load_dotenv
    from nn_meta.v7.daily_identities import query, page_records, next_page, ENDPOINT
    from nn_meta.v7.storage import identity,receipt,transaction,verify
    from scripts.download_v7_data import quota_update,tree_bytes,disk_guard,TASK_RESERVATION
    day,exchange,output,budget,sources=task
    params=query(day,exchange);fingerprint=identity(dict(query=params,sources=sources))
    destination=output/day/exchange
    if destination.exists():
        doc=verify(destination,expected_identity=fingerprint)
        return dict(day=day,exchange=exchange,records=doc['records'],resumed=True)
    disk_guard(budget,100)
    load_dotenv(ROOT/'.env')
    reservation=uuid.uuid4().hex;quota_update(budget,reserve=reservation)
    before=sum(tree_bytes(p) for p in destination.parent.glob(exchange+'.partial-*'))
    try:
        with transaction(destination) as temp, requests.Session() as session:
            url=ENDPOINT;seen_urls=set();seen_symbols=set();count=used=0
            for page in range(100):
                if url in seen_urls:raise ValueError('Identity pagination loop')
                seen_urls.add(url)
                for attempt in range(5):
                    try:
                        response=session.get(url,params=params,
                            headers={'Authorization':'Bearer '+os.environ['MASSIVE_API_KEY']},
                            timeout=30,allow_redirects=False)
                    except requests.RequestException:
                        raise RuntimeError('Daily identity transport failed') from None
                    if response.status_code not in (429,500,502,503,504):break
                    time.sleep(2**attempt)
                if response.status_code!=200:
                    raise RuntimeError('Daily identity HTTP '+str(response.status_code))
                if len(response.content)>32*1024**2:raise ValueError('Oversized identity response')
                body=response.json();rows=page_records(body,exchange,seen_symbols)
                # Retain all returned records; omit next_url because it may contain credentials.
                retained=dict(results=rows,status=body['status'],count=len(rows),request_id=body.get('request_id'))
                payload=gzip.compress(json.dumps(retained,sort_keys=True).encode(),mtime=0)
                used+=len(payload)
                if used>TASK_RESERVATION//2:raise ValueError('Identity capture exceeds reservation')
                (temp/f'page-{page:03d}.json.gz').write_bytes(payload);count+=len(rows)
                if not body.get('next_url'):break
                url=next_page(body['next_url']);params=None
            else:raise ValueError('Identity pagination exceeds page bound')
            receipt(temp,dict(identity=fingerprint,query=query(day,exchange),sources=sources,
                records=count,pages=page+1,retrieved_at=datetime.now(timezone.utc).isoformat(),
                purpose='dated listed identity only; no stock prices or publication-safe fundamentals',
                historical_publication_vintage_verified=False,research_ready=False))
        return dict(day=day,exchange=exchange,records=count,resumed=False)
    finally:
        used=(tree_bytes(destination) if destination.exists() else 0)+sum(
            tree_bytes(p) for p in destination.parent.glob(exchange+'.partial-*'))-before
        quota_update(budget,finish=(reservation,max(used,0)))


def main():
    from nn_meta.v7.runtime import configure_threads,worker_pool
    configure_threads(1)
    from nn_meta.v7.daily_identities import EXCHANGES
    from nn_meta.v7.scope import HISTORY_START,HISTORY_END
    from nn_meta.v7.storage import sha,identity,verify,receipt,transaction
    import fcntl
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('calendar','output','budget-root'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--workers',type=int,required=True)
    parser.add_argument('--max-shards',type=int,help='Bound this invocation; retained declaration still covers full scope')
    args=parser.parse_args()
    if (not 1<=args.workers<=4 or not args.output.resolve().is_relative_to(args.budget_root.resolve())
            or not args.budget_root.resolve().is_relative_to(ROOT/'nn_meta')
            or args.max_shards is not None and args.max_shards<1):
        raise ValueError('Shared repository quota and one to four workers required')
    calendar=json.loads(args.calendar.read_text())
    all_days=[r['date'] for r in calendar['sessions']]
    days=[d for d in all_days if HISTORY_START<=d<=HISTORY_END]
    if all_days!=sorted(set(all_days)) or not days or days[0]!=HISTORY_START or days[-1]!=HISTORY_END:
        raise ValueError('Complete ordered active calendar required')
    sources={str(p):sha(p) for p in [Path(__file__),ROOT/'nn_meta/v7/daily_identities.py',
        ROOT/'nn_meta/v7/runtime.py',ROOT/'nn_meta/v7/storage.py',ROOT/'scripts/download_v7_data.py',
        ROOT/'nn_meta/v7/scope.py',ROOT/'nn_meta/v7/action_inventory.py']}
    declaration=dict(schema='v7-daily-listed-identities-v1',days=days,exchanges=EXCHANGES,
        calendar=str(args.calendar),calendar_sha256=sha(args.calendar),sources=sources,
        start=HISTORY_START,end=HISTORY_END,research_ready=False)
    args.output.mkdir(parents=True,exist_ok=True)
    with (args.output/'.capture.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        declaration=json.loads(json.dumps(declaration))
        manifest=args.output/'acquisition.json'
        if manifest.exists():
            if json.loads(manifest.read_text())!=declaration:raise ValueError('Identity acquisition resume differs')
        else:manifest.write_text(json.dumps(declaration,indent=2)+'\n')
        tasks=[(day,exchange,args.output,args.budget_root,sources) for day in days for exchange in EXCHANGES]
        pending=[t for t in tasks if not (args.output/t[0]/t[1]/'complete.json').exists()]
        if args.max_shards is not None:pending=pending[:args.max_shards]
        with worker_pool(args.workers,threads=1) as pool:
            for completed,result in enumerate(pool.map(capture,pending,chunksize=1),1):
                if completed%25==0 or completed==len(pending):
                    print(json.dumps(dict(completed_this_run=completed,pending_this_run=len(pending),latest=result)),flush=True)
        missing=[t for t in tasks if not (args.output/t[0]/t[1]/'complete.json').exists()]
        if missing:
            print(json.dumps(dict(status='partial',missing_shards=len(missing),total_shards=len(tasks))),flush=True)
            return
        hashes={};total=0
        from nn_meta.v7.daily_identities import query
        for day,exchange,*_ in tasks:
            path=args.output/day/exchange
            doc=verify(path,expected_identity=identity(dict(query=query(day,exchange),sources=sources)))
            hashes[str(path/'complete.json')]=sha(path/'complete.json');total+=doc['records']
        if any(sha(p)!=h for p,h in sources.items()) or sha(args.calendar)!=declaration['calendar_sha256']:
            raise ValueError('Identity capture inputs changed')
        summary=args.output/'summary';binding=dict(declaration=declaration,shards=hashes)
        if summary.exists():verify(summary,expected_identity=identity(binding));return
        with transaction(summary) as temp:
            (temp/'binding.json').write_text(json.dumps(binding,indent=2)+'\n')
            (temp/'report.json').write_text(json.dumps(dict(days=len(days),shards=len(tasks),records=total,
                research_ready=False),indent=2)+'\n')
            receipt(temp,dict(identity=identity(binding),research_ready=False))
        print(json.dumps(dict(status='complete',days=len(days),shards=len(tasks),records=total)),flush=True)


if __name__=='__main__':main()
