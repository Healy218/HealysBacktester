"""Reconcile every normalized raw-row occurrence against captured page bodies."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nn_meta.etfe.acquisition import committed,load_plan,rows,save,sha
from nn_meta.etfe.normalization import load_normalization


def audit(root):
    root=Path(root);plan=load_normalization(root)
    seal=json.loads((root/'NORMALIZED.json').read_text())
    if seal['plan_sha256']!=plan['sha256'] or not seal['normalized_complete']:
        raise ValueError('Missing complete normalization seal')
    inputs={p['sha256']:p for p in plan['inputs']}
    total=0;counts=Counter();checked=[]
    expected=sum(len(load_plan(p['root'])['jobs']) for p in inputs.values())
    if len(seal['partition_receipts'])!=expected:
        raise ValueError('Partition inventory mismatch')
    for key,digest in sorted(seal['partition_receipts'].items()):
        meta_path=root/'partitions'/(key+'.json')
        if sha(meta_path.read_bytes())!=digest:raise ValueError('Partition receipt mismatch')
        meta=json.loads(meta_path.read_text());source=inputs[meta['input_plan_sha256']]
        item=next(j for j in load_plan(source['root'])['jobs'] if j['id']==meta['job_id'])
        history,_,complete=committed(source['root'],item)
        if not complete:raise ValueError('Raw input incomplete')
        before=hashlib.sha256();raw_count=0
        for _,body,_ in history:
            for symbol,row in rows(body,item):
                before.update((symbol+'\t'+json.dumps(row,sort_keys=True,separators=(',',':'))+'\n').encode())
                raw_count+=1
        data=root/meta['data']
        if sha(data.read_bytes())!=meta['data_sha256']:raise ValueError('Parquet mismatch')
        after=hashlib.sha256();typed_count=0;quality=Counter()
        for batch in pq.ParquetFile(data).iter_batches(batch_size=5000,columns=['symbol','raw_json','quality_flags']):
            for row in batch.to_pylist():
                after.update((row['symbol']+'\t'+row['raw_json']+'\n').encode())
                quality.update(row['quality_flags']);typed_count+=1
        if (before.digest()!=after.digest() or raw_count!=typed_count or typed_count!=meta['rows']
                or dict(quality)!=meta['quality_counts']):
            raise ValueError('Raw-to-normalized sequence/count/quality mismatch')
        total+=typed_count;counts[meta['route']]+=typed_count
        checked.append(dict(key=key,rows=typed_count,row_sequence_sha256=before.hexdigest()))
    if total!=seal['rows']:raise ValueError('Sealed total mismatch')
    return dict(schema='etfe-normalized-independent-audit-v1',root=str(root.resolve()),
        plan_sha256=plan['sha256'],rows=total,rows_by_route=dict(counts),partitions=len(checked),
        raw_occurrence_sequence_preserved=True,checked=checked,
        audit_source_sha256=sha(Path(__file__).read_bytes()),ready_for_build=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=audit(a.root);save(a.output,r)
    print(json.dumps({k:v for k,v in r.items() if k!='checked'},indent=2))


if __name__=='__main__':main()
