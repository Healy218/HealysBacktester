"""Independently reconcile complete raw and normalized ETFE capture tranche rows."""
import argparse
from collections import Counter
import hashlib
import json
import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nn_meta.etfe import acquisition as a
from nn_meta.etfe.normalization import load_normalization


def audit(root):
    root=Path(root);plan=load_normalization(root)
    if len(plan['inputs'])!=1:raise ValueError('Single-tranche source expected')
    source=plan['inputs'][0];raw_root=Path(source['root'])
    latest=max((root/'runs').glob('*.json'),key=lambda p:p.stat().st_mtime_ns)
    run=json.loads(latest.read_text())
    seal=run['partition_receipts'];rawplan=a.load_plan(raw_root)
    expected={a.digest([source['sha256'],j['id']]):j for j in rawplan['jobs']}
    if len(seal)!=512 or len(expected)!=3036:raise ValueError('Unexpected tranche census')
    total=0;routes=Counter();checked=0
    for key,digest in sorted(seal.items()):
        if key not in expected:raise ValueError('Unknown normalized key')
        meta_path=root/'partitions'/(key+'.json')
        if a.sha(meta_path.read_bytes())!=digest:raise ValueError('Partition receipt hash mismatch')
        meta=json.loads(meta_path.read_text());item=expected[key]
        history,_,complete=a.committed(raw_root,item)
        if not complete or meta['raw_body_hashes']!=[x['body_sha256'] for x,_,_ in history]:
            raise ValueError('Raw page lineage mismatch')
        before=hashlib.sha256();nraw=0
        for _,body,_ in history:
            for symbol,row in a.rows(body,item):
                before.update((symbol+'\t'+json.dumps(row,sort_keys=True,separators=(',',':'))+'\n').encode());nraw+=1
        data=root/meta['data']
        if a.sha(data.read_bytes())!=meta['data_sha256']:raise ValueError('Parquet hash mismatch')
        after=hashlib.sha256();n=0;quality=Counter()
        for batch in pq.ParquetFile(data).iter_batches(batch_size=5000,columns=['symbol','raw_json','quality_flags']):
            for row in batch.to_pylist():
                after.update((row['symbol']+'\t'+row['raw_json']+'\n').encode());n+=1;quality.update(row['quality_flags'])
        if n!=nraw or n!=meta['rows'] or before.digest()!=after.digest() or dict(quality)!=meta['quality_counts']:
            raise ValueError('Occurrence/value/quality mismatch')
        total+=n;routes[item['route']]+=n;checked+=1
    result=dict(schema='etfe-capture-tranche-independent-audit-v1',
        capture_plan_sha256=rawplan['sha256'],normalization_plan_sha256=plan['sha256'],
        terminal_jobs=checked,normalized_occurrences=total,rows_by_route=dict(routes),
        raw_typed_occurrences_and_quality_reconciled=True,
        historical_admission=False,ready_for_build=False,ready_for_training=False,
        auditor_sha256=a.sha(Path(__file__).read_bytes()))
    a.save(root/'TRANCHE_INDEPENDENT_AUDIT.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(audit(args.root.resolve()),indent=2))
