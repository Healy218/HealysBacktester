import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import run_v6_parallel_freeze as p
from scripts import materialize_v6_tick_store as streaming
from tests.test_option_tick_dataset import evidence, capture, request
from tests.test_v6_streaming_ticks import bound_task


def test_resource_math_reserves_physical_siblings_and_ram():
    cores = {n: [n, n+8] for n in range(8)}
    plan = p.resource_plan(24*1024**3, cores, {n: .05 for n in range(16)})
    assert plan['symbol_workers'] == 4 and plan['planned_symbol_ram_gib'] == 12
    assert len(plan['reserved_cpus']) == 4
    used = [n for group in plan['worker_cpu_groups'] for n in group]
    assert len(used) == len(set(used)) == 12
    for group in plan['worker_cpu_groups']:
        assert all((n+8 in group) for n in group if n < 8)
    assert not set(used) & set(plan['reserved_cpus'])
    assert p.resource_plan(11*1024**3, cores, {})['symbol_workers'] == 2
    with pytest.raises(p.TickDataError, match='headroom'):
        p.resource_plan(9*1024**3, cores, {})
    with pytest.raises(p.TickDataError, match='headroom'):
        p.resource_plan(24*1024**3, cores, {n: .95 for n in range(16)})


def test_existing_store_reverified_without_capture_or_changed_bytes(tmp_path, evidence, monkeypatch):
    selected = bound_task(evidence, [request()])
    raw = capture(tmp_path/'raw')
    output = tmp_path/'output';store = output/'stores/AA'
    expected = streaming.materialize(selected, [raw], store)
    before = {f.name: f.read_bytes() for f in store.iterdir()}
    monkeypatch.setattr(p.pinned, 'prepare_symbol', lambda *a: (selected, {'capture_batches': []}))
    monkeypatch.setattr(p.pinned, 'capture_one', lambda *a: pytest.fail('must not download completed store'))
    reference = p.one_symbol('AA', tmp_path/'inventory', tmp_path/'policy', output, 2)
    assert reference['store_sha256'] == expected['store_sha256']
    assert before == {f.name: f.read_bytes() for f in store.iterdir()}
    (store/'features.parquet').write_bytes(b'tampered')
    with pytest.raises(p.TickDataError):
        p.one_symbol('AA', tmp_path/'inventory', tmp_path/'policy', output, 2)


def test_interrupted_store_preserved_and_rebuilt_with_same_features(tmp_path, evidence, monkeypatch):
    selected = bound_task(evidence, [request()])
    raw = capture(tmp_path/'raw')
    expected = streaming.materialize(selected, [raw], tmp_path/'expected')
    output = tmp_path/'output';store = output/'stores/AA';store.mkdir(parents=True)
    (store/'features.parquet').write_bytes(b'incomplete')
    monkeypatch.setattr(p.pinned, 'prepare_symbol', lambda *a: (selected, {'capture_batches': [{}]}))
    monkeypatch.setattr(p.pinned, 'capture_one', lambda *a: raw)
    reference = p.one_symbol('AA', tmp_path/'inventory', tmp_path/'policy', output, 2)
    assert reference['store_sha256'] == expected['store_sha256']
    preserved = list((output/'parallel/incomplete_stores').glob('AA-*/features.parquet'))
    assert len(preserved) == 1 and preserved[0].read_bytes() == b'incomplete'


def fake_scheduler(tmp_path, monkeypatch, failure=False):
    output = tmp_path/'output';output.mkdir()
    symbols = ['AA','AAL','AAPL','ABBV','ABNB']
    completed = output/'stores/AA/manifest.json';completed.parent.mkdir(parents=True);completed.write_text('{}')
    args = SimpleNamespace(output=output, inventory=tmp_path/'inventory', policy=tmp_path/'policy', symbol_workers=4, workers=16)
    monkeypatch.setattr(p, 'available_bytes', lambda: 24*1024**3)
    monkeypatch.setattr(p, 'measure_resources', lambda n: p.resource_plan(24*1024**3, {i:[i,i+8] for i in range(8)}, {}))
    monkeypatch.setattr(p, 'check_scope', lambda *a: symbols)
    monkeypatch.setattr(p.time, 'sleep', lambda n: None)
    jobs=[]
    class Process:
        def __init__(self, command, **kwargs):
            self.symbol=command[command.index('--symbol')+1];self.pid=100+len(jobs);self.calls=0;self.returncode=None;self.stopped=False
            assert command[:2] == ['taskset','--cpu-list']
            jobs.append(self)
            p.write_json(output/'parallel/symbols'/f'{self.symbol}.json', {'pid':self.pid,'phase':'complete',
                'reference':{'directory':str(output/'stores'/self.symbol),'task_sha256':'task','store_sha256':self.symbol}})
        def poll(self):
            self.calls+=1
            if self.stopped:self.returncode=130
            elif self.calls>=2:self.returncode=1 if failure and self.symbol=='AAL' else 0
            return self.returncode
        def send_signal(self, sig):self.stopped=True
        def wait(self, **kwargs):self.returncode=130 if self.stopped else 0;return self.returncode
        def terminate(self):self.stopped=True
    monkeypatch.setattr(p.subprocess,'Popen',Process)
    return args,symbols,jobs


def test_scheduler_runs_four_symbols_and_rechecks_completed_last(tmp_path, monkeypatch):
    args,symbols,jobs=fake_scheduler(tmp_path,monkeypatch)
    p.run_parallel(args,symbols)
    assert [job.symbol for job in jobs[:4]]==['AAL','AAPL','ABBV','ABNB']
    assert jobs[-1].symbol=='AA'
    report=json.loads((args.output/'manifest.json').read_text())
    assert report['complete'] and set(report['stores'])==set(symbols)
    assert not (args.output/'final-inputs.json').exists()  # sealing is a later gate


def test_worker_failure_stops_peers_and_never_marks_complete(tmp_path, monkeypatch):
    args,symbols,jobs=fake_scheduler(tmp_path,monkeypatch,failure=True)
    with pytest.raises(p.TickDataError, match='worker failed'):
        p.run_parallel(args,symbols)
    assert not (args.output/'manifest.json').exists()
    assert all(job.returncode is not None for job in jobs)
