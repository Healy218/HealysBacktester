"""Bounded inclusive-timestamp replay with explicit historical-coverage limits."""
from datetime import datetime, timezone
from decimal import Decimal
import fcntl,json,time,uuid
from pathlib import Path
import pandas as pd
from nn_meta.etfe.acquisition import ROOT,sha,digest,save,write_new,guard
from nn_meta.etfe.action_capture import HTTP,STREAM
from nn_meta.etfe.action_evidence import parse_sse,PARENT

TAIL=ROOT/'nn_meta/data_cache_etfe/alpaca-fresh-actions-tail-20261005-r0'
DAYS=['2024-03-14','2025-03-20','2026-03-19','2026-09-17']
SOURCES=['nn_meta/etfe/action_replay_v2.py','nn_meta/etfe/action_capture.py','nn_meta/etfe/action_evidence.py',
         'nn_meta/etfe/acquisition.py','scripts/replay_etfe_actions_v2.py','scripts/audit_etfe_action_replay_v2.py',
         'docs/specs/ETFE_ACTION_REPLAY_V2_20261005.md']


def overlap_cursor(stamp):
    return pd.Timestamp(stamp).floor('s').isoformat()


def prepare(root):
    inputs=[ROOT/'nn_meta/data_cache_etfe/alpaca-fresh-action-replay-20261005-r0/REJECTION.json',PARENT/'ACTIONS.parquet',PARENT/'INDEPENDENT_AUDIT.json',TAIL/'OBSERVATIONS.json',TAIL/'INDEPENDENT_AUDIT.json']
    jobs=[dict(day=d,start=d+'T00:00:00Z',end=d+'T23:59:59.999999999Z') for d in DAYS]
    plan=dict(schema='etfe-action-replay-v2',jobs=jobs,sources={n:sha((ROOT/n).read_bytes()) for n in SOURCES},
        inputs={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in inputs},
        limits=dict(max_requests=96,max_seconds=900,max_page_bytes=2*2**20,max_root_bytes=192*2**20,max_day_bytes=32*2**20,max_total_bytes=128*2**20),
        type_filter='cash_dividend_corporateaction_event',model_feature_admitted=False,retention_verified=False)
    plan['sha256']=digest(plan);root=Path(root);root.mkdir(parents=True,exist_ok=False);save(root/'PLAN.json',plan)
    for n in SOURCES:
        p=root/'source'/n;p.parent.mkdir(parents=True,exist_ok=True);write_new(p,(ROOT/n).read_bytes())
    return plan


def verify(root):
    root=Path(root);p=json.loads((root/'PLAN.json').read_text())
    if digest({k:v for k,v in p.items() if k!='sha256'})!=p['sha256']:raise ValueError('Replay plan drift')
    for n,h in p['sources'].items():
        if sha((ROOT/n).read_bytes())!=h or sha((root/'source'/n).read_bytes())!=h:raise ValueError('Replay source drift')
    for n,h in p['inputs'].items():
        if sha((ROOT/n).read_bytes())!=h:raise ValueError('Replay input drift')
    return p


def parse_page(raw,receipt,job):
    if receipt['status']!=200 or not receipt['headers'].get('content-type','').startswith('text/event-stream'):raise ValueError('Not an SSE response')
    if receipt['error'] not in (None,'byte_limit','response_time_limit'):raise ValueError('Unusable replay transport')
    events,trailing=parse_sse(raw);previous=None;ids={}
    for _,e in events:
        at=pd.Timestamp(e['at'])
        if not pd.Timestamp(receipt['params']['since'])<=at<=pd.Timestamp(job['end']):raise ValueError('Replay timestamp outside interval')
        if previous is not None and at<previous:raise ValueError('Replay clock went backwards')
        if e.get('region')!='us' or e.get('event_type')!='cash_dividend_corporateaction_event':raise ValueError('Replay filter mismatch')
        if not isinstance(e['event_id'],str) or not isinstance(e['ca'].get('id'),str):raise ValueError('Replay identity missing')
        h=digest(e)
        if e['event_id'] in ids and ids[e['event_id']]!=h:raise ValueError('Conflicting replay event ID')
        ids[e['event_id']]=h;previous=at
    eof=receipt['error'] is None
    if eof and trailing:raise ValueError('Incomplete SSE block at EOF')
    if not eof and not events:raise ValueError('Capped replay has no complete cursor')
    return events,eof,(events[-1][1]['at'] if events else None),trailing


