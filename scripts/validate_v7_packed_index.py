#!/usr/bin/env python3
"""Seal sample pack routing and verify every original request in sampled ranges."""
import argparse
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('forecast','plan','audit','output','evidence'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    from nn_meta.v7.packed_quote_index import write_index,IndexedQuoteArchive
    from nn_meta.v7.packed_quotes_v2 import PackedQuoteArchive
    from nn_meta.v7.storage import verify,sha,identity,transaction,receipt
    from scripts.download_v7_data import quota_update,tree_bytes,save,TASK_RESERVATION
    from scripts.capture_v7_volume_sample import guard
    from scripts.validate_v7_adjacent_capture import same_records
    for name in ('forecast','plan','audit','output','evidence'):
        setattr(args,name,getattr(args,name).resolve())
    budget=ROOT/'nn_meta/data_v7'
    if not args.output.is_relative_to(budget) or not args.evidence.is_relative_to(ROOT/'nn_meta/validation'):
        parser.error('Use acquisition output and validation evidence')
    for root in (args.forecast,args.plan,args.audit):verify(root)
    forecast=json.loads((args.forecast/'report.json').read_text())
    plan=json.loads((args.plan/'report.json').read_text())
    audit=json.loads((args.audit/'report.json').read_text())
    demand=Path(json.loads((args.audit/'binding.json').read_text())['demand_root'])/'demand'
    binding=dict(inputs={str(root/'complete.json'):sha(root/'complete.json') for root in (args.forecast,args.plan,args.audit)},
        sources={str(p):sha(p) for p in (Path(__file__),ROOT/'nn_meta/v7/packed_quote_index.py',
            ROOT/'nn_meta/v7/packed_quotes.py',ROOT/'nn_meta/v7/packed_quotes_v2.py')})
    if args.evidence.exists():
        verify(args.evidence,expected_identity=identity(binding));verify(args.output);return
    if not args.output.exists():
        guard(plan,used_bytes=0,pending=1,task_reservation=TASK_RESERVATION,free_bytes=shutil.disk_usage(budget).free,
              quota=json.loads((budget/'quota.json').read_text()))
        key=uuid.uuid4().hex;quota_update(budget,reserve=key)
        previous=set(args.output.parent.glob(args.output.name+'.partial-*'))
        try:
            write_index(args.output,[p['pack'] for p in forecast['packs']],binding=binding)
        finally:
            used=tree_bytes(args.output) if args.output.exists() else 0
            used+=sum(tree_bytes(p) for p in args.output.parent.glob(args.output.name+'.partial-*') if p not in previous)
            quota_update(budget,finish=(key,used))
    samples={c['capture_id']:(sample,c) for sample in plan['samples'] for c in sample['captures'].values()}
    verified=set();checks=[]
    with IndexedQuoteArchive(args.output,cache_packs=1) as indexed:
        for number,pack in enumerate(forecast['packs']):
            with PackedQuoteArchive(pack['pack'],cache_shards=1) as original:
                for cid,contract,kind,start,end in original.db.execute('SELECT capture_id,contract,kind,start_ns,end_ns FROM captures'):
                    sample,item=samples[cid]
                    root=demand/sample['security_id']
                    if root not in verified:
                        if sha(root/'complete.json')!=audit['inputs'][str(root/'complete.json')]:
                            raise ValueError('Demand receipt differs from union audit')
                        verify(root);verified.add(root)
                    with sqlite3.connect((root/'demand.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
                        requests=db.execute('SELECT request_id,start_ns,end_ns FROM requests WHERE contract=? AND date=? '
                            'AND kind=? AND start_ns>=? AND end_ns<=? ORDER BY start_ns,end_ns',
                            (contract,sample['date'],kind,start,end)).fetchall()
                    if not requests:raise ValueError('Sample has no original demand mapping')
                    for rid,lo,hi in requests:
                        left,lm=original.window(contract,kind,lo,hi);right,rm=indexed.window(contract,kind,lo,hi)
                        same_records(left,right)
                        if lm['records_sha256']!=rm['records_sha256']:raise ValueError('Indexed request hash drift')
                        checks.append(dict(request_id=rid,capture_id=cid,records=len(right),records_sha256=rm['records_sha256']))
            if (number+1)%10==0:print(f'Indexed original-request parity {number+1}/{len(forecast["packs"])} packs',flush=True)
    for path,digest in {**binding['inputs'],**binding['sources']}.items():
        if sha(path)!=digest:raise ValueError('Index proof parent changed')
    report=dict(schema='v7-packed-index-parity-v1',sample_captures=len(samples),original_request_checks=len(checks),
        security_checks=len(verified),checks=checks,raw_request_parity=True,index_bytes=tree_bytes(args.output),
        estimated_population_index_bytes=int(tree_bytes(args.output)*plan['population_captures']/len(samples)),
        index_projection_note='Linear measured bytes per capture at 24 captures per pack; planning estimate, not upper bound.',
        index_receipt_sha256=sha(args.output/'complete.json'),full_execution_coverage=False,research_ready=False)
    with transaction(args.evidence) as temp:
        save(temp/'binding.json',binding);save(temp/'report.json',report)
        receipt(temp,dict(identity=identity(binding),research_ready=False))
    print(json.dumps({k:v for k,v in report.items() if k!='checks'}))


if __name__=='__main__':main()
