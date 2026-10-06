"""Full-window, source-bound announcement snapshots for Alpaca's dated announcement route."""
import argparse
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import time
import requests
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nn_meta.etfe.acquisition import digest,sha,save,write_new,guard
from scripts.expand_etfe_alpaca import credentials
URL='https://paper-api.alpaca.markets/v2/corporate_actions/announcements'


def inventory():
    jobs=[];start=date(2024,1,1);end=date(2026,10,2)
    while start<=end:
        stop=min(start+timedelta(days=88),end)
        for symbol in ('SPY','QQQ','VOO'):
            jobs.append(dict(symbol=symbol,ca_types='Dividend,Merger,Spinoff,Split,Reorg',
                since=str(start),until=str(stop),date_type='ex_date'))
        start=stop+timedelta(days=1)
    return jobs


def prepare(root):
    source=Path(__file__).read_bytes()
    plan=dict(schema='etfe-full-dated-announcements-v1',url=URL,queries=inventory(),
        sources={str(Path(__file__).relative_to(ROOT)):sha(source)},max_requests=36,max_page_bytes=2**20,
        purpose='All supported types by ex-date over the full fixed research window; current declaration dates are not revision history',
        effective_and_available_history_admitted=False)
    plan['sha256']=digest(plan);root.mkdir(parents=True,exist_ok=False);save(root/'PLAN.json',plan);write_new(root/'SOURCE.py',source)
    return plan


def run(root):
    p=json.loads((root/'PLAN.json').read_text())
    if p['sha256']!=digest({k:v for k,v in p.items() if k!='sha256'}) or sha((root/'SOURCE.py').read_bytes())!=sha(Path(__file__).read_bytes()):raise ValueError('Source drift')
    if p['queries']!=inventory() or p['url']!=URL:raise ValueError('Scope drift')
    key,secret=credentials()['metadata'];summary=[]
    for n,params in enumerate(p['queries']):
        target=root/f'{n:02d}'
        if target.exists():
            if not (target/'receipt.json').exists():raise ValueError('Reserved incomplete request; inspect before successor')
            receipt=json.loads((target/'receipt.json').read_text())
            raw=(target/'body').read_bytes()
            if sha(raw)!=receipt['body_sha256']:raise ValueError('Body drift')
        else:
            guard(root,dict(max_page_bytes=p['max_page_bytes'],max_root_bytes=16*2**20))
            target.mkdir();started=datetime.now(timezone.utc).isoformat();clock=time.monotonic();raw=bytearray();status=None;error=None
            try:
                with requests.get(URL,params=params,headers={'APCA-API-KEY-ID':key,'APCA-API-SECRET-KEY':secret},timeout=(10,10),stream=True,allow_redirects=False) as response:
                    status=response.status_code
                    for block in response.iter_content(4096):
                        if len(raw)+len(block)>p['max_page_bytes']:error='byte_limit';break
                        raw.extend(block)
                        if time.monotonic()-clock>30:error='response_time_limit';break
            except requests.RequestException:error='transport_error'
            raw=bytes(raw)
            if any(s.encode() in raw for s in (key,secret)):raw=b'';error='credential_echo'
            write_new(target/'body',raw)
            receipt=dict(plan_sha256=p['sha256'],url=URL,params=params,status=status,error=error,body_sha256=sha(raw),
                observed_at=started,received_at=datetime.now(timezone.utc).isoformat())
            save(target/'receipt.json',receipt);time.sleep(1)
        try:body=json.loads(raw)
        except ValueError:body=None
        records=body if isinstance(body,list) else []
        summary.append(dict(params=params,status=receipt['status'],error=receipt['error'],rows=len(records),
            declaration_dates=[r.get('declaration_date') for r in records],body_sha256=receipt['body_sha256']))
        if receipt['error'] or receipt['status']==429 or (receipt['status'] or 0)>=500:break
    result=dict(plan_sha256=p['sha256'],controls=summary,all_controls_observed=len(summary)==len(p['queries']),
        historical_availability_admitted=False)
    if not (root/'RESULT.json').exists():save(root/'RESULT.json',result)
    elif json.loads((root/'RESULT.json').read_text())!=result:raise ValueError('Result changed')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['prepare','run']);p.add_argument('--root',type=Path,required=True);a=p.parse_args();root=a.root.resolve()
    if root.parent!=ROOT/'nn_meta/data_cache_etfe' or not root.name.startswith('alpaca-fresh-full-announcements-'):p.error('Isolated fresh root required')
    print(json.dumps(prepare(root) if a.command=='prepare' else run(root),indent=2))
