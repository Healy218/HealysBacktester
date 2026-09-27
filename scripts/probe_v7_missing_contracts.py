#!/usr/bin/env python3
"""Retain narrow same-date list-endpoint evidence for missing contract references.

No alternate ticker, date or contract is admitted by this diagnostic.
"""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import sys
import uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('references','output'):
        p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args()
    from dotenv import load_dotenv
    import requests
    from options.data.provider import parse_occ_symbol
    from nn_meta.v7.storage import verify,sha,identity,transaction,receipt
    from scripts.download_v7_data import quota_update,tree_bytes,save,disk_guard
    budget=ROOT/'nn_meta/data_v7'
    if not args.output.resolve().is_relative_to(budget):p.error('Use acquisition budget output')
    load_dotenv(ROOT/'.env')
    missing=[]
    for source in sorted(args.references.glob('*/*/complete.json')):
        doc=verify(source.parent)
        if doc['http_status']==404:
            missing.append((source,doc))
    if len(missing)>20:raise ValueError('Diagnostic limited to 20 named missing contracts')
    with requests.Session() as session:
        for source,prior in missing:
            contract=source.parent.parent.name;day=source.parent.name
            root,expiry,right,strike=parse_occ_symbol(contract)
            for expired in ('false','true'):
                query=dict(path='/v3/reference/options/contracts',params=dict(underlying_ticker=root,
                    expiration_date=expiry.isoformat(),strike_price=strike,contract_type='call' if right=='C' else 'put',
                    as_of=day,expired=expired,limit=1000))
                binding=dict(query=query,missing_receipt_sha256=sha(source),producer_sha256=sha(__file__))
                output=args.output/contract/expired
                if output.exists():verify(output,expected_identity=identity(binding));continue
                disk_guard(budget,100)
                key=uuid.uuid4().hex;quota_update(budget,reserve=key)
                before=set(output.parent.glob(output.name+'.partial-*'))
                try:
                    try:
                        response=session.get('https://api.massive.com'+query['path'],params=query['params'],
                            headers={'Authorization':'Bearer '+os.environ['MASSIVE_API_KEY']},timeout=45,allow_redirects=False)
                    except requests.RequestException:
                        raise RuntimeError('Narrow contract-reference transport failed') from None
                    if len(response.content)>1024**2:raise ValueError('Oversized narrow reference response')
                    body=response.json()
                    with transaction(output) as temp:
                        (temp/'response.json').write_bytes(response.content)
                        save(temp/'binding.json',binding)
                        receipt(temp,dict(identity=identity(binding),http_status=response.status_code,
                            pagination_complete=not bool(body.get('next_url')),retrieved_at=datetime.now(timezone.utc).isoformat(),
                            exact_matches=sum(r.get('ticker')=='O:'+contract for r in body.get('results',[])),
                            admission_performed=False))
                    print(json.dumps(dict(contract=contract,date=day,expired=expired,http_status=response.status_code,
                        exact_matches=sum(r.get('ticker')=='O:'+contract for r in body.get('results',[])))),flush=True)
                finally:
                    used=tree_bytes(output) if output.exists() else 0
                    used+=sum(tree_bytes(d) for d in output.parent.glob(output.name+'.partial-*') if d not in before)
                    quota_update(budget,finish=(key,used))


if __name__=='__main__':main()
