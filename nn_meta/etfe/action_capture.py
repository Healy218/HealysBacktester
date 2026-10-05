"""Fresh Alpaca corporate-action observations, never backdated eligibility."""
from collections import Counter
from datetime import date, datetime, timezone
import fcntl
import json
from pathlib import Path
import time
import uuid

import pandas as pd
import requests

from nn_meta.etfe.acquisition import ROOT, SYMBOLS, digest, sha, save, write_new, guard

URL = 'https://data.alpaca.markets/v1/corporate-actions'
STREAM = 'https://stream.data.alpaca.markets/v1beta1/events/corporate-actions'
SOURCES = ['nn_meta/etfe/action_capture.py', 'nn_meta/etfe/acquisition.py',
           'scripts/capture_etfe_actions.py', 'scripts/audit_etfe_actions.py',
           'docs/specs/ETFE_ACTION_EVIDENCE_20261005.md']


def inventory():
    jobs = [dict(kind='actions', params=dict(symbols=s, start='2024-01-01', end='2026-10-02',
            data_quality='all', sort='asc', limit=5)) for s in SYMBOLS]
    # Bounded route-capability probes only; stream has no symbol filter.
    for start, end in [('2024-01-18T00:00:00Z','2024-01-19T23:59:59Z'),
                       ('2026-10-01T00:00:00Z','2026-10-02T23:59:59Z')]:
        jobs.append(dict(kind='events_probe',params=dict(since=start,until=end,region='us')))
    return [dict(j,id=digest(j)) for j in jobs]


def prepare(root):
    plan = dict(schema='etfe-action-evidence-v1', jobs=inventory(),
        sources={n:sha((ROOT/n).read_bytes()) for n in SOURCES},
        limits=dict(max_requests=64,max_seconds=900,max_page_bytes=8*2**20,max_root_bytes=128*2**20),
        model_feature_admitted=False,complete_effective_date_history=False,legacy_data_inputs=[])
    plan['sha256']=digest(plan);root=Path(root);root.mkdir(parents=True,exist_ok=False);save(root/'PLAN.json',plan)
    for n in SOURCES:
        p=root/'source'/n;p.parent.mkdir(parents=True,exist_ok=True);write_new(p,(ROOT/n).read_bytes())
    return plan


def verify(root):
    root=Path(root);p=json.loads((root/'PLAN.json').read_text())
    if digest({k:v for k,v in p.items() if k!='sha256'})!=p['sha256'] or p['jobs']!=inventory():raise ValueError('Action plan drift')
    for n,h in p['sources'].items():
        if sha((ROOT/n).read_bytes())!=h or sha((root/'source'/n).read_bytes())!=h:raise ValueError('Action source drift')
    return p


def action_rows(body,item):
    if not isinstance(body,dict) or 'corporate_actions' not in body or 'next_page_token' not in body:raise ValueError('Action response schema')
    token=body['next_page_token']
    if token is not None and (not isinstance(token,str) or not token):raise ValueError('Invalid action token')
    groups=body['corporate_actions']
    if groups is None:groups={}
    if not isinstance(groups,dict):raise ValueError('Action group map required')
    for kind,rows in groups.items():
        if not isinstance(rows,list):raise ValueError('Action record list required')
        for ordinal,row in enumerate(rows):
            if not isinstance(row,dict) or not isinstance(row.get('id'),str) or not row['id']:raise ValueError('Native action identity required')
            symbols=[v for k,v in row.items() if k=='symbol' or k.endswith('_symbol')]
            if item['params']['symbols'] not in symbols:raise ValueError('Action symbol mismatch')
            process=row.get('process_date')
            if process is not None and not item['params']['start']<=date.fromisoformat(process).isoformat()<=item['params']['end']:
                raise ValueError('Action process date outside request')
            yield kind,ordinal,row


