import gzip
import hashlib
import json

import pytest

from nn_meta.v7.quote_archive import QuoteArchive
from nn_meta.v7.quotes import capture_union
from nn_meta.v7.storage import receipt
from nn_meta.v7.execution import QuoteUnavailable
from options.data.massive_ticks import canonical_bytes


CONTRACT = 'SPY220311C00420000'


def archive_at(root, intervals, *, omitted=()):
    root.mkdir()
    plan = capture_union([{'request_id': str(i), 'contract': CONTRACT, 'kind': 'quotes',
                          'start_ns': lo, 'end_ns': hi} for i, (lo, hi) in enumerate(intervals)],
                         max_span_ns=10)
    (root / 'requests.json').write_text(json.dumps(plan))
    for i, capture in enumerate(plan['captures']):
        if i in omitted:
            continue
        directory = root / capture['capture_id']
        directory.mkdir()
        records = [{'sip_timestamp': capture['start_ns'], 'bid_price': 1., 'ask_price': 1.1,
                    'bid_size': 2, 'ask_size': 2}]
        manifest = {'schema': 'massive-option-ticks-v1', 'provider': 'massive', 'contract': 'O:' + CONTRACT,
                    'kind': 'quotes', 'start_ns': capture['start_ns'], 'end_ns': capture['end_ns'],
                    'complete': True, 'records': 1,
                    'records_sha256': hashlib.sha256(canonical_bytes(records)).hexdigest()}
        (directory / 'records.json.gz').write_bytes(gzip.compress(canonical_bytes(records)))
        (directory / 'capture.json').write_bytes(canonical_bytes(manifest))
        receipt(directory, {'identity': capture['capture_id'], 'capture': capture})
    return QuoteArchive(root, cache_shards=1)


def test_adjacent_shards_cover_exact_window_and_detach_cached_rows(tmp_path):
    archive = archive_at(tmp_path / 'a', [(0, 30)])
    rows, manifest = archive.window(CONTRACT, 'quotes', 5, 25)
    assert [r['sip_timestamp'] for r in rows] == [10, 20]
    assert manifest['complete'] and len(manifest['derived_from_captures']) == 3
    assert len(archive.cache) == 1
    rows[0]['bid_price'] = 1000.
    assert archive.window(CONTRACT, 'quotes', 5, 25)[0][0]['bid_price'] == 1.


@pytest.mark.parametrize('intervals,omitted', [([(0, 10), (20, 30)], ()), ([(0, 30)], (1,))])
def test_missing_shard_and_uncaptured_gap_are_not_empty_markets(tmp_path, intervals, omitted):
    archive = archive_at(tmp_path / 'a', intervals, omitted=omitted)
    with pytest.raises(QuoteUnavailable):
        archive.window(CONTRACT, 'quotes', 5, 25)


def test_modified_quote_bytes_fail_hash_verification(tmp_path):
    archive = archive_at(tmp_path / 'a', [(0, 10)])
    path = next((tmp_path / 'a').glob('*/records.json.gz'))
    path.write_bytes(gzip.compress(b'[]'))
    with pytest.raises(ValueError):
        archive.window(CONTRACT, 'quotes', 0, 10)
