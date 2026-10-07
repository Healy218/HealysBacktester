"""Typed Parquet normalization and independent audit for ETFE envelope captures.

One partition per capture job, raw occurrence order preserved, page/ordinal/body-hash lineage.
Output roots are immutable: an existing partition is verified by hash and never rewritten.
"""
import hashlib
import json
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from nn_meta.etfe import option_minute_capture as m,stock_quote_capture_v2 as q

ENGINES={'bars':m,'quotes':q}
FIELDS={'bars':[('o','open',pa.float64()),('h','high',pa.float64()),('l','low',pa.float64()),('c','close',pa.float64()),
                ('v','volume',pa.int64()),('n','trade_count',pa.int64()),('vw','vwap',pa.float64())],
        'quotes':[('bp','bid',pa.float64()),('bs','bid_size_raw',pa.int64()),('bx','bid_exchange',pa.string()),
                  ('ap','ask',pa.float64()),('as','ask_size_raw',pa.int64()),('ax','ask_exchange',pa.string()),
                  ('c','conditions',pa.list_(pa.string())),('z','tape',pa.string())]}


def table(kind,item,history):
    engine=ENGINES[kind];cols={k:[] for k in ('symbol','timestamp_ns','page','ordinal','body_sha256')}
    for _,name,_ in FIELDS[kind]:cols[name]=[]
    for page,(receipt,body,_) in enumerate(history):
        for ordinal,(sym,row) in enumerate(engine.rows(body,item)):
            cols['symbol'].append(sym);cols['timestamp_ns'].append(pd.Timestamp(row['t']).value)
            cols['page'].append(page);cols['ordinal'].append(ordinal);cols['body_sha256'].append(receipt['body_sha256'])
            for raw,name,_ in FIELDS[kind]:cols[name].append(row[raw])
    schema=pa.schema([('symbol',pa.string()),('timestamp_ns',pa.int64()),('page',pa.int32()),('ordinal',pa.int32()),
        ('body_sha256',pa.string())]+[(name,t) for _,name,t in FIELDS[kind]])
    return pa.Table.from_pydict(cols,schema=schema)


def normalize(kind,raw_root,out):
    engine=ENGINES[kind];raw_root,out=Path(raw_root),Path(out);plan=engine.load_plan(raw_root)
    (out/'partitions').mkdir(parents=True,exist_ok=True);receipts={};rows=0
    for item in plan['jobs']:
        meta_path=out/'partitions'/(item['id']+'.json')
        if meta_path.exists():
            meta=json.loads(meta_path.read_text())
            if engine.sha((out/meta['data']).read_bytes())!=meta['data_sha256']:raise ValueError('Partition drift')
        else:
            history,_,done=engine.committed(raw_root,item)
            if not done:raise ValueError(f'Incomplete capture job {item["id"]}')
            t=table(kind,item,history);data=out/'partitions'/(item['id']+'.parquet')
            if data.exists():raise ValueError('Uncommitted partition requires recovery')
            pq.write_table(t,data,compression='zstd')
            meta=dict(job_id=item['id'],purpose=item['purpose'],data=str(data.relative_to(out)),
                data_sha256=engine.sha(data.read_bytes()),rows=t.num_rows,pages=len(history),
                raw_body_hashes=[r['body_sha256'] for r,_,_ in history])
            engine.save(meta_path,meta)
        receipts[item['id']]=engine.sha(meta_path.read_bytes());rows+=meta['rows']
    seal=dict(schema=f'etfe-envelope-normalized-{kind}-v1',capture_plan_sha256=plan['sha256'],partitions=len(receipts),
        rows=rows,partition_receipts=receipts,ready_for_build=False,ready_for_training=False)
    if not (out/'NORMALIZED.json').exists():engine.save(out/'NORMALIZED.json',seal)
    return {k:v for k,v in seal.items() if k!='partition_receipts'}


def audit(kind,raw_root,out):
    """Recount and rehash every partition straight from raw bodies (json only, no engine row parser)."""
    engine=ENGINES[kind];raw_root,out=Path(raw_root),Path(out);plan=engine.load_plan(raw_root)
    seal=json.loads((out/'NORMALIZED.json').read_text());field='bars' if kind=='bars' else 'quotes';total=0
    if seal['capture_plan_sha256']!=plan['sha256'] or len(seal['partition_receipts'])!=len(plan['jobs']):raise ValueError('Seal/plan mismatch')
    for item in plan['jobs']:
        meta_path=out/'partitions'/(item['id']+'.json')
        if engine.sha(meta_path.read_bytes())!=seal['partition_receipts'][item['id']]:raise ValueError('Receipt drift')
        meta=json.loads(meta_path.read_text());before=hashlib.sha256();n=0
        for h in meta['raw_body_hashes']:
            body=None
            for page in sorted((raw_root/'jobs'/item['id']).glob('page-*.json')):
                attempt=raw_root/json.loads(page.read_text())['attempt']
                if json.loads((attempt/'receipt.json').read_text())['body_sha256']==h:
                    raw=(attempt/'body.json').read_bytes()
                    if engine.sha(raw)!=h:raise ValueError('Raw body hash')
                    body=json.loads(raw);break
            if body is None:raise ValueError('Missing raw body')
            for sym,records in (body[field] or {}).items():
                for r in records:before.update(f"{sym}\t{pd.Timestamp(r['t']).value}\n".encode());n+=1
        t=pq.read_table(out/meta['data'],columns=['symbol','timestamp_ns'])
        after=hashlib.sha256()
        for s,ts in zip(t['symbol'].to_pylist(),t['timestamp_ns'].to_pylist()):after.update(f'{s}\t{ts}\n'.encode())
        if n!=meta['rows'] or before.digest()!=after.digest():raise ValueError(f'Occurrence mismatch {item["id"]}')
        total+=n
    result=dict(schema=f'etfe-envelope-normalized-{kind}-independent-audit-v1',rows=total,partitions=len(plan['jobs']),
        occurrences_reconciled=True,capture_plan_sha256=plan['sha256'])
    if not (out/'INDEPENDENT_AUDIT.json').exists():engine.save(out/'INDEPENDENT_AUDIT.json',result)
    return result
