"""Capture bounded Alpaca-only stock liquidation quotes under the shared V7 cap."""
from pathlib import Path
import argparse
import gzip
import json
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def prepare_request(row, allowed_ids):
    import pandas as pd
    from nn_meta.v7.stock_quotes import scope
    from nn_meta.v7.storage import verify,sha,identity
    expected={'symbol','security_id','start_ns','end_ns','identity_reference',
              'legacy_lot_shares','size_evidence'}
    if set(row)!=expected or row['security_id'] not in allowed_ids:
        raise ValueError('Exact stock request and active non-OTC security identity required')
    query=scope(row['symbol'],row['start_ns'],row['end_ns'])
    path=Path(row['identity_reference'])
    doc=verify(path)
    source=json.loads((path/'response.json').read_text())['results']
    day=pd.Timestamp(query['start_ns'],unit='ns',tz='UTC').tz_convert('America/New_York').date().isoformat()
    if (doc.get('http_status')!=200 or doc['query']!={'params':{'date':day},'path':'/v3/reference/tickers/'+row['symbol']}
            or source.get('ticker')!=row['symbol'] or source.get('composite_figi')!=row['security_id']
            or source.get('market')!='stocks' or source.get('locale')!='us'
            or source.get('primary_exchange') not in ('XNYS','XNAS','ARCX','XASE','BATS')):
        raise ValueError('Exact-date listed-security reference required; no OTC or ticker remapping')
    if type(row['legacy_lot_shares']) is not int or row['legacy_lot_shares']<=0 or not row['size_evidence']:
        raise ValueError('Explicit legacy lot size and source evidence required')
    evidence={str(path/'complete.json'):sha(path/'complete.json'),str(path/'response.json'):sha(path/'response.json')}
    for value in row['size_evidence']:
        p=Path(value);d=verify(p)
        evidence[str(p/'complete.json')]=sha(p/'complete.json')
        evidence.update({str(p/name):digest for name,digest in d['files'].items()})
    return {**query,'security_id':row['security_id'],'legacy_lot_shares':row['legacy_lot_shares'],
        'size_source_identity':identity({k:v for k,v in evidence.items() if k.startswith(tuple(row['size_evidence']))}),
        'evidence':evidence,'identity_basis':'exact-date historical company reference; original publication vintage unverified'}


def capture_one(item, output, budget):
    from nn_meta.v7.stock_quotes import AlpacaStockQuotes
    from nn_meta.v7.storage import verify,identity,transaction,receipt,sha
    from scripts.download_v7_data import quota_update,tree_bytes,TASK_RESERVATION,disk_guard
    cid=identity(item);dest=output/cid
    for path,digest in item['evidence'].items():
        if sha(path)!=digest:raise ValueError('Stock request evidence changed')
    if dest.exists():
        d=verify(dest,expected_identity=cid)
        if d.get('capture')!=item:raise ValueError('Saved stock request changed')
        return {'capture_id':cid,'rows':d['rows'],'reused':True}
    disk_guard(budget,100);key=uuid.uuid4().hex
    before=sum(tree_bytes(p) for p in output.glob(cid+'.partial-*'))
    quota_update(budget,reserve=key)
    try:
        rows,manifest=AlpacaStockQuotes().capture(item['symbol'],item['start_ns'],item['end_ns'])
        data=gzip.compress(json.dumps(rows,sort_keys=True,separators=(',',':'),allow_nan=False).encode(),mtime=0)
        if len(data)+len(json.dumps(manifest).encode())+1024**2>TASK_RESERVATION:
            raise ValueError('Stock quote capture exceeds reservation; split window')
        for path,digest in item['evidence'].items():
            if sha(path)!=digest:raise ValueError('Stock evidence changed during capture')
        with transaction(dest) as tmp:
            (tmp/'records.json.gz').write_bytes(data)
            (tmp/'capture.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
            receipt(tmp,{'identity':cid,'format':'v7-frozen-stock-capture-v1','capture':item,
                'rows':len(rows),'research_ready':False,'full_execution_coverage':False})
        return {'capture_id':cid,'rows':len(rows),'reused':False}
    finally:
        used=(tree_bytes(dest) if dest.exists() else 0)+sum(tree_bytes(p) for p in output.glob(cid+'.partial-*'))
        quota_update(budget,finish=(key,max(0,used-before)))


def main():
    from dotenv import load_dotenv
    import pandas as pd
    from nn_meta.v7.storage import verify,sha
    ap=argparse.ArgumentParser(description=__doc__)
    for flag in ('requests','output','budget-root'):
        ap.add_argument('--'+flag,type=Path,required=True)
    ap.add_argument('--active',type=Path,default=ROOT/'docs/specs/V7_ACTIVE_INPUTS_20220315.json')
    args=ap.parse_args();load_dotenv(ROOT/'.env')
    output,budget=args.output.resolve(),args.budget_root.resolve()
    if not output.is_relative_to(budget) or not (budget/'quota.json').exists():
        raise ValueError('Stock captures must use initialized shared acquisition budget')
    active=json.loads(args.active.read_text());universe=ROOT/active['universe']
    verify(universe)
    if sha(universe/'complete.json')!=active['universe_receipt_sha256']:
        raise ValueError('Active universe changed')
    exclusions=json.loads((ROOT/active['universe_exclusions']).read_text())
    if sha(ROOT/active['universe_exclusions'])!=active['universe_exclusions_sha256']:
        raise ValueError('Active no-OTC exclusion declaration changed')
    allowed=set(pd.read_parquet(universe/'membership.parquet',columns=['security_id']).security_id)
    allowed-={x['security_id'] for x in exclusions['exclusions']}
    rows=json.loads(args.requests.read_text())
    if not isinstance(rows,list) or not 0<len(rows)<=1000:
        raise ValueError('Provide 1–1000 bounded stock requests')
    items=[prepare_request(row,allowed) for row in rows]
    # Serial acquisition preserves headroom for V6; no hidden worker count.
    for item in items:
        print(json.dumps(capture_one(item,output,budget)),flush=True)


if __name__=='__main__':main()
