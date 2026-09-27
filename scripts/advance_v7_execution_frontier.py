#!/usr/bin/env python3
"""Capture/reuse only the exact missing intervals requested by bounded replay."""
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
    for name in ('frontier','previous-index','output','index-output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--reuse-pack',type=Path,action='append',default=[])
    args=p.parse_args()
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    from dotenv import load_dotenv
    from nn_meta.v7.storage import verify,sha,identity,transaction,receipt
    from nn_meta.v7.packed_quotes_v2 import PackedQuoteArchive,write_pack
    from nn_meta.v7.packed_quote_index import IndexedQuoteArchive,write_index
    from nn_meta.v7.execution import CaptureUnavailable
    from nn_meta.v7.quotes import capture_union
    from scripts.capture_v7_joined_sample import capture_split
    from scripts.capture_v7_volume_sample import guard
    from scripts.download_v7_data import quota_update,tree_bytes,TASK_RESERVATION
    from options.data.massive_ticks import MassiveTicks
    for name in ('frontier','previous_index','output','index_output'):
        setattr(args,name,getattr(args,name).resolve())
    args.reuse_pack=[p.resolve() for p in args.reuse_pack]
    budget=ROOT/'nn_meta/data_v7'
    if not args.output.is_relative_to(budget) or not args.index_output.is_relative_to(ROOT/'nn_meta/validation'):
        p.error('Acquisition pack and new validation index required')
    verify(args.frontier);verify(args.previous_index)
    request_path=args.frontier/'capture-requests.json'
    requests=json.loads(request_path.read_text())
    if not 0<len(requests)<=128:raise ValueError('A bounded nonempty replay frontier is required')
    if sum(r['end_ns']-r['start_ns'] for r in requests)>3600*10**9:
        raise ValueError('Bounded validation exceeds one quote hour')
    prior=json.loads((args.frontier/'binding.json').read_text())['inputs']
    if prior.get(str(args.previous_index/'complete.json'))!=sha(args.previous_index/'complete.json'):
        raise ValueError('Frontier belongs to a different archive index')
    if any(sha(p)!=h for p,h in prior.items()):raise ValueError('Frontier inputs changed')
    plan=capture_union(requests,max_span_ns=86400*10**9)
    inputs={str(args.frontier/'complete.json'):sha(args.frontier/'complete.json'),str(request_path):sha(request_path),
            str(args.previous_index/'complete.json'):sha(args.previous_index/'complete.json')}
    for pack in args.reuse_pack:
        verify(pack);inputs[str(pack/'complete.json')]=sha(pack/'complete.json')
    for path in (Path(__file__),ROOT/'nn_meta/v7/packed_quotes_v2.py',ROOT/'nn_meta/v7/packed_quote_index.py',
                 ROOT/'scripts/capture_v7_joined_sample.py',ROOT/'scripts/download_v7_data.py',ROOT/'options/data/massive_ticks.py',
                 ROOT/'docs/specs/V7_CAPTURE_CAPACITY_20260926.json'):
        inputs[str(path)]=sha(path)
    binding=dict(schema='v7-execution-frontier-capture-v1',inputs=inputs,plan=plan)
    capacity=json.loads((ROOT/'docs/specs/V7_CAPTURE_CAPACITY_20260926.json').read_text())
    guard(dict(acquisition_budget_bytes=2*TASK_RESERVATION,metadata_budget_bytes=64*1024**2,
        disk_reserve_bytes=capacity['disk_reserve_bytes'],project_baseline_ceiling_bytes=490000000000,
        project_budget_bytes=capacity['project_limit_bytes']),used_bytes=0,pending=1,
        task_reservation=TASK_RESERVATION,free_bytes=shutil.disk_usage(budget).free,
        quota=json.loads((budget/'quota.json').read_text()))
    if args.output.exists():verify(args.output,expected_identity=identity(binding))
    else:
        key=uuid.uuid4().hex;quota_update(budget,reserve=key)
        previous=set(args.output.parent.glob(args.output.name+'.partial-*'))
        attempts=[];reused=[];downloaded=[]
        try:
            load_dotenv(ROOT/'.env');client=MassiveTicks()
            def entries():
                for item in plan['captures']:
                    hit=None
                    for pack in args.reuse_pack:
                        with PackedQuoteArchive(pack) as archive:
                            try:
                                rows,manifest=archive.window(*[item[k] for k in ('contract','kind','start_ns','end_ns')])
                                hit=(item,rows,manifest)
                            except CaptureUnavailable:pass
                        if hit is not None:
                            reused.append(dict(capture_id=item['capture_id'],source_pack=str(pack),records_sha256=manifest['records_sha256']))
                            break
                    if hit is not None:yield hit
                    else:
                        downloaded.append(item['capture_id'])
                        yield from capture_split(client,item,attempts)
            write_pack(args.output,entries(),binding=binding)
        finally:
            used=tree_bytes(args.output) if args.output.exists() else 0
            used+=sum(tree_bytes(p) for p in args.output.parent.glob(args.output.name+'.partial-*') if p not in previous)
            quota_update(budget,finish=(key,used))
            with transaction(args.index_output.with_suffix('.attempts')/key) as temp:
                doc=dict(reused=reused,downloaded=downloaded,split_attempts=attempts,charged_bytes=used,completed=args.output.exists())
                (temp/'report.json').write_text(json.dumps(doc,indent=2)+'\n')
                receipt(temp,dict(identity=identity(binding),research_ready=False))
    with IndexedQuoteArchive(args.previous_index) as archive:
        packs=[Path(p) for p, in archive.db.execute('SELECT path FROM packs ORDER BY id')]
    packs.append(args.output)
    index_binding=dict(schema='v7-execution-frontier-index-v1',inputs=inputs,
                       packs={str(p):sha(p/'complete.json') for p in packs})
    if any(sha(p)!=h for p,h in inputs.items()):raise ValueError('Frontier capture sources changed')
    if args.index_output.exists():verify(args.index_output,expected_identity=identity(index_binding))
    else:write_index(args.index_output,packs,binding=index_binding)
    print(json.dumps(dict(pack=str(args.output),bytes=tree_bytes(args.output),index=str(args.index_output),
                          original_intervals_preserved=True,full_execution_coverage=False)))


if __name__=='__main__':main()
