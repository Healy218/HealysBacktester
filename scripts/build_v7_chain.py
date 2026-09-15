"""Build immutable observed-first contract catalog from verified V7 daily captures."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import polars as pl
    import pyarrow.parquet as pq
    import shutil
    import time
    from nn_meta.v7.storage import transaction,receipt,verify,sha,identity
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--audit',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--partitions', type=int, default=64)
    args=ap.parse_args()
    if not 16 <= args.partitions <= 256:
        raise ValueError('Use 16–256 bounded disk partitions')
    began = time.perf_counter()
    paths=sorted((args.audit/'options').glob('*/contracts.parquet'));sources={}
    for path in paths:verify(path.parent);sources[str(path)]=sha(path)
    with transaction(args.output) as temp:
        parts = temp / 'grouping-parts'
        parts.mkdir()
        writers = {}
        try:
            for number, path in enumerate(paths):
                for batch in pq.ParquetFile(path).iter_batches(columns=['ticker', 'window_start'], batch_size=131072):
                    frame = pl.from_arrow(batch).filter(pl.col('ticker').str.contains(r'^O:[A-Z]+\d{6}[CP]\d{8}$'))
                    frame = frame.with_columns((pl.col('ticker').hash(seed=7) % args.partitions).alias('part'))
                    for key, block in frame.partition_by('part', as_dict=True).items():
                        part = int(key[0])
                        table = block.drop('part').to_arrow()
                        if part not in writers:
                            writers[part] = pq.ParquetWriter(parts / f'{part:03d}.parquet', table.schema, compression='zstd')
                        writers[part].write_table(table)
                if number % 100 == 0:
                    print(json.dumps({'partitioned_days': number + 1, 'total': len(paths)}), flush=True)
        finally:
            for writer in writers.values():
                writer.close()
        output_writer = None
        count, roots = 0, set()
        try:
            for path in sorted(parts.glob('*.parquet')):
                frame = pl.scan_parquet(path).group_by('ticker').agg(
                    pl.col('window_start').min().alias('first_seen_ns')).collect(engine='streaming')
                frame = frame.with_columns(pl.col('ticker').str.extract(r'^O:([A-Z]+)',1).alias('root'),
                    pl.col('ticker').str.slice(-15,6).str.strptime(pl.Date,format='%y%m%d').alias('expiry'),
                    pl.col('ticker').str.slice(-9,1).alias('right'),
                    (pl.col('ticker').str.slice(-8).cast(pl.Float64)/1000).alias('strike'),
                    pl.from_epoch('first_seen_ns',time_unit='ns').dt.replace_time_zone('UTC').dt.convert_time_zone('America/New_York').dt.date().alias('first_seen')).sort('root','ticker')
                roots.update(frame['root'].unique().to_list())
                count += frame.height
                table = frame.to_arrow()
                if output_writer is None:
                    output_writer = pq.ParquetWriter(temp/'contracts.parquet', table.schema, compression='zstd')
                output_writer.write_table(table, row_group_size=100000)
        finally:
            if output_writer is not None:
                output_writer.close()
        if output_writer is None:
            raise ValueError('No observed standard-root contracts')
        # Only this invocation's derived grouping files; original captures and
        # any failed earlier transactions remain intact.
        shutil.rmtree(parts)
        report={'contracts':count,'roots':len(roots),'sessions':len(paths),
                'partitions':args.partitions,'seconds':time.perf_counter()-began,
                'research_ready':False,'selection':'observed by previous date; no current-day admission',
                'standard_deliverables_verified':False}
        (temp/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        receipt(temp,{'identity':identity({'sources':sources,'code':sha(__file__)}),'research_ready':False})
    print(json.dumps(report))


if __name__=='__main__':main()
