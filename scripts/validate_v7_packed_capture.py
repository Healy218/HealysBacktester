#!/usr/bin/env python3
"""Prove packed consumer parity against retained fixed and joined raw archives."""
import argparse
import gzip
import json
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('archive','plan','output','evidence'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    from nn_meta.v7.packed_quotes import write_pack, PackedQuoteArchive
    from nn_meta.v7.quote_archive import QuoteArchive
    from nn_meta.v7.storage import verify, sha, identity, receipt, transaction
    from scripts.download_v7_data import save, quota_update, tree_bytes, TASK_RESERVATION
    from scripts.capture_v7_volume_sample import guard
    from scripts.validate_v7_adjacent_capture import same_records
    import shutil
    budget=ROOT/'nn_meta/data_v7'
    for name in ('archive','plan','output','evidence'):
        setattr(args,name,getattr(args,name).resolve())
    if not args.output.is_relative_to(budget) or not args.evidence.is_relative_to(ROOT/'nn_meta/validation'):
        parser.error('Use acquisition output and validation evidence')
    verify(args.plan)
    requests=json.loads((args.plan/'requests.json').read_text())
    archive=QuoteArchive(args.archive)
    inputs={str(args.plan/'complete.json'):sha(args.plan/'complete.json'),
            str(args.archive/'requests.json'):sha(args.archive/'requests.json')}
    for item in archive.plan['captures']:
        verify(args.archive/item['capture_id'],expected_identity=item['capture_id'])
        path=args.archive/item['capture_id']/'complete.json'
        inputs[str(path)]=sha(path)
    binding=dict(inputs=inputs,sources={str(p):sha(p) for p in (
        Path(__file__),ROOT/'nn_meta/v7/packed_quotes.py',ROOT/'nn_meta/v7/quote_archive.py')})
    if args.evidence.exists():
        verify(args.evidence,expected_identity=identity(binding)); verify(args.output)
        print('Verified prior packed parity evidence');return
    if not args.output.exists():
        policy=json.loads((ROOT/'docs/specs/V7_CAPTURE_CAPACITY_20260926.json').read_text())
        guard(dict(acquisition_budget_bytes=2*TASK_RESERVATION,metadata_budget_bytes=64*1024**2,
            project_baseline_ceiling_bytes=490000000000,project_budget_bytes=policy['project_limit_bytes'],
            disk_reserve_bytes=policy['disk_reserve_bytes']),used_bytes=0,pending=1,
            task_reservation=TASK_RESERVATION,free_bytes=shutil.disk_usage(budget).free,
            quota=json.loads((budget/'quota.json').read_text()))
        reservation=uuid.uuid4().hex
        quota_update(budget,reserve=reservation)
        prior={p for p in args.output.parent.glob(args.output.name+'.partial-*')}
        try:
            def entries():
                for item in archive.plan['captures']:
                    rows,manifest=archive._read(item)
                    yield item,rows,manifest
            write_pack(args.output,entries(),binding=binding)
        finally:
            used=tree_bytes(args.output) if args.output.exists() else 0
            used+=sum(tree_bytes(p) for p in args.output.parent.glob(args.output.name+'.partial-*') if p not in prior)
            quota_update(budget,finish=(reservation,used))
    checks=[]
    with PackedQuoteArchive(args.output,cache_shards=1) as packed:
        for item in requests:
            scope=[item[k] for k in ('contract','kind','start_ns','end_ns')]
            original,lm=archive.window(*scope); restored,rm=packed.window(*scope)
            same_records(original,restored)
            if lm['records_sha256']!=rm['records_sha256']:
                raise ValueError('Packed causal window hash drift')
            checks.append(dict(request_id=item['request_id'],records=len(restored),sha256=rm['records_sha256']))
    for path,digest in {**binding['inputs'],**binding['sources']}.items():
        if sha(path)!=digest:raise ValueError('Packed parity parent changed')
    report=dict(raw_record_parity=True,causal_request_parity=True,request_count=len(checks),checks=checks,
                packed_bytes=tree_bytes(args.output),original_bytes=tree_bytes(args.archive),
                packed_receipt_sha256=sha(args.output/'complete.json'),research_ready=False)
    with transaction(args.evidence) as temp:
        save(temp/'binding.json',binding); save(temp/'report.json',report)
        receipt(temp,dict(identity=identity(binding),research_ready=False))
    print(json.dumps({k:v for k,v in report.items() if k!='checks'}))


if __name__=='__main__':main()
