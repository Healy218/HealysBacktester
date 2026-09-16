"""All-variant V7 signal/feature pilot with original warmup and explicit censoring."""
from pathlib import Path
import argparse
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run_one(arguments):
    source, calendar_path, symbol, start, end, output, minutes = arguments
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import time
    import resource
    import numpy as np
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    from nn_meta.v7.bars import aggregate_lazy
    from nn_meta.v7.context import chart_context
    from nn_meta.v7.features import source_frames, project, technical
    from nn_meta.v7.signals import signal_batches
    from nn_meta.v7.storage import transaction, receipt, identity, sha
    from nn_meta.v7.coverage import receipt_frame
    from nn_meta.multitimeframe_catalog import registered_catalog
    import polars as pl
    began = time.perf_counter()
    source, output = Path(source), Path(output)
    calendar = json.loads(Path(calendar_path).read_text())
    paths, hashes = {}, {}
    for basis in ('raw', 'all'):
        paths[basis] = []
        for year in range(2021, int(end[:4]) + 1):
            path = source / 'stock_1m' / basis / symbol / str(year) / 'complete.json'
            doc, frame = receipt_frame(source, path)
            del frame
            hashes[str(path)] = sha(path)
            paths[basis].extend(path.parent / n for n in doc['files'] if n.endswith('bars.parquet'))
    from nn_meta.v7.scope import HISTORY_START
    stop = pd.Timestamp(end, tz='America/New_York') + pd.DateOffset(days=1)
    begin = pd.Timestamp(start, tz='America/New_York')
    feature_begin = pd.Timestamp(HISTORY_START, tz='America/New_York').value
    def bars_at(basis, interval):
        return aggregate_lazy(paths[basis], calendar, interval).filter(
            (pl.col('timestamp').cast(pl.Int64) >= feature_begin) &
            (pl.col('timestamp').cast(pl.Int64) < stop.value)).collect(engine='streaming').to_pandas().set_index('timestamp')
    minute = bars_at('all', 1)
    bars = minute if minutes == 1 else bars_at('all', minutes)
    raw = bars_at('raw', minutes)
    if not raw.index.equals(bars.index):
        raise ValueError('Raw/adjusted chart timestamps differ')
    context = chart_context(bars, minute, calendar, minutes)
    observed = bars.index[bars.index >= begin]
    frames = source_frames(bars, context, observation_index=observed)
    projected = project(bars, frames, context)
    tech = technical(bars, context).loc[observed]
    variants = [r for r in registered_catalog([symbol])['records'] if r['signal_minutes'] == minutes]
    schema = pa.schema([('bar_at', pa.timestamp('ns', tz='UTC')),
                        ('decision_at', pa.timestamp('ns', tz='UTC')),
                        ('variant_id', pa.string()), ('event', pa.int8()), ('raw_spot', pa.float64())])
    counts = [0] * 4
    with transaction(output) as temp:
        with pq.ParquetWriter(temp / 'events.parquet', schema, compression='zstd') as writer:
            for records, channels in signal_batches(bars, variants, sources=frames, batch_columns=16):
                ids = np.asarray([r['variant_id'] for r in records])
                for kind, channel in enumerate(channels):
                    selected = channel.loc[observed]
                    row, col = np.nonzero(selected.to_numpy())
                    counts[kind] += len(row)
                    for first in range(0, len(row), 65536):
                        pos = row[first:first + 65536]
                        times = observed[pos]
                        writer.write_table(pa.Table.from_arrays([
                            pa.array(times, type=schema.field(0).type),
                            pa.array(times + pd.Timedelta(minutes=minutes), type=schema.field(1).type),
                            pa.array(ids[col[first:first + 65536]]),
                            pa.array(np.full(len(pos), kind, dtype='int8')),
                            pa.array(raw.Close.loc[times])], schema=schema))
        projected.to_parquet(temp / 'tv_features.parquet')
        tech.to_parquet(temp / 'technical_features.parquet')
        raw.loc[observed].to_parquet(temp / 'raw_bars.parquet')
        report = {'symbol': symbol, 'start': start, 'end': end, 'minutes': minutes,
                  'warmup_and_signal_bars': len(bars), 'observed_bars': len(observed),
                  'variants': len(variants), 'families': len({r['strategy'] for r in variants}),
                  'events_by_channel': counts, 'tv_features': projected.shape[1],
                  'technical_features': tech.shape[1], 'seconds': time.perf_counter() - began,
                  'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  'research_ready': False, 'full_feature_suite': False,
                  'price_vintage_verified': False, 'execution_labels_complete': False}
        (temp / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        receipt(temp, {'identity': identity({'stock': hashes, 'calendar': sha(calendar_path),
                    'variants': variants, 'scope': [start, end],
                    'v7_source': {p.name: sha(p) for p in (ROOT / 'nn_meta/v7').glob('*.py')},
                    'runner': sha(__file__)}), 'research_ready': False})
    return report


def main():
    from nn_meta.v7.runtime import worker_pool
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'calendar', 'output'):
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--symbol', required=True)
    ap.add_argument('--start', required=True)
    ap.add_argument('--end', required=True)
    ap.add_argument('--workers', type=int, required=True)
    args = ap.parse_args()
    from nn_meta.v7.scope import require_active_inputs, require_research_window
    require_active_inputs(args.source)
    require_research_window(args.start, args.end)
    args.output.mkdir(parents=True, exist_ok=False)
    with worker_pool(args.workers, threads=1) as pool:
        reports = list(pool.map(run_one, [(str(args.source), str(args.calendar), args.symbol,
                          args.start, args.end, str(args.output / str(m)), m) for m in (1, 5, 15, 30)]))
    (args.output / 'report.json').write_text(json.dumps(reports, indent=2) + '\n')
    print(json.dumps(reports, indent=2))


if __name__ == '__main__':
    main()