def committed(root,job,plan):
    root=Path(root);cursor=job['start'];seen={};done=False;pages=[];total=0
    for index,path in enumerate(sorted((root/'days'/job['day']).glob('page-*.json'))):
        if done or path.name!=f'page-{index:06d}.json':raise ValueError('Broken replay page sequence')
        pointer=json.loads(path.read_text());folder=root/pointer['attempt']
        if not folder.resolve().is_relative_to(root.resolve()):raise ValueError('Unsafe replay attempt')
        rec=json.loads((folder/'receipt.json').read_text());raw=(folder/'body').read_bytes()
        expected=dict(since=cursor,until=job['end'],region='us',type=plan['type_filter'])
        if (sha((folder/'receipt.json').read_bytes())!=pointer['receipt_sha256'] or sha(raw)!=rec['body_sha256']
            or rec['params']!=expected or rec['plan_sha256']!=plan['sha256'] or rec['url']!=STREAM):raise ValueError('Replay receipt drift')
        events,eof,last,trailing=parse_page(raw,rec,job);new=0
        for _,e in events:
            h=digest(e)
            if e['event_id'] in seen and seen[e['event_id']]!=h:raise ValueError('Conflicting replay event ID')
            if e['event_id'] not in seen:new+=1
            seen[e['event_id']]=h
        if not eof and (pd.Timestamp(last)<pd.Timestamp(cursor) or (index>0 and new==0)):raise ValueError('Replay cursor made no progress')
        done=eof;cursor=overlap_cursor(last) if not eof else cursor;total+=len(raw)
        pages.append(dict(receipt=rec,attempt=pointer['attempt'],events=events,trailing=trailing,new_events=new,bytes=len(raw)))
    return pages,cursor,done,total


