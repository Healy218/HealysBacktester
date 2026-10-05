"""Action process-date tail and bounded mutation inspection; no input admission."""
from collections import Counter
from datetime import datetime,timezone
import fcntl,json,time,uuid
from pathlib import Path
import pandas as pd
from nn_meta.etfe.acquisition import ROOT,SYMBOLS,sha,digest,save,write_new,guard
from nn_meta.etfe.action_capture import HTTP,URL,chain,action_rows,verify as verify_parent

PARENT=ROOT/'nn_meta/data_cache_etfe/alpaca-fresh-actions-20261005-r0'
SOURCES=['nn_meta/etfe/action_evidence.py','scripts/extend_etfe_action_evidence.py','scripts/audit_etfe_action_tail.py',
         'docs/specs/ETFE_ACTION_TAIL_20261005.md','nn_meta/etfe/action_capture.py','nn_meta/etfe/acquisition.py']


def inventory():
    jobs=[dict(kind='actions',params=dict(symbols=s,start='2026-10-03',end='2026-12-31',data_quality='all',sort='asc',limit=5)) for s in SYMBOLS]
    return [dict(j,id=digest(j)) for j in jobs]


def prepare(root):
    parent=verify_parent(PARENT)
    # Bind all committed parent receipts and raw pages, including bounded probes.
    paths=[p for p in PARENT.rglob('*') if p.is_file() and p.name!='writer.lock']
    plan=dict(schema='etfe-action-tail-v1',parent_sha256=parent['sha256'],jobs=inventory(),
        inputs={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in paths},sources={n:sha((ROOT/n).read_bytes()) for n in SOURCES},
        limits=dict(max_requests=32,max_seconds=900,max_page_bytes=8*2**20,max_root_bytes=128*2**20),
        price_end_unchanged='2026-10-02',model_feature_admitted=False)
    plan['sha256']=digest(plan);root=Path(root);root.mkdir(parents=True,exist_ok=False);save(root/'PLAN.json',plan)
    for n in SOURCES:
        p=root/'source'/n;p.parent.mkdir(parents=True,exist_ok=True);write_new(p,(ROOT/n).read_bytes())
    return plan


def verify(root):
    root=Path(root);p=json.loads((root/'PLAN.json').read_text())
    if digest({k:v for k,v in p.items() if k!='sha256'})!=p['sha256'] or p['jobs']!=inventory():raise ValueError('Tail plan drift')
    for n,h in p['inputs'].items():
        if sha((ROOT/n).read_bytes())!=h:raise ValueError('Parent evidence drift')
    for n,h in p['sources'].items():
        if sha((ROOT/n).read_bytes())!=h or sha((root/'source'/n).read_bytes())!=h:raise ValueError('Tail source drift')
    return p