def chain(root,item,plan):
    root=Path(root);history=[];token=None;seen=set();done=False
    for i,path in enumerate(sorted((root/'jobs'/item['id']).glob('page-*.json'))):
        if done or path.name!=f'page-{i:06d}.json':raise ValueError('Broken action page chain')
        pointer=json.loads(path.read_text());attempt=root/pointer['attempt']
        if not attempt.resolve().is_relative_to(root.resolve()):raise ValueError('Unsafe receipt path')
        receipt=json.loads((attempt/'receipt.json').read_text());raw=(attempt/'body').read_bytes()
        params=dict(item['params'])
        if token is not None:params['page_token']=token
        if (sha((attempt/'receipt.json').read_bytes())!=pointer['receipt_sha256'] or sha(raw)!=receipt['body_sha256']
            or receipt['params']!=params or receipt['plan_sha256']!=plan['sha256'] or receipt['kind']!=item['kind']
            or receipt['url']!=(URL if item['kind']=='actions' else STREAM)):raise ValueError('Action receipt drift')
        if item['kind']=='actions':
            if receipt['status']!=200 or receipt['error']:raise ValueError('Unsuccessful action page committed')
            body=json.loads(raw);list(action_rows(body,item));token=body['next_page_token']
            if token is not None and token in seen:raise ValueError('Repeated action token')
            seen.add(token);done=token is None
        else:
            # A bounded probe receipt is complete as an observation, never replay coverage.
            body=None;done=True
        history.append((receipt,body,pointer['attempt']))
    return history,token,done


class HTTP:
    def __init__(self,key,secret):
        if not key or not secret:raise ValueError('Missing Alpaca data credentials')
        self.secrets=(key,secret);self.session=requests.Session()

    def get(self,kind,params,max_bytes):
        raw=bytearray();status=None;headers={};error=None;started=time.monotonic()
        try:
            with self.session.get(URL if kind=='actions' else STREAM,params=params,
                headers={'APCA-API-KEY-ID':self.secrets[0],'APCA-API-SECRET-KEY':self.secrets[1]},
                stream=True,timeout=(10,5),allow_redirects=False) as response:
                status=response.status_code
                allowed={'content-type','x-request-id','retry-after','x-ratelimit-remaining','x-ratelimit-reset'}
                headers={k.lower():v for k,v in response.headers.items() if k.lower() in allowed}
                for block in response.iter_content(4096):
                    if len(raw)+len(block)>max_bytes:error='byte_limit';break
                    raw.extend(block)
                    if time.monotonic()-started>20:error='response_time_limit';break
        except requests.RequestException:error='transport_error'
        if any(s.encode() in raw or s in json.dumps(headers) for s in self.secrets):
            return None,b'',{},'credential_echo'
        return status,bytes(raw),headers,error