def run(root,http,*,budget=96,sleep=time.sleep,resource_guard=guard):
    root=Path(root);plan=verify(root);started=time.monotonic();calls=0;last=0.;stop=None
    if budget<1:raise ValueError('Positive request budget required')
    with (root/'writer.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            waits=[json.loads(p.read_text())['not_before'] for p in root.glob('wait-*.json')]
            if waits and max(waits)>time.time():raise RuntimeError('provider_wait_pending')
            for job in plan['jobs']:
                pages,cursor,done,day_bytes=committed(root,job,plan)
                while not done:
                    if calls>=min(budget,plan['limits']['max_requests']):raise RuntimeError('request_budget')
                    if time.monotonic()-started>=plan['limits']['max_seconds']:raise RuntimeError('time_budget')
                    total=sum(p.stat().st_size for p in root.glob('attempts/*/body'))
                    # Include failed/orphan attempts in both budgets.
                    day_bytes=sum((p.parent/'body').stat().st_size for p in root.glob('attempts/*/receipt.json') if json.loads(p.read_text())['day']==job['day'])
                    if day_bytes+plan['limits']['max_page_bytes']>plan['limits']['max_day_bytes']:raise RuntimeError('day_byte_budget')
                    if total+plan['limits']['max_page_bytes']>plan['limits']['max_total_bytes']:raise RuntimeError('total_byte_budget')
                    resource_guard(root,plan['limits']);sleep(max(0,1-(time.monotonic()-last)))
                    params=dict(since=cursor,until=job['end'],region='us',type=plan['type_filter']);before=datetime.now(timezone.utc).isoformat();last=time.monotonic()
                    status,raw,headers,error=http.get('events_probe',params,plan['limits']['max_page_bytes']);calls+=1
                    folder=root/'attempts'/uuid.uuid4().hex;folder.mkdir(parents=True);write_new(folder/'body',raw)
                    rec=dict(plan_sha256=plan['sha256'],url=STREAM,day=job['day'],params=params,status=status,error=error,headers=headers,
                        observed_at=before,received_at=datetime.now(timezone.utc).isoformat(),body_sha256=sha(raw));save(folder/'receipt.json',rec)
                    if status==429 or headers.get('x-ratelimit-remaining')=='0' or headers.get('retry-after'):
                        delay=max(60 if status==429 else 1,float(headers.get('x-ratelimit-reset',time.time()))-time.time())
                        if headers.get('retry-after'):
                            try:delay=max(delay,float(headers['retry-after']))
                            except ValueError:
                                from email.utils import parsedate_to_datetime
                                delay=max(delay,parsedate_to_datetime(headers['retry-after']).timestamp()-time.time())
                        save(root/('wait-'+uuid.uuid4().hex+'.json'),dict(not_before=time.time()+delay));raise RuntimeError('provider_wait_required')
                    events,eof,end,_=parse_page(raw,rec,job)
                    known={e['event_id']:digest(e) for p in pages for _,e in p['events']}
                    for _,e in events:
                        if e['event_id'] in known and known[e['event_id']]!=digest(e):raise ValueError('Conflicting replay event ID')
                    if not eof and (pd.Timestamp(end)<pd.Timestamp(cursor) or (pages and not any(e['event_id'] not in known for _,e in events))):raise ValueError('Replay cursor made no progress')
                    dest=root/'days'/job['day'];dest.mkdir(parents=True,exist_ok=True)
                    save(dest/f'page-{len(pages):06d}.json',dict(attempt=str(folder.relative_to(root)),receipt_sha256=sha((folder/'receipt.json').read_bytes())))
                    pages,cursor,done,day_bytes=committed(root,job,plan)
        except (RuntimeError,ValueError) as exc:stop=str(exc)
        result=dict(plan_sha256=plan['sha256'],requests=calls,stop_reason=stop,transport_complete=all(committed(root,j,plan)[2] for j in plan['jobs']),elapsed_seconds=time.monotonic()-started)
        save(root/('run-'+uuid.uuid4().hex+'.json'),result)
    return result


def native_actions():
    rows=[json.loads(v) for v in pd.read_parquet(PARENT/'ACTIONS.parquet').raw_json]
    rows += [r['raw'] for r in json.loads((TAIL/'OBSERVATIONS.json').read_text())['tail_occurrences']]
    if len({r['id'] for r in rows})!=len(rows):raise ValueError('Ambiguous native action inventory')
    return rows


def reconcile(root):
    root=Path(root);plan=verify(root);summaries=[];etf=[];all_seen={};duplicates=0
    for job in plan['jobs']:
        pages,_,done,nbytes=committed(root,job,plan)
        if not done:raise ValueError('Replay transport incomplete')
        occurrences=0;unique=set()
        for page,p in enumerate(pages):
            for block,e in p['events']:
                occurrences+=1;unique.add(e['event_id']);duplicates+=int(e['event_id'] in all_seen)
                if e['event_id'] in all_seen and all_seen[e['event_id']]!=digest(e):raise ValueError('Conflicting replay event ID')
                all_seen[e['event_id']]=digest(e)
                if e['ca'].get('symbol') in ('SPY','QQQ','VOO'):
                    etf.append(dict(day=job['day'],page=page,block_ordinal=block,attempt=p['attempt'],body_sha256=p['receipt']['body_sha256'],event=e))
        summaries.append(dict(day=job['day'],pages=len(pages),bytes=nbytes,event_occurrences=occurrences,unique_events=len(unique),transport_eof=True,history_coverage_verified=False))
    witnesses=[]
    for action in native_actions():
        events={r['event']['event_id']:r['event'] for r in etf if r['event']['ca']['id']==action['id']}
        ex_open=pd.Timestamp(action['ex_date']+' 09:30',tz='America/New_York')
        before=[e for e in events.values() if pd.Timestamp(e['at'])<ex_open]
        matching=[e for e in before if e['action']!='delete' and all(e['ca'].get(k)==action.get(k) for k in ('symbol','ex_date'))
                  and Decimal(str(e['ca'].get('rate')))==Decimal(str(action.get('rate')))]
        witnesses.append(dict(native_id=action['id'],symbol=action['symbol'],ex_date=action['ex_date'],mutations=len(events),
            pre_effective_mutations=len(before),matching_pre_effective_mutations=len(matching),
            first_matching_emission=min((e['at'] for e in matching),key=pd.Timestamp,default=None),
            original_publication_verified=False,latest_asof_version_verified=False,model_feature_admitted=False))
    save(root/'ETF_MUTATIONS.json',dict(plan_sha256=plan['sha256'],occurrences=etf))
    result=dict(plan_sha256=plan['sha256'],days=summaries,total_unique_events=len(all_seen),overlap_occurrences=duplicates,
        etf_occurrences=len(etf),etf_unique_events=len({r['event']['event_id'] for r in etf}),action_witnesses=witnesses,
        actions_with_pre_effective_witness=sum(w['matching_pre_effective_mutations']>0 for w in witnesses),
        files=[dict(path='ETF_MUTATIONS.json',sha256=sha((root/'ETF_MUTATIONS.json').read_bytes()))],
        transport_complete=True,retention_verified=False,full_history_complete=False,model_feature_admitted=False)
    save(root/'RECONCILED.json',result);return result
