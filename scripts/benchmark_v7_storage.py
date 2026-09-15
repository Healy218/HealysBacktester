"""Real-shard V7 storage/aggregation benchmark with correctness and thread reports.

Warm-cache read timings include consuming all values, not only opening a map.
No cold-cache or complete-build speedup claim is made.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def storage_trial(arguments):
    source, out, backend = arguments
    from nn_meta.v7.runtime import configure_threads
    runtime = configure_threads(1)
    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq
    from nn_meta.v7.storage import write_table, table_batches, write_matrix, open_matrix, verify, sha
    import hashlib
    import resource
    source, out = Path(source), Path(out)
    inp = pq.ParquetFile(source)
    columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    def batches():
        yield from inp.iter_batches(batch_size=32768, columns=columns)
    def arrays():
        for batch in batches():
            yield np.column_stack([c.to_numpy(zero_copy_only=False) for c in batch.columns]).astype('float64')
    expected = hashlib.sha256()
    for a in arrays():
        expected.update(a.tobytes())
    digest = sha(source)
    began = time.perf_counter()
    if backend in ('parquet', 'arrow'):
        write_table(out, batches(), schema=pa.schema([inp.schema_arrow.field(c) for c in columns]),
                    backend=backend, input_identity=digest)
    else:
        write_matrix(out, arrays(), shape=(inp.metadata.num_rows, len(columns)), dtype='float64',
                     backend=backend, input_identity=digest, chunk_rows=32768)
    write_seconds = time.perf_counter() - began
    began = time.perf_counter(); verify(out, expected_identity=digest)
    verified_seconds = time.perf_counter() - began
    matrix = open_matrix(out, expected_identity=digest) if backend in ('numpy', 'zarr') else None
    times = []
    for _ in range(3):
        actual = hashlib.sha256(); began = time.perf_counter()
        if matrix is None:
            for batch in table_batches(out, batch_size=32768):
                a = np.column_stack([c.to_numpy(zero_copy_only=False) for c in batch.columns]).astype('float64')
                actual.update(a.tobytes())
        else:
            for offset in range(0, matrix.shape[0], 32768):
                actual.update(np.asarray(matrix[offset:offset + 32768]).tobytes())
        times.append(time.perf_counter() - began)
        if actual.hexdigest() != expected.hexdigest():
            raise ValueError(f'{backend}: decoded numerical values differ')
    return {'backend': backend, 'rows': inp.metadata.num_rows, 'columns': columns,
        'write_and_commit_seconds': write_seconds, 'verify_seconds': verified_seconds,
        'warm_read_and_consume_seconds': times, 'bytes': sum(p.stat().st_size for p in out.rglob('*') if p.is_file()),
        'process_peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'numeric_sha256': expected.hexdigest(), 'runtime': runtime, 'equal': True}


def aggregation_trial(arguments):
    source, calendar_path = arguments
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import pandas as pd
    from nn_meta.v7.bars import aggregate_lazy
    calendar = json.loads(Path(calendar_path).read_text())
    frame = pd.read_parquet(source).set_index('timestamp')
    sessions = {s['date']: s for s in calendar['sessions']}
    columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    outputs = []
    for minutes in (1, 5, 15, 30):
        began = time.perf_counter()
        pieces = []
        # Reference includes the same session filtering, bar origin and full
        # bucket rule as the Polars path. Preserve genuine no-trade gaps.
        days = frame.index.tz_convert('America/New_York').strftime('%Y-%m-%d')
        for day, part in frame.groupby(days):
            if day not in sessions:
                continue
            s = sessions[day]
            opening = pd.Timestamp(day + ' ' + s['open'], tz='America/New_York').tz_convert('UTC')
            closing = pd.Timestamp(day + ' ' + s['close'], tz='America/New_York').tz_convert('UTC')
            part = part[(part.index >= opening) & (part.index + pd.Timedelta(minutes=1) <= closing)]
            grouped = part.resample(f'{minutes}min', origin=opening).agg(
                {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()
            pieces.append(grouped[grouped.index + pd.Timedelta(minutes=minutes) <= closing])
        reference = pd.concat(pieces)
        pandas_seconds = time.perf_counter() - began
        began = time.perf_counter()
        actual = aggregate_lazy([source], calendar, minutes).collect(engine='streaming').to_pandas().set_index('timestamp')
        polars_seconds = time.perf_counter() - began
        pd.testing.assert_frame_equal(actual[columns], reference, check_freq=False, rtol=1e-12, atol=1e-12)
        outputs.append({'minutes': minutes, 'rows': len(actual), 'pandas_transform_seconds': pandas_seconds,
                        'polars_read_transform_pandas_conversion_seconds': polars_seconds,
                        'buckets_with_unobserved_minutes': int((~actual.all_minutes_observed).sum()), 'equal': True})
    return outputs


def main():
    from nn_meta.v7.runtime import worker_pool
    from nn_meta.v7.storage import verify, sha
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--stock-receipt', type=Path, required=True)
    ap.add_argument('--calendar', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--workers', type=int, default=4)
    args = ap.parse_args()
    doc = json.loads(args.stock_receipt.read_text())
    if doc.get('complete') is not True or doc['task']['kind'] != 'stock':
        raise ValueError('Complete stock acquisition receipt required')
    for name, expected in doc['files'].items():
        if sha(args.stock_receipt.parent / name) != expected:
            raise ValueError('Stock source receipt hash mismatch')
    files = [args.stock_receipt.parent / n for n in doc['files'] if n.endswith('bars.parquet')]
    if len(files) != 1:
        raise ValueError('Expected one stock table')
    args.output.mkdir(parents=True, exist_ok=False)
    with worker_pool(args.workers, threads=1) as pool:
        trials = list(pool.map(storage_trial, [(str(files[0]), str(args.output / b), b)
                                              for b in ('parquet', 'arrow', 'numpy', 'zarr')]))
        aggregation = pool.submit(aggregation_trial, (str(files[0]), str(args.calendar))).result()
    report = {'schema': 'v7-storage-benchmark-v1', 'source_receipt_sha256': sha(args.stock_receipt),
        'storage': trials, 'aggregation': aggregation, 'workers': args.workers,
        'limitations': ['One real stock shard, not full option workload',
            'Warm cache; no OS page-cache eviction', 'Concurrent acquisition may affect timing',
            'Storage writes include integrity hashes and durable commit',
            'Pandas aggregation input preloaded; Polars includes read and pandas conversion',
            'No end-to-end freeze/build/training speedup established']}
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