def run(root,http,*,budget=32,sleep=time.sleep,resource_guard=guard):
    root=Path(root);plan=verify(root);started=time.monotonic();calls=0;last=0.;stop=None
    if budget<1:raise ValueError('Positive request budget required')
    with (root/'writer.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            waits=[json.loads(p.read_text())['not_before'] for p in root.glob('wait-*.json')]
            if waits and max(waits)>time.time():raise RuntimeError('provider_wait_pending')
            for item in plan['jobs']:
                history,token,done=chain(root,item,plan)
                while not done:
                    if calls>=min(budget,plan['limits']['max_requests']):raise RuntimeError('request_budget')
                    if time.monotonic()-started>=plan['limits']['max_seconds']:raise RuntimeError('time_budget')
                    resource_guard(root,plan['limits']);sleep(max(0,1-(time.monotonic()-last)))
                    params=dict(item['params'])
                    if token is not None:params['page_token']=token
                    before=datetime.now(timezone.utc).isoformat();last=time.monotonic()
                    status,raw,headers,error=http.get('actions',params,plan['limits']['max_page_bytes']);calls+=1
                    folder=root/'attempts'/uuid.uuid4().hex;folder.mkdir(parents=True);write_new(folder/'body',raw)
                    receipt=dict(plan_sha256=plan['sha256'],kind='actions',url=URL,params=params,status=status,error=error,
                        headers=headers,observed_at=before,received_at=datetime.now(timezone.utc).isoformat(),body_sha256=sha(raw))
                    save(folder/'receipt.json',receipt)
                    # No automatic retries in this small extension; preserve failure for resume.
                    if status==429 or headers.get('x-ratelimit-remaining')=='0' or headers.get('retry-after'):
                        delay=max(60 if status==429 else 1,float(headers.get('x-ratelimit-reset',time.time()))-time.time())
                        if headers.get('retry-after'):
                            try:delay=max(delay,float(headers['retry-after']))
                            except ValueError:
                                from email.utils import parsedate_to_datetime
                                delay=max(delay,parsedate_to_datetime(headers['retry-after']).timestamp()-time.time())
                        save(root/('wait-'+uuid.uuid4().hex+'.json'),dict(not_before=time.time()+delay))
                        raise RuntimeError('provider_wait_required')
                    if status!=200 or error:raise RuntimeError(f'action_request_failed:{status}:{error}')
                    body=json.loads(raw);list(action_rows(body,item))
                    if body['next_page_token'] in {b['next_page_token'] for _,b,_ in history if b['next_page_token'] is not None}:raise ValueError('Repeated action token')
                    dest=root/'jobs'/item['id'];dest.mkdir(parents=True,exist_ok=True)
                    save(dest/f'page-{len(history):06d}.json',dict(attempt=str(folder.relative_to(root)),receipt_sha256=sha((folder/'receipt.json').read_bytes())))
                    history,token,done=chain(root,item,plan)
        except (ValueError,RuntimeError) as exc:stop=str(exc)
        report=dict(plan_sha256=plan['sha256'],requests=calls,capture_complete=all(chain(root,j,plan)[2] for j in plan['jobs']),stop_reason=stop,elapsed_seconds=time.monotonic()-started)
        save(root/('run-'+uuid.uuid4().hex+'.json'),report)
    return report


def parse_sse(raw):
    """Consume complete SSE blocks only. A capped trailing block remains unknown."""
    # A UTF-8 codepoint may itself be truncated by the byte cap; decode full blocks.
    raw=raw.replace(b'\r\n',b'\n');blocks=raw.split(b'\n\n');events=[]
    for ordinal,block in enumerate(blocks[:-1]):
        data=[]
        for line in block.decode('utf-8').split('\n'):
            if line.startswith('data:'):data.append(line[5:].removeprefix(' '))
        if not data:continue
        event=json.loads('\n'.join(data))
        if (not isinstance(event,dict) or not isinstance(event.get('ca'),dict) or not event.get('event_id')
            or event.get('action') not in ('insert','update','delete')):raise ValueError('Mutation schema drift')
        at=pd.Timestamp(event.get('at'))
        if pd.isna(at) or at.tzinfo is None:raise ValueError('Mutation timestamp required')
        events.append((ordinal,event))
    return events,len(blocks[-1])


def inspect(root):
    root=Path(root);plan=verify(root);parent=verify_parent(PARENT);tail=[];pages=0
    for item in plan['jobs']:
        history,_,done=chain(root,item,plan)
        if not done:raise ValueError('Tail capture incomplete')
        pages+=len(history)
        for page,(receipt,body,attempt) in enumerate(history):
            for kind,ordinal,row in action_rows(body,item):
                tail.append(dict(symbol=item['params']['symbols'],native_id=row['id'],kind=kind,process_date=row.get('process_date'),
                    effective_date=row.get('ex_date') or row.get('effective_date'),job_id=item['id'],page=page,group_ordinal=ordinal,
                    body_sha256=receipt['body_sha256'],attempt=attempt,raw=row,historical_available_at_ns=-1,model_feature_admitted=False))
    original=pd.read_parquet(PARENT/'ACTIONS.parquet');original_ids=set(original.native_id);probes=[];matched=[]
    for item in parent['jobs']:
        if item['kind']!='events_probe':continue
        history,_,done=chain(PARENT,item,parent);assert done and len(history)==1
        receipt,_,attempt=history[0];raw=(PARENT/attempt/'body').read_bytes()
        if receipt['status']!=200 or not receipt['headers'].get('content-type','').startswith('text/event-stream'):
            probes.append(dict(attempt=attempt,status=receipt['status'],events=None,parse_status='not_event_stream'));continue
        events,trailing=parse_sse(raw);timestamps=[pd.Timestamp(e['at']) for _,e in events]
        assert all(pd.Timestamp(item['params']['since'])<=t<=pd.Timestamp(item['params']['until']) for t in timestamps)
        ids=[e['event_id'] for _,e in events]
        probes.append(dict(attempt=attempt,events=len(events),trailing_bytes=trailing,capture_error=receipt['error'],
            first_event_at=str(min(timestamps)) if timestamps else None,last_event_at=str(max(timestamps)) if timestamps else None,
            duplicate_event_ids=len(ids)-len(set(ids)),replay_coverage_verified=False))
        for ordinal,e in events:
            symbols={v for k,v in e['ca'].items() if k=='symbol' or k.endswith('_symbol')}
            if not symbols.intersection(SYMBOLS):continue
            matched.append(dict(block_ordinal=ordinal,source_attempt=attempt,source_body_sha256=sha(raw),event=e,
                emitted_at_ns=pd.Timestamp(e['at']).value,original_announcement_time_verified=False,model_feature_admitted=False))
    matched_ids={e['event']['ca']['id'] for e in matched};tail_ids={e['native_id'] for e in tail}
    payload=dict(plan_sha256=plan['sha256'],tail_occurrences=tail,etf_mutations=matched)
    save(root/'OBSERVATIONS.json',payload)
    window=lambda day:day is not None and '2024-01-01'<=day<='2026-10-02'
    result=dict(plan_sha256=plan['sha256'],tail_pages=pages,tail_rows=len(tail),tail_rows_by_symbol=dict(Counter(r['symbol'] for r in tail)),
        tail_rows_effective_in_price_window=sum(window(r['effective_date']) for r in tail),
        original_rows=len(original),original_rows_effective_in_price_window=sum(window(d) for d in original.effective_date),
        tail_native_ids_not_in_original=len(tail_ids-original_ids),etf_mutations=len(matched),unique_etf_mutation_actions=len(matched_ids),
        mutation_action_ids_matching_tail=sorted(matched_ids&tail_ids),probes=probes,
        files=[dict(path='OBSERVATIONS.json',sha256=sha((root/'OBSERVATIONS.json').read_bytes()))],
        historical_availability_verified=False,complete_effective_date_history=False,model_feature_admitted=False)
    save(root/'INSPECTION.json',result);return result
