import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

from scripts.capture_v7_recovery_frontier import subtract, batch_items, snapshot
from scripts.run_v7_execution_recovery import capacity, empty_job
from nn_meta.v7.storage import receipt, sha, identity, verify


def test_subtraction_retains_only_actual_uncovered_ranges():
    window = dict(contract='AAPL220325C00160000', kind='quotes', start_ns=10, end_ns=100)
    parts = list(subtract(window, [(50, 80), (0, 20), (15, 40), (90, 120)]))
    assert [(p['start_ns'], p['end_ns']) for p in parts] == [(40, 50), (80, 90)]
    assert all(p['contract'] == window['contract'] and p['kind'] == 'quotes' for p in parts)
    assert not list(subtract(window, [(0, 100)]))
    assert list(subtract(window, [(110, 120)])) == [window]


def test_snapshot_batching_never_drops_tail():
    values = list(range(55))
    batches = list(batch_items(values))
    assert [len(b) for b in batches] == [24, 24, 7]
    assert [v for batch in batches for v in batch] == values


def test_live_reserve_accounts_for_all_active_slices(monkeypatch):
    monkeypatch.setattr('scripts.run_v7_execution_recovery.shutil.disk_usage',
                        lambda _: SimpleNamespace(free=10_000_000_000 + 600 * 1024**2))
    assert capacity(Path('.'), 1) > 10_000_000_000
    with pytest.raises(ValueError, match='reserve'): capacity(Path('.'), 2)


def fixture_jobs(tmp_path, proposals=0, horizons=0, rows=0, selections=0):
    jobs = tmp_path / 'jobs'; jobs.mkdir()
    demand = tmp_path / 'demand'; demand.mkdir()
    with sqlite3.connect(demand / 'demand.sqlite3') as db:
        db.execute('CREATE TABLE selections(x)')
        db.executemany('INSERT INTO selections VALUES(?)', [(i,) for i in range(selections)])
    receipt(demand, {})
    with sqlite3.connect(jobs / 'jobs.sqlite3') as db:
        db.execute('CREATE TABLE jobs(x)')
        db.executemany('INSERT INTO jobs VALUES(?)', [(i,) for i in range(rows)])
    (jobs / 'binding.json').write_text(json.dumps(dict(demand=str(demand))))
    (jobs / 'report.json').write_text(json.dumps(dict(proposals=proposals, distinct_horizons=horizons)))
    receipt(jobs, {})
    return jobs


def test_only_verified_empty_demand_skips_quote_index(tmp_path):
    assert empty_job(fixture_jobs(tmp_path))


@pytest.mark.parametrize('changes', [{'rows': 1}, {'selections': 1}])
def test_false_empty_census_fails_closed(tmp_path, changes):
    with pytest.raises(ValueError, match='Empty queue'):
        empty_job(fixture_jobs(tmp_path, **changes))


def test_nonempty_demand_does_not_bypass_missing_capture(tmp_path):
    assert not empty_job(fixture_jobs(tmp_path, proposals=1, horizons=1, rows=1, selections=1))


def test_snapshot_preserves_provenance_and_non_tick_requests_after_source_advances(tmp_path):
    parent = tmp_path / 'parent'; parent.mkdir()
    (parent / 'declaration.json').write_text(json.dumps(dict(securities=['sid'])))
    previous = tmp_path / 'previous'; previous.mkdir()
    (previous / 'binding.json').write_text('{}'); receipt(previous, {})
    wave = parent / 'waves' / 'sid'
    root = wave / 'securities' / 'sid'; root.mkdir(parents=True)
    index = wave / 'indexes' / 'sid'; index.mkdir(parents=True)
    with sqlite3.connect(index / 'index.sqlite3') as db:
        db.execute('CREATE TABLE ranges(contract,kind,start_ns,end_ns)')
        db.execute('INSERT INTO ranges VALUES(?,?,?,?)', ('AAPL220325C00160000', 'quotes', 10, 20))
    receipt(index, {})
    declaration = dict(inputs={})
    (wave / 'declaration.json').write_text(json.dumps(declaration))
    (root / 'binding.json').write_text(json.dumps(dict(campaign_identity=identity(declaration),
                                             quote_index_sha256=sha(index / 'complete.json'))))
    requests = [dict(request_id='tick', provider='massive', kind='quotes',
                     contract='AAPL220325C00160000', start_ns=10, end_ns=30),
                dict(request_id='ref', provider='massive', kind='contract_reference', contract='AAPL220325C00160000')]
    with sqlite3.connect(root / 'wave.sqlite3') as db:
        db.execute('CREATE TABLE cohorts(x)')
        db.execute('CREATE TABLE pending(request_id,request)')
        db.executemany('INSERT INTO pending VALUES(?,?)', [(r['request_id'], json.dumps(r)) for r in requests])
    output = tmp_path / 'snapshot'
    result = snapshot(parent, previous, output)
    assert result['non_tick_requests'] == 1 and result['pending_rows'] == 2
    plan = json.loads((output / 'capture-plan.json').read_text())
    assert [(c['start_ns'], c['end_ns']) for c in plan['captures']] == [(20, 30)]
    frozen = json.loads((output / 'binding.json').read_text())
    assert frozen['source_state_observations'][0]['pending'] == 2
    with sqlite3.connect(root / 'wave.sqlite3') as db: db.execute('DELETE FROM pending')
    verify(output)
    assert json.loads((output / 'requests.json').read_text())['ref'] == requests[1]
    assert str(root / 'wave.sqlite3') not in frozen['inputs']
