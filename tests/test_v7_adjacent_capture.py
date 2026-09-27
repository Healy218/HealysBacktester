import pytest

from nn_meta.v7.quotes import capture_union
from scripts.validate_v7_adjacent_capture import same_records


def test_joining_preserves_request_mapping_without_filling_gaps_or_crossing_kind():
    rows = [dict(request_id=str(i), contract='SPY220316P00420000', kind=kind,
                 start_ns=start, end_ns=end) for i,(kind,start,end) in enumerate([
                     ('quotes', 890*10**9, 900*10**9), ('quotes', 900*10**9, 910*10**9),
                     ('quotes', 911*10**9, 930*10**9), ('trades', 890*10**9, 930*10**9)])]
    fixed = capture_union(rows)
    joined = capture_union(rows, max_span_ns=86400*10**9)
    assert len(fixed['captures']) == 5
    assert len(joined['captures']) == 3
    assert joined['requests'] == fixed['requests']
    by_id = {c['capture_id']:c for c in joined['captures']}
    for request in rows:
        capture = by_id[joined['request_captures'][request['request_id']][0]]
        assert capture['kind'] == request['kind']
        assert capture['start_ns'] <= request['start_ns'] < request['end_ns'] <= capture['end_ns']
    quotes = [c for c in joined['captures'] if c['kind']=='quotes']
    assert quotes[0]['end_ns'] == 910*10**9
    assert quotes[1]['start_ns'] == 911*10**9


def test_parity_rejects_precision_order_multiplicity_and_null_changes():
    rows = [{'sip_timestamp':1647351270000000001,'price':1.125}, {'sip_timestamp':1647351270000000001,'price':1.125}]
    same_records(rows, list(rows))
    for changed in (rows[:1], [dict(rows[0], price=1.12),rows[1]], [dict(rows[0],extra=None),rows[1]]):
        with pytest.raises(ValueError, match='raw record'):
            same_records(rows, changed)
    with pytest.raises(ValueError, match='raw record'):
        same_records([{'x':1},{'x':2}], [{'x':2},{'x':1}])
