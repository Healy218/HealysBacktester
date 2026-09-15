"""Capture complete dated stock security masters; identity precedes PIT ranking."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import gzip
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode
import uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    import requests
    from dotenv import load_dotenv
    from nn_meta.v7.storage import transaction,receipt,verify,identity
    from scripts.download_v7_data import quota_update,tree_bytes,TASK_RESERVATION
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--calendar',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--budget-root',type=Path,required=True)
    ap.add_argument('--limit',type=int)
    args=ap.parse_args()
    if not args.output.resolve().is_relative_to(args.budget_root.resolve()):raise ValueError('Shared quota required')
    calendar=json.loads(args.calendar.read_text());month_ends={}
    for r in calendar['sessions']:month_ends[r['date'][:7]]=r['date']
    # Include last partial month as identity evidence, never a membership selection date.
    days=list(month_ends.values())
    if args.limit:days=days[:args.limit]
    load_dotenv(ROOT/'.env');session=requests.Session()
    for day in days:
        query={'market':'stocks','date':day,'active':'true','limit':1000,'sort':'ticker','order':'asc'}
        dest=args.output/day;fingerprint=identity(query)
        if dest.exists():verify(dest,expected_identity=fingerprint);continue
        key=uuid.uuid4().hex;quota_update(args.budget_root,reserve=key);used=0
        try:
            with transaction(dest) as temp:
                url='https://api.massive.com/v3/reference/tickers';params=query;seen=set();count=0
                for page in range(100):
                    if url in seen:raise ValueError('Security master pagination loop')
                    seen.add(url)
                    for attempt in range(5):
                        try:r=session.get(url,params=params,headers={'Authorization':'Bearer '+os.environ['MASSIVE_API_KEY']},timeout=30,allow_redirects=False)
                        except requests.RequestException:raise RuntimeError('Security master transport failed') from None
                        if r.status_code not in (429,500,502,503,504):break
                        time.sleep(2**attempt)
                    if r.status_code!=200:raise RuntimeError(f'Security master HTTP {r.status_code}')
                    body=r.json()
                    if body.get('status')!='OK' or not isinstance(body.get('results'),list):raise ValueError('Invalid master page')
                    # Do not store provider next_url: it can embed credentials.
                    payload=json.dumps({'results':body['results'],'status':body['status']},sort_keys=True).encode()
                    compressed=gzip.compress(payload,mtime=0)
                    if used+len(compressed)>TASK_RESERVATION//2:raise ValueError('Master capture exceeds reservation')
                    (temp/f'page-{page:03d}.json.gz').write_bytes(compressed);used+=len(compressed);count+=len(body['results'])
                    if not body.get('next_url'):break
                    parsed=urlsplit(body['next_url'])
                    if parsed.scheme!='https' or parsed.netloc!='api.massive.com' or parsed.path!='/v3/reference/tickers':raise ValueError('Master pagination changed origin')
                    url=urlunsplit((parsed.scheme,parsed.netloc,parsed.path,urlencode([(k,v) for k,v in parse_qsl(parsed.query) if k.lower()!='apikey']),''));params=None
                else:raise ValueError('Security master page budget exhausted')
                receipt(temp,{'identity':fingerprint,'query':query,'records':count,'pages':page+1,
                              'retrieved_at':datetime.now(timezone.utc).isoformat(),
                              'purpose':'dated listing/security identity only; not publication-safe fundamentals'})
                used=tree_bytes(temp)
            print(json.dumps({'date':day,'records':count,'pages':page+1}),flush=True)
        finally:
            if not dest.exists():used=sum(tree_bytes(p) for p in dest.parent.glob(dest.name+'.partial-*'))
            quota_update(args.budget_root,finish=(key,used))


if __name__=='__main__':main()
