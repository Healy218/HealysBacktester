"""Calendar-aligned Polars aggregation; gaps are explicit, never synthesized."""
from __future__ import annotations

import pandas as pd


def session_table(calendar):
    import polars as pl
    if calendar.get('timezone') != 'America/New_York':
        raise ValueError('New York calendar required')
    days = [r['date'] for r in calendar['sessions']]
    if not days or days != sorted(set(days)):
        raise ValueError('Ordered unique calendar sessions required')
    return pl.DataFrame({'day': days,
        'open_ns': [pd.Timestamp(r['date'] + ' ' + r['open'], tz='America/New_York').value for r in calendar['sessions']],
        'close_ns': [pd.Timestamp(r['date'] + ' ' + r['close'], tz='America/New_York').value for r in calendar['sessions']]})


def aggregate_lazy(paths, calendar, minutes):
    import polars as pl
    frame = pl.scan_parquet([str(p) for p in paths]).select('timestamp', 'Open', 'High', 'Low', 'Close', 'Volume')
    return _aggregate(frame, calendar, minutes)


def aggregate_frame(raw, calendar, minutes):
    """Use the identical session/gap rules for an as-of in-memory raw view."""
    import polars as pl
    frame = raw.rename_axis('timestamp').reset_index()
    frame = pl.from_pandas(frame[['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']]).lazy()
    return _aggregate(frame, calendar, minutes).collect(engine='streaming').to_pandas().set_index('timestamp')


def _aggregate(frame, calendar, minutes):
    import polars as pl
    if type(minutes) is not int or minutes not in (1, 5, 15, 30):
        raise ValueError('Signal interval must be 1/5/15/30 minutes')
    interval = minutes * 60_000_000_000
    frame = frame.with_columns(pl.col('timestamp').dt.convert_time_zone('America/New_York').dt.strftime('%Y-%m-%d').alias('day'),
                               pl.col('timestamp').cast(pl.Int64).alias('stamp_ns'))
    # Raw pages are separately validated. Calendar coverage must be checked by
    # the caller; non-session and extended-hours observations are filtered here.
    frame = frame.join(session_table(calendar).lazy(), on='day', how='inner')
    frame = frame.filter((pl.col('stamp_ns') >= pl.col('open_ns')) &
                         (pl.col('stamp_ns') + 60_000_000_000 <= pl.col('close_ns')))
    frame = frame.with_columns((pl.col('open_ns') +
        ((pl.col('stamp_ns') - pl.col('open_ns')) // interval) * interval).alias('bucket_ns'))
    frame = frame.filter(pl.col('bucket_ns') + interval <= pl.col('close_ns')).sort('timestamp')
    grouped = frame.group_by('bucket_ns').agg(pl.col('Open').first(), pl.col('High').max(),
        pl.col('Low').min(), pl.col('Close').last(), pl.col('Volume').sum(),
        pl.len().cast(pl.UInt32).alias('observed_minutes'))
    return grouped.with_columns(
        pl.from_epoch('bucket_ns', time_unit='ns').dt.replace_time_zone('UTC').alias('timestamp'),
        pl.from_epoch(pl.col('bucket_ns') + interval, time_unit='ns').dt.replace_time_zone('UTC').alias('available_at'),
        pl.lit(minutes, dtype=pl.UInt32).alias('expected_minutes'),
        (pl.col('observed_minutes') == minutes).alias('all_minutes_observed')).drop('bucket_ns').sort('timestamp')


def write_bars(paths, calendar, minutes, destination):
    from nn_meta.v7.storage import transaction, receipt, identity, sha
    for path in paths:
        # Metadata check bounds calendar coverage before Polars' inner join.
        import pyarrow.parquet as pq
        source = pq.ParquetFile(path)
        for batch in source.iter_batches(columns=['timestamp'], batch_size=65536):
            stamps = batch.column(0).to_pandas().dt.tz_convert('America/New_York')
            if len(stamps) and (stamps.min().date().isoformat() < calendar['coverage_start'] or
                               stamps.max().date().isoformat() > calendar['coverage_end']):
                raise ValueError('Calendar does not cover source history')
    provenance = identity({'sources': {str(p): sha(p) for p in paths}, 'calendar': calendar,
                           'minutes': minutes, 'source_code': sha(__file__)})
    with transaction(destination) as temporary:
        aggregate_lazy(paths, calendar, minutes).sink_parquet(temporary / 'data.parquet',
            compression='zstd', row_group_size=65536, maintain_order=True, engine='streaming')
        receipt(temporary, {'backend': 'parquet', 'identity': provenance,
                            'format': 'v7-session-bars-v1', 'minutes': minutes,
                            'research_ready': False, 'gaps': 'observed counts; no synthetic bars'})
