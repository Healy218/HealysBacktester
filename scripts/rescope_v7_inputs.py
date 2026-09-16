"""Create verified V7 working inputs with the user-deleted dates removed.

Original provider captures remain historical evidence. The output is explicitly
labelled derived, so acquisition cannot silently reuse it as a provider capture.
"""
from pathlib import Path
import argparse
import json
import os
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def stock(payload):
    source, output, quota_root = map(Path, payload)
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import pandas as pd
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    from nn_meta.v7.scope import declaration, EXCLUDED_START, EXCLUDED_END
    from nn_meta.v7.storage import sha, identity, receipt, transaction
    from scripts.download_v7_data import quota_update, tree_bytes
    before = sha(source)
    doc = json.loads(source.read_text())
    task = doc['task']
    if not doc.get('complete') or task['kind'] != 'stock':
        raise ValueError('Completed stock capture required')
    names = [n for n in doc['files'] if n.endswith('bars.parquet')]
    if len(names) != 1:
        raise ValueError('Exactly one captured stock table required')
    raw = source.parent / names[0]
    if sha(raw) != doc['files'][names[0]]:
        raise ValueError('Original stock hash mismatch')
    destination = output / task['key']
    if destination.exists():
        from nn_meta.v7.storage import verify
        saved = verify(destination)
        if saved.get('source_receipt_sha256') != before or saved.get('scope') != declaration():
            raise ValueError('Resume source/scope changed')
        return {'key': task['key'], 'rows': saved['rows'], 'removed_rows': saved['removed_rows']}
    reservation = uuid.uuid4().hex
    quota_update(quota_root, reserve=reservation)
    consumed = 0
    try:
        with transaction(destination) as temp:
            try:
                table = pq.ParquetFile(raw)
                if table.metadata.num_rows != doc['rows']:
                    raise ValueError('Source row count mismatch')
                count = 0
                if source.parent.name == '2022':
                    begin = pd.Timestamp(EXCLUDED_START, tz='America/New_York').value
                    stop = (pd.Timestamp(EXCLUDED_END, tz='America/New_York') + pd.DateOffset(days=1)).value
                    with pq.ParquetWriter(temp/'bars.parquet', table.schema_arrow, compression='zstd') as writer:
                        for batch in table.iter_batches(batch_size=65536):
                            stamps = batch.column(batch.schema.get_field_index('timestamp'))
                            if not pa.types.is_timestamp(stamps.type) or stamps.type.tz is None:
                                raise ValueError('Aware timestamps required')
                            ns = pc.cast(pc.cast(stamps, pa.timestamp('ns', tz='UTC')), pa.int64())
                            keep = pc.or_(pc.less(ns, begin), pc.greater_equal(ns, stop))
                            filtered = pa.Table.from_batches([batch]).filter(keep)
                            writer.write_table(filtered); count += len(filtered)
                else:
                    os.link(raw, temp/'bars.parquet')
                    count = table.metadata.num_rows
                if sha(source) != before or sha(raw) != doc['files'][names[0]]:
                    raise ValueError('Source changed during derivation')
                metadata = {'task': {**task, 'derived_scope': identity(declaration())},
                    'format': 'v7-date-filtered-stock-v1', 'scope': declaration(),
                    'source_receipt': str(source), 'source_receipt_sha256': before,
                    'source_table_sha256': doc['files'][names[0]], 'rows': count,
                    'removed_rows': doc['rows']-count, 'coverage_validated': False,
                    'research_ready': False}
                receipt(temp, metadata)
            finally:
                consumed = sum(p.stat().st_size for p in temp.rglob('*')
                               if p.is_file() and p.stat().st_nlink == 1)
    finally:
        quota_update(quota_root, finish=(reservation, consumed))
    return {'key': task['key'], 'rows': count, 'removed_rows': doc['rows']-count}


def link_receipt(source, destination):
    from nn_meta.v7.storage import verify
    doc = verify(source)
    if destination.exists():
        if verify(destination) != doc:
            raise ValueError('Resume linked input differs')
        return
    destination.mkdir(parents=True)
    for name in [*doc['files'], 'complete.json']:
        target = destination/name; target.parent.mkdir(parents=True, exist_ok=True)
        os.link(source/name, target)


def main():
    from nn_meta.v7.runtime import configure_threads, worker_pool
    configure_threads(1)
    from nn_meta.v7.scope import declaration, data_day_allowed
    from nn_meta.v7.storage import sha
    from scripts.download_v7_data import save
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--stock-source', type=Path, action='append', required=True,
                    help='Sources in ascending precedence; overlaps require --replace')
    ap.add_argument('--replace', action='append', default=[], help='Explicit SYMBOL:YEAR replacement')
    for name in ('base','audit','output','quota-root'):
        ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--workers',type=int,required=True)
    args=ap.parse_args()
    if args.output.parent.resolve()!=args.quota_root.resolve():
        raise ValueError('Working inputs must share the acquisition quota root')
    inputs={}
    for root in args.stock_source:
        for path in sorted(root.glob('stock_1m/*/*/*/complete.json')):
            key=str(path.parent.relative_to(root))
            if key in inputs and f'{path.parents[1].name}:{path.parent.name}' not in args.replace:
                raise ValueError('Duplicate source requires explicit replacement: '+key)
            inputs[key]=path
    args.output.mkdir(parents=True,exist_ok=True)
    calendar=args.base/'calendar.json'
    target=args.output/'calendar.json'
    if not target.exists(): os.link(calendar,target)
    elif sha(target)!=sha(calendar): raise ValueError('Calendar changed')
    scope=declaration()
    save(args.output/'scope.json',scope)
    reports=[]
    with worker_pool(args.workers,threads=1) as pool:
        for result in pool.map(stock,[(str(p),str(args.output),str(args.quota_root)) for p in inputs.values()]):
            reports.append(result)
            if len(reports)%100==0:
                print(json.dumps({'stock_shards':len(reports),'total':len(inputs),
                                  'removed_rows':sum(r['removed_rows'] for r in reports)}),flush=True)
    days=[]; removed=[]
    for source in sorted((args.base/'options/day_aggs').iterdir()):
        day=source.name
        if len(day)!=10 or not (source/'complete.json').exists(): continue
        if not data_day_allowed(day): removed.append(day); continue
        link_receipt(source,args.output/'options/day_aggs'/day)
        link_receipt(args.audit/'options'/day,args.output/'audit/options'/day)
        days.append(day)
    report={'scope':scope,'stock_shards':len(reports),
            'stock_rows':sum(r['rows'] for r in reports),'removed_stock_rows':sum(r['removed_rows'] for r in reports),
            'option_days':len(days),'removed_option_days':removed,'calendar_sha256':sha(calendar),
            'sources':[str(p) for p in args.stock_source],'replacement_keys':args.replace,
            'stock_reports':reports,'research_ready':False,
            'original_captures':'historical only; not active working inputs'}
    save(args.output/'report.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='stock_reports'}),flush=True)


if __name__=='__main__': main()