def capture(root,http,*,budget=None,sleep=time.sleep,resource_guard=guard):
    root=Path(root);plan=verify(root);limit=plan['limits'];budget=min(budget or limit['max_requests'],limit['max_requests'])
    if budget<1:raise ValueError('Positive request budget required')
    started=time.monotonic();calls=0;last=0.;stop=None
    with (root/'writer.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            waits=[json.loads(p.read_text())['not_before'] for p in (root/'waits').glob('*.json')]
            if waits and max(waits)>time.time():raise RuntimeError('provider_wait_pending')
            for item in plan['jobs']:
                history,token,done=chain(root,item,plan);failures=0
                while not done:
                    if calls>=budget:raise RuntimeError('request_budget')
                    if time.monotonic()-started>=limit['max_seconds']:raise RuntimeError('time_budget')
                    resource_guard(root,limit);sleep(max(0,1-(time.monotonic()-last)))
                    params=dict(item['params'])
                    if token is not None:params['page_token']=token
                    before=datetime.now(timezone.utc).isoformat();last=time.monotonic()
                    status,raw,headers,error=http.get(item['kind'],params,limit['max_page_bytes']);calls+=1
                    attempt=root/'attempts'/uuid.uuid4().hex;attempt.mkdir(parents=True)
                    write_new(attempt/'body',raw)
                    receipt=dict(plan_sha256=plan['sha256'],kind=item['kind'],url=URL if item['kind']=='actions' else STREAM,
                        params=params,status=status,error=error,headers=headers,observed_at=before,received_at=datetime.now(timezone.utc).isoformat(),body_sha256=sha(raw))
                    save(attempt/'receipt.json',receipt)
                    retry=(error=='transport_error' or status==429 or (status is not None and status>=500)) and item['kind']=='actions'
                    if retry:
                        failures+=1
                        if failures>=5:raise RuntimeError('retries_exhausted')
                        delay=2**(failures-1)
                    elif item['kind']=='actions' and (status!=200 or error):raise RuntimeError(f'action_request_failed:{status}:{error}')
                    else:
                        if item['kind']=='actions':list(action_rows(json.loads(raw),item))
                        folder=root/'jobs'/item['id'];folder.mkdir(parents=True,exist_ok=True)
                        # Check a repeated token before publishing a page.
                        if item['kind']=='actions' and json.loads(raw)['next_page_token'] in {b['next_page_token'] for _,b,_ in history if b['next_page_token'] is not None}:
                            raise ValueError('Repeated action token')
                        save(folder/f'page-{len(history):06d}.json',dict(attempt=str(attempt.relative_to(root)),receipt_sha256=sha((attempt/'receipt.json').read_bytes())))
                        history,token,done=chain(root,item,plan);failures=0;delay=0
                    if status==429 or headers.get('x-ratelimit-remaining')=='0':
                        delay=max(delay,1,float(headers.get('x-ratelimit-reset',time.time()+60))-time.time())
                    if headers.get('retry-after'):
                        try:delay=max(delay,float(headers['retry-after']))
                        except ValueError:
                            from email.utils import parsedate_to_datetime
                            delay=max(delay,parsedate_to_datetime(headers['retry-after']).timestamp()-time.time())
                    if delay:
                        folder=root/'waits';folder.mkdir(exist_ok=True);save(folder/(uuid.uuid4().hex+'.json'),dict(not_before=time.time()+delay))
                        if delay>60:raise RuntimeError('provider_wait_required')
                        sleep(delay)
        except (ValueError,RuntimeError) as exc:stop=str(exc)
        complete=all(chain(root,j,plan)[2] for j in plan['jobs'])
        result=dict(plan_sha256=plan['sha256'],capture_complete=complete,requests=calls,stop_reason=stop,elapsed_seconds=time.monotonic()-started)
        (root/'runs').mkdir(exist_ok=True);save(root/'runs'/(uuid.uuid4().hex+'.json'),result)
    return result


def normalize(root):
    root=Path(root);plan=verify(root);records=[];jobs=[]
    if (root/'NORMALIZED.json').exists():raise FileExistsError('Normalization already committed')
    for item in plan['jobs']:
        pages,_,done=chain(root,item,plan)
        if not done:raise ValueError('Finish all action requests/probes')
        count=0
        for page,(receipt,body,attempt) in enumerate(pages):
            if item['kind']!='actions':continue
            for group,ordinal,row in action_rows(body,item):
                count+=1
                records.append(dict(occurrence_id=digest([item['id'],page,group,ordinal]),query_symbol=item['params']['symbols'],
                    action_type=group,native_id=str(row['id']),process_date=row.get('process_date'),
                    effective_date=row.get('ex_date') or row.get('effective_date'),
                    observed_at=receipt['received_at'],historical_available_at_ns=-1,model_feature_admitted=False,
                    job_id=item['id'],page=page,group_ordinal=ordinal,attempt=attempt,body_sha256=receipt['body_sha256'],
                    raw_json=json.dumps(row,sort_keys=True,separators=(',',':'),allow_nan=False)))
        jobs.append(dict(id=item['id'],kind=item['kind'],pages=len(pages),rows=count,statuses=[r['status'] for r,_,_ in pages]))
    frame=pd.DataFrame(records)
    if frame.empty:raise ValueError('No action observations; retain capture without asserting normalized evidence')
    path=root/'ACTIONS.parquet'
    # Atomic publication with the same immutable convention as raw evidence.
    raw=frame.to_parquet(index=False,compression='zstd')
    if path.exists():
        if sha(path.read_bytes())!=sha(raw):raise ValueError('Orphan normalized payload mismatch')
    else:write_new(path,raw)
    result=dict(plan_sha256=plan['sha256'],rows=len(frame),jobs=jobs,rows_by_symbol=dict(Counter(frame.query_symbol)),
        rows_by_type=dict(Counter(frame.action_type)),duplicate_native_ids=int(frame.duplicated(['query_symbol','native_id']).sum()),
        effective_date_min=min(frame.effective_date.dropna(),default=None),effective_date_max=max(frame.effective_date.dropna(),default=None),
        files=[dict(path=path.name,sha256=sha(path.read_bytes()))],historical_availability_verified=False,
        complete_effective_date_history=False,model_feature_admitted=False)
    save(root/'NORMALIZED.json',result);return result
