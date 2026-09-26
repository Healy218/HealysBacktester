import pytest

from nn_meta.v7.storage import identity
from scripts.plan_v7_capture_sample import combine, summarize
from scripts.capture_v7_volume_sample import forecast, guard
from scripts.benchmark_v7_capture_encoding import columns, records
from scripts.audit_v7_contiguous_captures import ranges


def rows(contract, starts):
    result = []
    for start in starts:
        for kind in ('quotes', 'trades'):
            scope = dict(contract=contract, kind=kind, start_ns=start, end_ns=start+60*10**9)
            result.append((identity(scope), contract, '2022-03-15', kind, scope['start_ns'], scope['end_ns']))
    return sorted(result, key=lambda r: (r[1], r[2], r[3], r[4], r[5]))


def test_stratified_sample_is_order_independent_and_parallel_merge_exact():
    start = 1647351600*10**9
    a = rows('SPY220316P00420000', [start+i*900*10**9 for i in range(20)])
    b = rows('SPY220316P00421000', [start+i*900*10**9 for i in range(20)])
    kwargs = dict(security_id='security', quartile=0, maximum=4)
    together = summarize(sorted(a+b, key=lambda r: (r[1], r[2], r[3], r[4], r[5])), **kwargs)
    split = combine([summarize(a, **kwargs), summarize(b, **kwargs)], 4)
    assert split == combine([together], 4)
    assert sum(split['population'].values()) == 40
    assert len(split['samples']) == 4
    assert all(set(s['captures']) == {'quotes', 'trades'} for s in split['samples'])


def test_sample_rejects_asymmetric_or_changed_requests():
    data = rows('SPY220316P00420000', [1647351600*10**9])
    with pytest.raises(ValueError, match='do not match'):
        summarize(data[:1], security_id='s', quartile=0, maximum=2)
    bad = list(data[0]); bad[0] = 'bad'
    with pytest.raises(ValueError, match='identity'):
        summarize([bad], security_id='s', quartile=0, maximum=2)


def test_sample_counts_census_strata_and_splits_cells():
    start = 1647351890*10**9
    data = rows('SPY220316P00420000', [start])
    result = summarize(data, security_id='s', quartile=3, maximum=2)
    assert result['requests'] == 2
    assert sum(result['seconds_ns'].values()) == 60*10**9
    assert all(k.startswith('2022-q3-') for k in result['population'])
    assert sum(result['population'].values()) == 2


def test_forecast_weights_population_and_rejects_missing_failed_samples():
    plan = {'population': {'a': 100, 'b': 1}, 'samples': []}
    measured = {}
    for stratum, values in [('a', [10, 30]), ('b', [200])]:
        for index, value in enumerate(values):
            ids = [f'{stratum}-{index}-{kind}' for kind in ('q', 't')]
            plan['samples'].append(dict(stratum=stratum, captures={k: {'capture_id': k} for k in ids}))
            for key in ids:
                measured[key] = dict(ok=True, logical_bytes=value//2)
    result = forecast(plan, measured)
    assert result['estimated_capture_bytes'] == 2200
    assert result['mean_plus_three_se_bytes'] > 2200
    measured['a-0-q']['ok'] = False
    with pytest.raises(ValueError, match='cannot be dropped'):
        forecast(plan, measured)
    del measured['a-0-q']
    with pytest.raises(ValueError, match='cannot be dropped'):
        forecast(plan, measured)


@pytest.mark.parametrize('field,value,reason', [
    ('acquisition_budget_bytes', 100, 'Sample acquisition'),
    ('disk_reserve_bytes', 1000, 'disk reserve'),
    ('project_budget_bytes', 100, 'total-project'),
])
def test_capacity_guard_accounts_for_inflight_reservations(field, value, reason):
    plan = dict(acquisition_budget_bytes=500, metadata_budget_bytes=10,
                disk_reserve_bytes=100, project_baseline_ceiling_bytes=100,
                project_budget_bytes=1000)
    arguments = dict(used_bytes=100, pending=2, task_reservation=100, free_bytes=1000,
                     quota=dict(used_bytes=50, reservations={'other': 100}, limit_bytes=1000))
    guard(plan, **arguments)
    with pytest.raises(ValueError, match=reason):
        guard(dict(plan, **{field: value}), **arguments)


def test_candidate_columns_preserve_absent_null_types_duplicates_and_large_timestamps():
    rows = [{'sip_timestamp': 1647351270000000001, 'size': 2, 'price': 1.125, 'conditions': []},
            {'sip_timestamp': 1647351270000000001, 'size': 2, 'price': 1.125, 'conditions': []},
            {'sip_timestamp': 1647351270000000002, 'size': None, 'price': 0.0},
            {'sip_timestamp': 1647351270000000003, 'extra': {'nested': True}}]
    from options.data.massive_ticks import canonical_bytes
    import json
    assert canonical_bytes(records(json.loads(canonical_bytes(columns(rows))))) == canonical_bytes(rows)
    assert records(columns([])) == []


def test_contiguous_ranges_never_fill_a_gap_or_cross_contract_day():
    rows = [('A', 'day1', 10, 20), ('A', 'day1', 15, 25), ('A', 'day1', 25, 30),
            ('A', 'day1', 31, 40), ('A', 'day2', 40, 50), ('B', 'day2', 40, 50)]
    assert list(ranges(rows)) == [('A', 'day1', 10, 30), ('A', 'day1', 31, 40),
                                 ('A', 'day2', 40, 50), ('B', 'day2', 40, 50)]
