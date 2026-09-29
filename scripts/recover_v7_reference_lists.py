#!/usr/bin/env python3
"""Capture both exact alternate-list queries for every unresolved reference pair."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import threading
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
LOCAL=threading.local()
MAX_BODY=1024**2


def fetch(item):
    import requests
    from options.data.provider import parse_occ_symbol
    c,d,original,expired=item
    root,expiry,right,strike=parse_occ_symbol(c)
    query=dict(path='/v3/reference/options/contracts',params=dict(underlying_ticker=root,
        expiration_date=expiry.isoformat(),strike_price=strike,contract_type='call' if right=='C' else 'put',
        as_of=d,expired=expired,limit=1000))
    if not hasattr(LOCAL,'session'):
        LOCAL.session=requests.Session()
        LOCAL.session.headers['Authorization']='Bearer '+os.environ['MASSIVE_API_KEY']
    for attempt in range(5):
        try:
            with LOCAL.session.get('https://api.massive.com'+query['path'],params=query['params'],
                                   timeout=30,allow_redirects=False,stream=True) as response:
                if response.status_code in (429,500,502,503,504):
                    time.sleep(min(2**attempt,8));continue
                if response.status_code!=200:raise ValueError('Alternate reference HTTP '+str(response.status_code))
                raw=bytearray()
                for chunk in response.iter_content(65536):
                    raw.extend(chunk)
                    if len(raw)>MAX_BODY:raise ValueError('Alternate reference body bound exceeded')
        except requests.RequestException:
            if attempt==4:raise RuntimeError('Alternate reference transport failed') from None
            time.sleep(min(2**attempt,8));continue
        body=json.loads(raw)
        if body.get('status')!='OK' or body.get('next_url') or not isinstance(body.get('results',[]),list):
            raise ValueError('Alternate reference list is incomplete')
        matched=[r for r in body.get('results',[]) if r.get('ticker')=='O:'+c]
        metadata=dict(query=query,missing_row_receipt_sha256=original,http_status=200,
                      retrieved_at=datetime.now(timezone.utc).isoformat(),pagination_complete=True,
                      exact_matches=len(matched),response_sha256=hashlib.sha256(raw).hexdigest())
        return c,d,expired,bytes(raw),metadata
    raise RuntimeError('Alternate reference retries exhausted')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['audit','output','state']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--threads',type=int,required=True)
    p.add_argument('--max-batches',type=int,default=0)
    a=p.parse_args()
    from dotenv import load_dotenv
    from nn_meta.v7.storage import sha,verify,identity,receipt,transaction
    from scripts.download_v7_data import quota_update,tree_bytes
    from incubator.continual.storage import write
    import fcntl
    for name in ['audit','output','state']:setattr(a,name,getattr(a,name).resolve())
    budget=ROOT/'nn_meta/data_v7'
    if not a.output.is_relative_to(budget) or not a.state.is_relative_to(ROOT/'nn_meta/validation'):
        p.error('Use shared capture budget and separate state root')
    if not 1<=a.threads<=16 or a.max_batches<0:p.error('Bounded threads and batch budget required')
    verify(a.audit);load_dotenv(ROOT/'.env')
    a.state.mkdir(parents=True,exist_ok=True);a.output.mkdir(parents=True,exist_ok=True)
    lock=(a.state/'lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    declaration=dict(schema='v7-full-reference-alternate-recovery-v1',audit=str(a.audit),
        audit_sha256=sha(a.audit/'complete.json'),producer_sha256=sha(__file__),output=str(a.output),
        max_bytes=1024**3,scope='All unapproved 404 pairs, both expired query values; no automatic admission or exclusion')
    if (a.state/'declaration.json').exists() and json.loads((a.state/'declaration.json').read_text())!=declaration:
        raise ValueError('Recovery campaign identity changed')
    write(a.state/'declaration.json',declaration)
    db=sqlite3.connect((a.audit/'coverage.sqlite3').as_uri()+'?mode=ro&immutable=1',uri=True)
    rows=db.execute('SELECT contract,date,receipt_sha256 FROM observed WHERE admission="unavailable_404" ORDER BY contract,date')
    done=matches=batches=0;began=time.monotonic();charged=tree_bytes(a.output);complete=False
    def progress(status):
        write(a.state/'progress.json',dict(status=status,campaign_identity=identity(declaration),
            pairs_complete=done,exact_matching_queries=matches,batches_complete=batches,retained_bytes=charged,
            elapsed_seconds=time.monotonic()-began,updated_at=datetime.now(timezone.utc).isoformat(),
            recovery_capture_complete=complete,reference_admission_complete=False))
    progress('running')
    try:
        with ThreadPoolExecutor(max_workers=a.threads) as pool:
            while True:
                pairs=rows.fetchmany(32)
                if not pairs:complete=True;break
                binding=dict(campaign_identity=identity(declaration),pairs=pairs)
                destination=a.output/identity(binding)
                if destination.exists():
                    verify(destination,expected_identity=identity(binding))
                    report=json.loads((destination/'report.json').read_text())
                else:
                    if charged+64*MAX_BODY>declaration['max_bytes'] or shutil.disk_usage(budget).free<11_000_000_000:
                        raise ValueError('Reference recovery capacity guard reached')
                    token=uuid.uuid4().hex;quota_update(budget,reserve=token)
                    prior=set(a.output.glob(destination.name+'.partial-*'))
                    try:
                        with transaction(destination) as temp:
                            with sqlite3.connect(temp/'responses.sqlite3') as out:
                                out.execute('CREATE TABLE responses(contract,date,expired,body BLOB,receipt_json,PRIMARY KEY(contract,date,expired)) WITHOUT ROWID')
                                exact=0
                                for c,d,expired,raw,metadata in pool.map(fetch,[(*row,value) for row in pairs for value in ['false','true']]):
                                    exact+=bool(metadata['exact_matches'])
                                    out.execute('INSERT INTO responses VALUES(?,?,?,?,?)',(c,d,expired,raw,json.dumps(metadata,sort_keys=True)))
                            report=dict(pairs=len(pairs),queries=len(pairs)*2,exact_matching_queries=exact)
                            for name,doc in [('binding.json',binding),('report.json',report)]:write(temp/name,doc)
                            receipt(temp,dict(identity=identity(binding),reference_admission_complete=False))
                    finally:
                        used=tree_bytes(destination) if destination.exists() else 0
                        used+=sum(tree_bytes(p) for p in a.output.glob(destination.name+'.partial-*') if p not in prior)
                        quota_update(budget,finish=(token,used));charged+=used
                done+=report['pairs'];matches+=report['exact_matching_queries'];batches+=1
                progress('running')
                if batches%10==0:print(json.dumps(dict(pairs=done,matching_queries=matches,bytes=charged)),flush=True)
                if a.max_batches and batches>=a.max_batches:break
        progress('completed' if complete else 'checkpointed')
    except Exception:
        progress('failed');raise
    finally:db.close()


if __name__=='__main__':main()
