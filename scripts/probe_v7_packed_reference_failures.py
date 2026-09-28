#!/usr/bin/env python3
"""Retain exact alternative-list evidence for selected packed reference failures.

No blackout admission or source substitution. Bounded review inputs only.
"""
from datetime import datetime,timezone
import argparse,json,os,sqlite3,sys,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--requests',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    import requests
    from dotenv import load_dotenv
    from nn_meta.v7.storage import sha,identity,verify,receipt,transaction
    from nn_meta.v7.packed_references import query
    from options.data.provider import parse_occ_symbol
    from scripts.download_v7_data import quota_update,tree_bytes,save
    from scripts.v7_capture_storage import RESERVE
    import shutil
    a.output=a.output.resolve();budget=ROOT/'nn_meta/data_v7'
    if not a.output.is_relative_to(budget):raise ValueError('Use shared capture budget root')
    items=json.loads(a.requests.read_text())
    if not isinstance(items,list) or not 0<len(items)<=16:raise ValueError('Select 1..16 exact review pairs')
    load_dotenv(ROOT/'.env');session=requests.Session()
    for item in items:
        pack=Path(item['pack']);verify(pack);c,d=item['contract'],item['date']
        with sqlite3.connect((pack/'references.sqlite3').resolve().as_uri()+'?mode=ro',uri=True) as db:
            status,body,encoded,anchor=db.execute('SELECT http_status,body,receipt_json,receipt_sha256 FROM responses WHERE contract=? AND date=?',(c,d)).fetchone()
        if status!=404 or json.loads(encoded)['query']!=query(c,d):raise ValueError('Exact retained 404 required')
        root,expiry,right,strike=parse_occ_symbol(c)
        for expired in ['false','true']:
            q=dict(path='/v3/reference/options/contracts',params=dict(underlying_ticker=root,
                expiration_date=expiry.isoformat(),strike_price=strike,contract_type='call' if right=='C' else 'put',
                as_of=d,expired=expired,limit=1000))
            binding=dict(query=q,missing_pack_receipt_sha256=sha(pack/'complete.json'),
                         missing_row_receipt_sha256=anchor,producer_sha256=sha(__file__))
            dest=a.output/c/d/expired
            if dest.exists():verify(dest,expected_identity=identity(binding));continue
            if shutil.disk_usage(budget).free<RESERVE+1024**3:raise ValueError('Disk reserve reached')
            token=uuid.uuid4().hex;quota_update(budget,reserve=token);prior=set(dest.parent.glob(dest.name+'.partial-*'))
            try:
                for attempt in range(5):
                    try:r=session.get('https://api.massive.com'+q['path'],params=q['params'],
                        headers={'Authorization':'Bearer '+os.environ['MASSIVE_API_KEY']},timeout=30,allow_redirects=False)
                    except requests.RequestException:raise RuntimeError('Reference probe transport failed') from None
                    if r.status_code not in (429,500,502,503,504):break
                    time.sleep(2**attempt)
                if r.status_code!=200 or len(r.content)>4*1024**2:raise ValueError('Unexpected probe HTTP status or size')
                response=r.json()
                if response.get('status')!='OK' or response.get('next_url') or not isinstance(response.get('results',[]),list):
                    raise ValueError('Probe lacks complete bounded list')
                with transaction(dest) as temp:
                    (temp/'response.json').write_bytes(r.content);save(temp/'binding.json',binding)
                    receipt(temp,dict(identity=identity(binding),http_status=200,pagination_complete=True,
                        retrieved_at=datetime.now(timezone.utc).isoformat(),exact_match=any(row.get('ticker')=='O:'+c for row in response.get('results',[]))))
                print(json.dumps(dict(contract=c,date=d,expired=expired,results=len(response.get('results',[])),
                    exact_match=any(row.get('ticker')=='O:'+c for row in response.get('results',[])))),flush=True)
            finally:
                used=tree_bytes(dest) if dest.exists() else 0
                used+=sum(tree_bytes(x) for x in dest.parent.glob(dest.name+'.partial-*') if x not in prior)
                quota_update(budget,finish=(token,used))


if __name__=='__main__':main()
