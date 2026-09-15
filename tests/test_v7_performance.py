import json

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from nn_meta.v7.storage import (write_table, table_batches, verify, write_matrix, open_matrix)
from nn_meta.v7.quotes import capture_union
from nn_meta.v7.signals import SharedIndicators, ma_batches


@pytest.mark.parametrize('backend', ['parquet', 'arrow'])
def test_table_storage_preserves_nulls_schema_and_small_batches(tmp_path, backend):
    table = pa.table({'t': pa.array([1, 2, 3], type=pa.int64()), 'v': [1., None, 3.]})
    dest = tmp_path / backend
    write_table(dest, table.to_batches(max_chunksize=2), schema=table.schema,
                backend=backend, input_identity='source-a')
    verify(dest, expected_identity='source-a')
    assert pa.Table.from_batches(list(table_batches(dest, batch_size=1))).equals(table)
    with pytest.raises(FileExistsError):
        write_table(dest, [], schema=table.schema, backend=backend, input_identity='source-a')
    with pytest.raises(ValueError, match='identity'):
        verify(dest, expected_identity='source-b')


@pytest.mark.parametrize('backend', ['numpy', 'zarr'])
def test_matrix_storage_is_readonly_and_preserves_dtype_and_nan(tmp_path, backend):
    x = np.array([[1., np.nan], [3., 4.], [5., 6.]])
    dest = tmp_path / backend
    write_matrix(dest, [x[:2], x[2:]], shape=x.shape, dtype=x.dtype, backend=backend,
                 input_identity='fold-training-only', chunk_rows=2)
    loaded = open_matrix(dest, expected_identity='fold-training-only')
    np.testing.assert_equal(loaded[:], x)
    with pytest.raises((ValueError, PermissionError)):
        loaded[0, 0] = 7


def test_incomplete_array_never_commits(tmp_path):
    with pytest.raises(ValueError, match='Incomplete'):
        write_matrix(tmp_path / 'bad', [np.ones((1, 2))], shape=(2, 2), dtype='float64',
                     backend='numpy', input_identity='x')
    assert not (tmp_path / 'bad').exists()


def request(name, lo, hi, kind='quotes'):
    return {'request_id': name, 'contract': 'SPY220311C00420000', 'kind': kind,
            'start_ns': lo, 'end_ns': hi}


def test_quote_union_preserves_memberships_and_does_not_merge_gaps_or_kinds():
    rows = [request('a', 1, 7), request('b', 5, 12), request('c', 15, 17), request('t', 1, 7, 'trades')]
    plan = capture_union(rows, max_span_ns=10)
    assert plan == capture_union(list(reversed(rows)), max_span_ns=10)
    by_id = {c['capture_id']: c for c in plan['captures']}
    for row in rows:
        captures = [by_id[k] for k in plan['request_captures'][row['request_id']]]
        actual = {n for c in captures for n in range(max(c['start_ns'], row['start_ns']), min(c['end_ns'], row['end_ns']))}
        assert actual == set(range(row['start_ns'], row['end_ns']))
        assert all(c['kind'] == row['kind'] and c['end_ns'] - c['start_ns'] <= 10 for c in captures)
    assert not any(c['start_ns'] < 14 < c['end_ns'] for c in plan['captures'])


def test_conflicting_request_id_rejected():
    with pytest.raises(ValueError, match='Conflicting'):
        capture_union([request('a', 1, 2), request('a', 2, 3)])


def test_shared_ma_matches_vectorbt_and_batch_size_without_recomputing():
    from signals.ma_crossover import generate_ma_signals
    close = pd.Series([1., 2., 2., 1., 1., 3., 3., 2., 5., 1.] * 10,
                      index=pd.date_range('2022-03-07', periods=100, freq='min'))
    variants = [{'strategy': 'ma', 'signal_minutes': 1, 'variant_id': str(i),
                 'params': {'fast_window': f, 'slow_window': s}}
                for i, (f, s) in enumerate([(2, 4), (2, 6), (4, 6)])]
    shared = SharedIndicators(close)
    outputs = [list(ma_batches(shared, variants, batch_columns=n)) for n in (1, 3)]
    assert shared.computations == 1
    reference = generate_ma_signals(close, np.array([2, 4, 6]), enable_shorting=True)
    for batches in outputs:
        for channel in range(4):
            result = pd.concat([frames[channel] for _, frames in batches], axis=1)
            np.testing.assert_array_equal(result.to_numpy(), reference[channel].to_numpy())


@pytest.mark.parametrize('minutes', [1, 5, 15, 30])
def test_polars_session_bars_align_close_availability_and_expose_gaps(tmp_path, minutes):
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    from nn_meta.v7.bars import aggregate_lazy
    idx = pd.date_range('2022-03-14T13:30:00Z', periods=60, freq='min').delete(7)
    frame = pd.DataFrame({'timestamp': idx, 'Open': 1., 'High': 3., 'Low': .5, 'Close': 2., 'Volume': 1.})
    path = tmp_path / 'bars.parquet'; frame.to_parquet(path, index=False)
    cal = {'timezone': 'America/New_York', 'sessions': [{'date': '2022-03-14', 'open': '09:30', 'close': '10:30'}]}
    got = aggregate_lazy([path], cal, minutes).collect(engine='streaming').to_pandas().set_index('timestamp')
    ref = frame.set_index('timestamp').resample(f'{minutes}min', origin=pd.Timestamp('2022-03-14T13:30:00Z')).agg(
        {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()
    pd.testing.assert_frame_equal(got[list(ref.columns)], ref, check_freq=False)
    assert ((got.available_at - got.index) == pd.Timedelta(minutes=minutes)).all()
    if minutes > 1:
        assert (~got.all_minutes_observed).sum() == 1
