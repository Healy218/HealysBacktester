import pytest

from nn_meta.v7.storage import identity
from scripts.audit_v7_capture_union import census


def row(start, end, kind='quotes'):
    scope = dict(contract='AAPL260918C00200000', kind=kind, start_ns=start, end_ns=end)
    return identity(scope), scope['contract'], '2026-09-14', kind, start, end


def test_full_union_deduplicates_cross_security_requests_and_preserves_kind():
    rows = [row(10, 20), row(10, 20), row(15, 30), row(10, 20, 'trades')]
    result = census(rows)
    assert result['input_requests'] == 4
    assert result['unique_requests'] == 3
    assert result['captures'] == 2
    assert result['contracts'] == result['contract_days'] == 1
    assert result['union_seconds_by_kind'] == {'quotes': 20 / 1e9, 'trades': 10 / 1e9}


def test_union_audit_rejects_changed_identity_and_preserves_fixed_cell_splits():
    bad = list(row(10, 20)); bad[0] = 'foreign'
    with pytest.raises(ValueError, match='identity differs'):
        census([bad])
    result = census([row(899_000_000_000, 901_000_000_000)])
    assert result['captures'] == 2
    assert result['unique_requests'] == 1
    assert result['union_seconds_by_kind']['quotes'] == 2
    assert census([])['input_requests'] == 0
