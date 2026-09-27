#!/usr/bin/env python3
"""Measure v2 lossless packs on the completed joined sample; no new downloads."""
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
    for name in ('forecast','plan','output','evidence'):
        p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args()
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    from nn_meta.v7.packed_quotes import PackedQuoteArchive
    from nn_meta.v7.packed_quotes_v2 import write_pack, PackedQuoteArchive as V2
    from nn_meta.v7.storage import verify,sha,identity,transaction,receipt
    from scripts.download_v7_data import save,quota_update,tree_bytes,TASK_RESERVATION
    from scripts.capture_v7_volume_sample import forecast,guard
    from scripts.validate_v7_adjacent_capture import same_records
    for name in ('forecast','plan','output','evidence'):
        setattr(args,name,getattr(args,name).resolve())
    budget=ROOT/'nn_meta/data_v7'
    if not args.output.is_relative_to(budget) or not args.evidence.is_relative_to(ROOT/'nn_meta/validation'):
        p.error('Use acquisition output and validation evidence')
    verify(args.forecast);verify(args.plan)
    prior=json.loads((args.forecast/'report.json').read_text())
    plan=json.loads((args.plan/'report.json').read_text())
    binding=dict(inputs={str(r/'complete.json'):sha(r/'complete.json') for r in (args.forecast,args.plan)},
        sources={str(r):sha(r) for r in (Path(__file__),ROOT/'nn_meta/v7/packed_quotes.py',ROOT/'nn_meta/v7/packed_quotes_v2.py',
            ROOT/'scripts/capture_v7_volume_sample.py',ROOT/'scripts/download_v7_data.py',ROOT/'nn_meta/v7/storage.py')})
    if args.evidence.exists():
        verify(args.evidence,expected_identity=identity(binding));print('Verified existing v2 forecast');return
    args.output.mkdir(parents=True,exist_ok=True)
    items={c['capture_id']:c for s in plan['samples'] for c in s['captures'].values()}
    measurements={};packs=[]
    for index,old in enumerate(prior['packs']):
        source=Path(old['pack'])
        doc=verify(source)
        if sha(source/'complete.json')!=next(iter(old['measurements'].values()))['pack_receipt_sha256']:
            raise ValueError('Source pack receipt drift')
        destination=args.output/f'{index:04d}'
        pack_binding=dict(parent=binding,source=str(source),source_sha256=sha(source/'complete.json'))
        with PackedQuoteArchive(source,cache_shards=1) as original:
            if not destination.exists():
                guard(plan,used_bytes=tree_bytes(args.output),pending=1,task_reservation=TASK_RESERVATION,
                    free_bytes=shutil.disk_usage(budget).free,quota=json.loads((budget/'quota.json').read_text()))
                key=uuid.uuid4().hex
                quota_update(budget,reserve=key)
                previous=set(destination.parent.glob(destination.name+'.partial-*'))
                try:
                    def entries():
                        for cid,contract,kind,start,end,raw_size,digest,blob in original.db.execute('SELECT * FROM captures ORDER BY capture_id'):
                            from nn_meta.v7.packed_quotes import decode
                            item=dict(capture_id=cid,contract=contract,kind=kind,start_ns=start,end_ns=end)
                            rows,manifest=decode(item,blob,raw_size,digest)
                            yield item,rows,manifest
                    write_pack(destination,entries(),binding=pack_binding)
                finally:
                    used=tree_bytes(destination) if destination.exists() else 0
                    used+=sum(tree_bytes(d) for d in destination.parent.glob(destination.name+'.partial-*') if d not in previous)
                    quota_update(budget,finish=(key,used))
            new=verify(destination,expected_identity=identity(pack_binding))
            total=tree_bytes(destination)
            overhead=total-sum(new['payload_bytes'].values())
            with V2(destination,cache_shards=1) as packed:
                for cid in old['measurements']:
                    item=items[cid]
                    scope=[item[k] for k in ('contract','kind','start_ns','end_ns')]
                    left,lm=original.window(*scope);right,rm=packed.window(*scope)
                    same_records(left,right)
                    if lm['records_sha256']!=rm['records_sha256']:
                        raise ValueError('V2 raw consumer parity failed')
                    payload=sum(new['payload_bytes'][s['capture_id']] for s in rm['derived_from_captures'])
                    measurements[cid]=dict(ok=True,rows=len(right),logical_bytes=payload+overhead/len(old['measurements']),
                        payload_bytes=payload,records_sha256=rm['records_sha256'],pack_receipt_sha256=sha(destination/'complete.json'))
            packs.append(dict(pack=str(destination),logical_bytes=total,overhead_bytes=overhead,source_pack=str(source)))
        if (index+1)%10==0:print(f'Verified lossless v2 packs {index+1}/{len(prior["packs"])}',flush=True)
    report=forecast(plan,measurements)
    report.update(schema='v7-joined-packed-v2-volume-forecast-v1',measurements=measurements,packs=packs,
        sample_captures=len(items),sample_records=sum(m['rows'] for m in measurements.values()),
        measured_pack_bytes=sum(r['logical_bytes'] for r in packs),measured_pack_overhead_bytes=sum(r['overhead_bytes'] for r in packs),
        population_captures=plan['population_captures'],raw_consumer_parity=True,provider_downloads=0,
        excludes='Additional pack routing/mappings, dated references, held execution paths, assembly and training arrays',
        research_ready=False,full_execution_coverage=False)
    for path,digest in {**binding['inputs'],**binding['sources']}.items():
        if sha(path)!=digest:raise ValueError('V2 repack parent changed')
    with transaction(args.evidence) as temp:
        save(temp/'binding.json',binding);save(temp/'report.json',report)
        receipt(temp,dict(identity=identity(binding),research_ready=False))
    print(json.dumps({k:v for k,v in report.items() if k not in ('packs','measurements','strata')}))


if __name__=='__main__':main()
