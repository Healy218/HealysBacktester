import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.download_v7_data import (completed, digest, save, tasks, validate_bars,
                                     quota_update, TASK_RESERVATION, CapacityPause, tree_bytes)


def bar(t='2022-03-07T14:30:00Z'):
    return {'t': t, 'o': 100., 'h': 102., 'l': 99., 'c': 101., 'v': 20}


def test_year_shards_respect_dst_and_inclusive_end_date():
    jobs = list(tasks(['SPY'], [], '2022-03-07', '2022-09-14', ['stock']))
    assert len(jobs) == 2
    assert jobs[0]['start'] == '2022-03-07T00:00:00-05:00'
    assert jobs[0]['end'] == '2022-09-15T00:00:00-04:00'


def test_validate_pages_does_not_silently_drop_conflicting_duplicates():
    table, prev = validate_bars([bar()], '2022-03-07T00:00:00Z', '2022-03-08T00:00:00Z')
    assert table.num_rows == 1
    with pytest.raises(ValueError, match='duplicate'):
        validate_bars([bar()], '2022-03-07T00:00:00Z', '2022-03-08T00:00:00Z', prev)


@pytest.mark.parametrize('change', [{'h': 99}, {'v': -1}, {'o': float('nan')}, {'t': '2022-03-07T14:30:01Z'}])
def test_invalid_bars_rejected(change):
    with pytest.raises(ValueError):
        validate_bars([{**bar(), **change}], '2022-03-07T00:00:00Z', '2022-03-08T00:00:00Z')


def test_receipt_binds_request_and_raw_bytes(tmp_path):
    task = {'key': 'example', 'kind': 'stock'}
    d = tmp_path / 'example'; d.mkdir(); p = d / 'raw'; p.write_bytes(b'original')
    save(d / 'complete.json', {'task': task, 'complete': True, 'files': {'raw': digest(p)}})
    assert completed(tmp_path, task)['complete']
    p.write_bytes(b'changed')
    with pytest.raises(RuntimeError, match='hash mismatch'):
        completed(tmp_path, task)


def test_capacity_is_reserved_before_writes_and_partial_bytes_remain_charged(tmp_path):
    quota_update(tmp_path, initialize=TASK_RESERVATION * 2)
    quota_update(tmp_path, reserve='first')
    with pytest.raises(CapacityPause):
        quota_update(tmp_path, reserve='second')
    quota_update(tmp_path, finish=('first', 1234))
    doc = quota_update(tmp_path, reserve='second')
    assert doc['used_bytes'] >= 1234
    assert doc['reservations'] == {'second': TASK_RESERVATION}


def test_hardlinked_reuse_does_not_double_count_storage(tmp_path):
    import os
    p = tmp_path / 'one'; p.write_bytes(b'1234567')
    os.link(p, tmp_path / 'two')
    assert tree_bytes(tmp_path) == 7
