import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from nn_meta.v7.compact_proposals import SCHEMA
from scripts.forecast_v7_entry_demand import count_decisions


def save(path, keys):
    rows = [dict(variant_index=i, decision_ns=clock, exit_decision_ns=clock + 1,
                 censored_ns=None, is_put=put, bars_since_previous_signal=1,
                 symbol=symbol, exit_stock_ticker=symbol)
            for i, (symbol, clock, put) in enumerate(keys)]
    pq.write_table(pa.Table.from_pylist(rows, schema=SCHEMA), path)


def test_exact_decision_census_deduplicates_variants_but_preserves_symbol_and_right(tmp_path):
    a, b = tmp_path / 'a.parquet', tmp_path / 'b.parquet'
    save(a, [('OLD', 100, False), ('OLD', 100, False), ('OLD', 100, True)])
    save(b, [('OLD', 100, False), ('NEW', 100, False), ('NEW', 200, True)])
    actual, rows = count_decisions([a, b], 6)
    assert rows == 6
    assert {k: v.tolist() for k, v in actual.items()} == {'OLD': [200, 201], 'NEW': [200, 401]}
    with pytest.raises(ValueError, match='census changed'):
        count_decisions([a, b], 5)


def test_census_preserves_empty_security_and_rejects_invalid_clock_or_schema(tmp_path):
    empty = tmp_path / 'empty.parquet'
    save(empty, [])
    assert count_decisions([empty], 0) == ({}, 0)
    for clock in (0, -1, np.iinfo(np.int64).max // 2 + 1):
        path = tmp_path / f'{clock}.parquet'
        save(path, [('X', int(clock), False)])
        with pytest.raises(ValueError, match='encoding range'):
            count_decisions([path], 1)
    bad = tmp_path / 'foreign.parquet'
    pq.write_table(pa.table({'decision_ns': [100]}), bad)
    with pytest.raises(ValueError, match='schema'):
        count_decisions([bad], 1)
