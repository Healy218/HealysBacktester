#!/usr/bin/env python3
"""Capture one explicit bounded request batch directly into a v2 pack.

Original request memberships are sealed in the pack binding. This CLI is for
consumer-bound validation; full bulk scheduling needs a separate budget gate.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('requests','output','evidence'):
        p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args()
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    from dotenv import load_dotenv
    from options.data.massive_ticks import MassiveTicks
    from nn_meta.v7.packed_quotes_v2 import write_pack,PackedQuoteArchive
    from nn_meta.v7.storage import verify,sha,identity,transaction,receipt
    from nn_meta.v7.quotes import capture_union
    from scripts.capture_v7_joined_sample import capture_split
    from scripts.capture_v7_volume_sample import guard
    from scripts.download_v7_data import save,quota_update,tree_bytes,TASK_RESERVATION
    for name in ('requests','output','evidence'):
        setattr(args,name,getattr(args,name).resolve())
    budget=ROOT/'nn_meta/data_v7'
    if not args.output.is_relative_to(budget) or not args.evidence.is_relative_to(ROOT/'nn_meta/validation'):
        p.error('Use acquisition output and validation evidence')
    requests=json.loads(args.requests.read_text())
    if not isinstance(requests,list) or not 0<len(requests)<=1000:
        raise ValueError('Explicit bounded request list required')
    union=capture_union(requests,max_span_ns=86400*10**9)
    if len(union['captures'])>128:raise ValueError('Validation batch exceeds 128 capture ranges')
    policy_path=ROOT/'docs/specs/V7_CAPTURE_CAPACITY_20260926.json'
    policy=json.loads(policy_path.read_text())
    binding=dict(requests_path=str(args.requests),requests_sha256=sha(args.requests),union=union,
        sources={str(p):sha(p) for p in (Path(__file__),ROOT/'nn_meta/v7/packed_quotes.py',
            ROOT/'nn_meta/v7/packed_quotes_v2.py',ROOT/'options/data/massive_ticks.py',
            ROOT/'scripts/capture_v7_joined_sample.py',ROOT/'scripts/download_v7_data.py',
            ROOT/'nn_meta/v7/storage.py',ROOT/'nn_meta/v7/quotes.py',policy_path)})
    if args.evidence.exists():
        verify(args.evidence,expected_identity=identity(binding));verify(args.output,expected_identity=identity(binding));return
    attempts=[]
    if not args.output.exists():
        guard(dict(acquisition_budget_bytes=2*TASK_RESERVATION,metadata_budget_bytes=64*1024**2,
            disk_reserve_bytes=policy['disk_reserve_bytes'],project_baseline_ceiling_bytes=490000000000,
            project_budget_bytes=policy['project_limit_bytes']),used_bytes=0,pending=1,
            task_reservation=TASK_RESERVATION,free_bytes=shutil.disk_usage(budget).free,
            quota=json.loads((budget/'quota.json').read_text()))
        load_dotenv(ROOT/'.env');client=MassiveTicks()
        key=uuid.uuid4().hex;quota_update(budget,reserve=key)
        previous=set(args.output.parent.glob(args.output.name+'.partial-*'))
        try:
            def entries():
                for item in union['captures']:
                    yield from capture_split(client,item,attempts)
            write_pack(args.output,entries(),binding=binding)
        finally:
            used=tree_bytes(args.output) if args.output.exists() else 0
            used+=sum(tree_bytes(path) for path in args.output.parent.glob(args.output.name+'.partial-*') if path not in previous)
            quota_update(budget,finish=(key,used))
            with transaction(args.evidence.with_suffix('.attempts')/uuid.uuid4().hex) as temp:
                save(temp/'report.json',dict(split_attempts=attempts,completed_pack=args.output.exists(),
                    failure_policy='An incomplete pack is never inferred as coverage',charged_bytes=used))
                receipt(temp,dict(identity=identity(binding)))
    verify(args.output,expected_identity=identity(binding))
    checks=[]
    with PackedQuoteArchive(args.output) as archive:
        for row in requests:
            data,manifest=archive.window(*[row[k] for k in ('contract','kind','start_ns','end_ns')])
            checks.append(dict(request_id=row['request_id'],records=len(data),records_sha256=manifest['records_sha256']))
    if sha(args.requests)!=binding['requests_sha256'] or any(sha(path)!=digest for path,digest in binding['sources'].items()):
        raise ValueError('Capture source or request file drift')
    report=dict(schema='v7-direct-packed-batch-v1',requests=len(requests),captures=len(union['captures']),checks=checks,
        pack_receipt_sha256=sha(args.output/'complete.json'),bytes=tree_bytes(args.output),full_execution_coverage=False,research_ready=False)
    with transaction(args.evidence) as temp:
        save(temp/'binding.json',binding);save(temp/'report.json',report);receipt(temp,dict(identity=identity(binding),research_ready=False))
    print(json.dumps({k:v for k,v in report.items() if k!='checks'}))


if __name__=='__main__':main()
