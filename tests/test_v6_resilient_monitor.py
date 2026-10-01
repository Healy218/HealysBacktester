import json
import threading
from types import SimpleNamespace as NS

import pandas as pd
import pytest

from scripts import run_v6_forward_resilient_v1 as runner

GAP = [{'symbol': 'FLY', 'error': 'ValueError: no fresh post-decision option quote'}]
NOW = pd.Timestamp('2026-10-01T19:45:20Z')


def test_quiet_quote_retries_without_blocking_candidate_work(tmp_path):
    attempted, computed = threading.Event(), threading.Event()
    def check():
        attempted.set()
        return [] if computed.is_set() else GAP
    monitor = runner.PositionMonitor(check, deadline=NOW+pd.Timedelta(seconds=120),
        receipt=tmp_path/'monitor.json', clock=lambda: NOW, interval=.005)
    try:
        assert attempted.wait(2)
        assert not monitor.future.done()
        computed.set()  # Candidate computation is free to run during quote recovery.
        monitor.require_complete()
        report = json.loads((tmp_path/'monitor.json').read_text())
        assert report['status'] == 'complete' and len(report['attempts']) >= 2
    finally:
        monitor.close()


@pytest.mark.parametrize('errors', [GAP, [{'symbol': 'FLY', 'error': 'ValueError: price vintage changed'}]])
def test_deadline_or_non_quote_error_keeps_allocation_blocked(tmp_path, errors):
    calls = []
    def check():
        calls.append(1)
        return errors
    monitor = runner.PositionMonitor(check, deadline=NOW, receipt=tmp_path/'monitor.json', clock=lambda: NOW)
    try:
        with pytest.raises(ValueError, match='new entries withheld'):
            monitor.require_complete()
        assert calls == [1]
        assert json.loads((tmp_path/'monitor.json').read_text())['status'] == 'blocked'
    finally:
        monitor.close()


def test_monitor_exception_is_not_mistaken_for_success(tmp_path):
    def broken(): raise RuntimeError('provider unavailable')
    monitor = runner.PositionMonitor(broken, deadline=NOW, receipt=tmp_path/'monitor.json', clock=lambda: NOW)
    try:
        with pytest.raises(RuntimeError, match='provider unavailable'):
            monitor.require_complete()
    finally:
        monitor.close()


@pytest.mark.parametrize('unresolved', [False, True])
def test_full_consumer_computes_during_monitoring_but_gates_allocation(tmp_path, monkeypatch, unresolved):
    from nn_meta.live import v6_forward_inputs as inputs, v6_portfolio as portfolio, v6_market as market
    from nn_meta import decision_contracts
    computed, checked = threading.Event(), threading.Event()
    calls = []
    bar = pd.Timestamp('2026-10-01T19:30')
    frame = pd.DataFrame({'Close': [100.]}, index=[bar])
    class Data:
        def __init__(self, *a, **kw):
            self.calendar = NS(scan_open=lambda now: True, closed_starts=lambda *a: [bar])
            self.spec = {'symbols': {'SPY': {}}}
            self.document = {'through': '2026-09-30'}
            self.raw = {'SPY': frame}
            self.market_receipts = []
        def update(self, *a, **kw): pass
        def tasks(self, *a): return [('SPY', ('SPY',))]
    class Book:
        def __init__(self, path, **kw): self.path = path
        def cycle_seen(self, bar): return False
        def open_positions(self): return []
        def summary(self): return {}
        def allocate(self, *a, **kw):
            assert checked.is_set(), 'allocated before risk completion'
            calls.append('allocated')
            return {'opened': 0}
    class Market:
        def __init__(self, *a): self.evidence = []
        def verify_current_access(self, *a): return {'status': 'passed'}
        def execution_quote(self, *a, **kw): raise AssertionError('empty batch has no order')
    class Selector:
        def __init__(self, *a): pass
        def select(self, *a, **kw): return NS(symbol='SPY261002C00100000')
    def detect(task):
        computed.set()
        return {'fresh': [], 'exits': {}}
    def monitor(*a, **kw):
        assert computed.wait(2), 'monitoring blocked candidate computation'
        checked.set()
        return [{'symbol': 'FLY', 'error': 'ValueError: unresolved risk'}] if unresolved else []
    monkeypatch.setattr(runner, 'configure', lambda *a: {'model_sha256': 'same-model'})
    monkeypatch.setattr(runner, 'utcnow', lambda: NOW)
    monkeypatch.setattr(runner, 'monitor_positions', monitor)
    monkeypatch.setattr(inputs, 'ForwardData', Data)
    monkeypatch.setattr(inputs, 'init_worker', lambda *a: None)
    monkeypatch.setattr(inputs, 'process_symbol', detect)
    monkeypatch.setattr(portfolio, 'ForwardPortfolio', Book)
    monkeypatch.setattr(market, 'MassiveMarket', Market)
    monkeypatch.setattr(decision_contracts, 'DecisionContractSelector', Selector)
    args = NS(state=tmp_path, env=tmp_path/'absent.env', release=tmp_path, anchor='same-release',
        data=tmp_path, data_anchor='same-input', replay_time=None, enable_alerts=False, workers=1)
    if unresolved:
        with pytest.raises(ValueError, match='new entries withheld'): runner.run(args)
        assert not calls
    else:
        assert runner.run(args)['status'] == 'recorded'
        assert calls == ['allocated']
    assert computed.is_set() and checked.is_set()
    assert (tmp_path/'passes/20261001T194500Z/receipt.json').is_file()
