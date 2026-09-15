"""V7 working-set pilot: Polars bars, shared indicators, streamed Arrow/Parquet signals.

This exercises performance paths; it does not build full-feature option labels.
Only the independently tested MA adapter is admitted by this initial runner.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def build_one(args):
    source, calendar_path, output, minutes, table_backend, matrix_backend, variant_limit = args
    from nn_meta.v7.runtime import configure_threads
    runtime = configure_threads(1)
    from nn_meta.v7.bars import write_bars
    from nn_meta.v7.signals import SharedIndicators, ma_batches
    from nn_meta.v7.storage import write_table, write_matrix, sha, identity
    from nn_meta.multitimeframe_catalog import registered_catalog
    import numpy as np
    import pandas as pd
    import pyarrow as pa
    import resource
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    calendar = json.loads(Path(calendar_path).read_text())
    began = time.perf_counter()
    write_bars([Path(source)], calendar, minutes, output / 'bars')
    bars_seconds = time.perf_counter() - began
    bars = pd.read_parquet(output / 'bars/data.parquet').set_index('timestamp')
    shared = SharedIndicators(bars.Close)
    variants = [r for r in registered_catalog(['REFERENCE'])['records']
                if r['strategy'] == 'ma' and r['signal_minutes'] == minutes]
    if variant_limit:
        variants = variants[:variant_limit]
    fingerprint = identity({'stock': sha(source), 'calendar': sha(calendar_path),
        'minutes': minutes, 'variants': variants, 'source': sha(__file__),
        'signal_adapter': sha(ROOT / 'nn_meta/v7/signals.py')})
    schema = pa.schema([('timestamp', pa.timestamp('ns', tz='UTC')),
                        ('available_at', pa.timestamp('ns', tz='UTC')),
                        ('variant_id', pa.string()), ('event', pa.int8())])
    emitted = 0
    def event_batches():
        nonlocal emitted
        for records, channels in ma_batches(shared, variants):
            ids = np.array([r['variant_id'] for r in records])
            for event, channel in enumerate(channels):
                row, column = np.nonzero(channel.to_numpy())
                # Bound serialization separately from signal-matrix batches.
                for start in range(0, len(row), 65536):
                    pos = row[start:start + 65536]; cols = column[start:start + 65536]
                    emitted += len(pos)
                    yield pa.Table.from_arrays([pa.array(bars.index[pos], type=schema.field(0).type),
                        pa.array(bars.index[pos] + pd.Timedelta(minutes=minutes), type=schema.field(1).type),
                        pa.array(ids[cols]), pa.array(np.full(len(pos), event, dtype='int8'))], schema=schema)
    began = time.perf_counter()
    write_table(output / 'signals', event_batches(), schema=schema, backend=table_backend, input_identity=fingerprint)
    signal_seconds = time.perf_counter() - began
    # Persist shared numerical inputs for read-only reuse by later workers.
    averages = shared.moving_averages([r['params'][k] for r in variants for k in ('fast_window', 'slow_window')])
    began = time.perf_counter()
    write_matrix(output / 'shared_ma', (averages.iloc[i:i + 32768].to_numpy(dtype='float64')
                 for i in range(0, len(averages), 32768)), shape=averages.shape, dtype='float64',
                 backend=matrix_backend, input_identity=fingerprint, columns=list(averages.columns))
    result = {'minutes': minutes, 'bars': len(bars), 'variants': len(variants), 'events': emitted,
        'indicator_computations': shared.computations, 'bars_seconds': bars_seconds,
        'signals_and_commit_seconds': signal_seconds, 'shared_matrix_seconds': time.perf_counter() - began,
        'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'buckets_with_unobserved_minutes': int((~bars.all_minutes_observed).sum()),
        'research_ready': False, 'runtime': runtime}
    (output / 'performance.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    from nn_meta.v7.runtime import worker_pool
    from nn_meta.v7.storage import sha
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--stock-receipt', type=Path, required=True)
    ap.add_argument('--calendar', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--table-backend', choices=['parquet', 'arrow'], default='parquet')
    ap.add_argument('--matrix-backend', choices=['numpy', 'zarr'], default='numpy')
    ap.add_argument('--workers', type=int, required=True)
    ap.add_argument('--pilot-variants', type=int, help='Explicit performance-pilot subset; omitted evaluates all MA variants')
    args = ap.parse_args()
    if args.pilot_variants is not None and args.pilot_variants < 1:
        ap.error('Positive pilot count required')
    doc = json.loads(args.stock_receipt.read_text())
    if doc.get('complete') is not True or doc['task']['kind'] != 'stock' or doc['task']['adjustment'] != 'all':
        raise ValueError('Complete adjusted-minute capture receipt required')
    for name, expected in doc['files'].items():
        if sha(args.stock_receipt.parent / name) != expected:
            raise ValueError('Stock receipt hash mismatch')
    sources = [args.stock_receipt.parent / n for n in doc['files'] if n.endswith('bars.parquet')]
    if len(sources) != 1:
        raise ValueError('Expected one verified stock shard')
    args.output.mkdir(parents=True, exist_ok=False)
    with worker_pool(args.workers, threads=1) as pool:
        results = list(pool.map(build_one, [(str(sources[0]), str(args.calendar), str(args.output / str(m)), m,
            args.table_backend, args.matrix_backend, args.pilot_variants) for m in (1, 5, 15, 30)]))
    report = {'schema': 'v7-working-set-pilot-v1', 'source_receipt_sha256': sha(args.stock_receipt),
        'results': results, 'ready_for_build': False, 'table_backend': args.table_backend,
        'matrix_backend': args.matrix_backend, 'scope': 'MA working-set pilot; no full-feature option labels'}
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
