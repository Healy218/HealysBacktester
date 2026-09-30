from datetime import datetime, timezone
import json
from types import SimpleNamespace

import pytest

from scripts import v6_focus_20260930 as focus
from scripts import resume_v7_compute_20260930 as resumed


def test_one_time_clock_does_not_bypass_future_market_windows():
    closing = datetime(2026, 9, 30, 20, tzinfo=timezone.utc)
    assert not focus.clock_allowed(datetime(2026, 9, 30, 20, 0, tzinfo=timezone.utc), closing)
    assert focus.clock_allowed(datetime(2026, 9, 30, 20, 1, tzinfo=timezone.utc), closing)
    assert not focus.clock_allowed(datetime(2026, 10, 1, 20, 1, tzinfo=timezone.utc), closing)
    assert not focus.clock_allowed(datetime(2026, 9, 30, 20, 1, tzinfo=timezone.utc),
                                   datetime(2026, 9, 30, 20, 15, tzinfo=timezone.utc))


def test_timer_scope_preserves_order_management_and_monitoring():
    for name in ['healys-fa-news.timer', 'healys-v6-data.timer', 'healys-v6-continual.timer',
                 'healys-v6-alpaca-scanner.timer', 'healys-cache-backup.timer']:
        assert focus.selected_timer(name)
    for name in ['healys-v6-alpaca-orders.timer', 'healys-server-deadman.timer',
                 'healys-v7-hourly-updates.timer', 'arch-update.timer']:
        assert not focus.selected_timer(name)


def test_resources_fit_service_memory_and_use_cpu_threads():
    resources = focus.resource_plan(available_workers=16, cpus=16)
    assert resources['workers'] * 4500 + 2048 <= resources['memory_max_mib']
    assert resources['training_threads'] == 16
    assert focus.resource_plan(available_workers=2, cpus=16)['workers'] == 2


def test_pause_stops_supervisors_before_signalling_capture(tmp_path, monkeypatch):
    monkeypatch.setattr(focus, 'STATE', tmp_path)
    calls = []
    monkeypatch.setattr(focus, 'ctl', lambda *args, **kw: calls.append(args))
    monkeypatch.setattr(focus, 'properties', lambda name: {'ActiveState': 'inactive'})
    plan = dict(timers={'healys-fa-news.timer': {'UnitFileState': 'enabled'}},
                active_services={focus.SUPERVISORS[0]: {}, focus.INITIAL[0]: {},
                                 'healys-fa-news.service': {}})
    focus.pause(plan)
    assert calls[0] == ('disable', '--now', 'healys-fa-news.timer')
    assert calls[1] == ('stop', focus.SUPERVISORS[0])
    assert calls[2] == ('stop', 'healys-fa-news.service')
    assert json.loads((tmp_path / 'progress.json').read_text())['phase'] == 'paused'


def test_failure_never_restores_or_claims_candidate(tmp_path, monkeypatch):
    state = tmp_path / 'state'
    state.mkdir()
    monkeypatch.setattr(focus, 'STATE', state)
    root = tmp_path / 'r3'
    root.mkdir()
    (root / 'latest-run.json').write_text(json.dumps({'status': 'blocked'}))
    monkeypatch.setattr(focus, 'preflight', lambda: ({'root': str(root)}, '2026-09-28', focus.WHEN))
    monkeypatch.setattr(focus, 'clock_allowed', lambda *args: True)
    monkeypatch.setattr(focus, 'inventory', lambda: {'timers': {}, 'active_services': {}})
    monkeypatch.setattr(focus, 'pause', lambda plan: None)
    monkeypatch.setattr(focus, 'resource_plan', lambda: {'workers': 4, 'training_threads': 16})
    monkeypatch.setattr(focus.subprocess, 'run', lambda *args, **kw: SimpleNamespace(returncode=1))
    monkeypatch.setattr(focus, 'restore', lambda plan: pytest.fail('restored after failure'))
    with pytest.raises(RuntimeError, match='not frozen'):
        focus.run(auto_restore=True)
    doc = json.loads((state / 'progress.json').read_text())
    assert doc['phase'] == 'needs_review'
    assert doc['candidate_complete'] is False
    assert '--through' in doc['command'] and '2026-09-28' in doc['command']


def test_restore_preserves_timer_state_and_skips_initial_v7_units(tmp_path, monkeypatch):
    monkeypatch.setattr(focus, 'STATE', tmp_path)
    monkeypatch.setenv('XDG_RUNTIME_DIR', str(tmp_path / 'runtime'))
    calls = []

    def ctl(*args, **kw):
        calls.append(args)
        return SimpleNamespace(stdout='not-found\n')

    monkeypatch.setattr(focus, 'ctl', ctl)
    monkeypatch.setattr(focus, 'properties', lambda name: {'ActiveState': 'activating'})
    plan = dict(timers={'healys-fa-news.timer': {'UnitFileState': 'enabled', 'ActiveState': 'active'},
                        'healys-fa-prices.timer': {'UnitFileState': 'disabled', 'ActiveState': 'inactive'}},
                active_services={name: {} for name in [*focus.INITIAL, *focus.SUPERVISORS]})
    focus.restore(plan)
    starts = [call for call in calls if call[0] == 'start']
    assert all(name not in call for name in focus.INITIAL for call in starts)
    assert ('start', 'healys-fa-news.timer') in starts
    assert ('start', 'healys-fa-prices.timer') not in starts
    assert ('start', '--no-block', *focus.SUPERVISORS) in starts
    assert 'resume_v7_compute_20260930.py' in next((tmp_path / 'runtime').rglob('90-focus-resume.conf')).read_text()


def test_v7_resource_revision_respects_existing_producer_limits(monkeypatch):
    monkeypatch.setattr(resumed.subprocess, 'check_output', lambda *args, **kw: '16\n')
    c = object.__new__(resumed.Controller)
    assert c.workers(1024, 2) == 4
    assert c.workers(3072, 1) == 1  # Existing replay producer is sequential.
    assert resumed.workers(3072, 2, 12288) == 2
    command = resumed.discovery_command(2)
    assert command[command.index('--workers') + 1] == '2'
    assert command[command.index('--state') + 1] == str(resumed.original.RECOVERY)


def test_success_requires_verified_candidate_before_restore(tmp_path, monkeypatch):
    state = tmp_path / 'state'
    state.mkdir()
    monkeypatch.setattr(focus, 'STATE', state)
    root = tmp_path / 'r3'
    root.mkdir()
    (root / 'latest-run.json').write_text(json.dumps({'status': 'candidate_frozen',
        'scope': 'full_universe', 'through': '2026-09-28'}))
    monkeypatch.setattr(focus, 'preflight', lambda: ({'root': str(root)}, '2026-09-28', focus.WHEN))
    monkeypatch.setattr(focus, 'clock_allowed', lambda *args: True)
    monkeypatch.setattr(focus, 'inventory', lambda: {'timers': {}, 'active_services': {}})
    monkeypatch.setattr(focus, 'pause', lambda plan: None)
    monkeypatch.setattr(focus, 'resource_plan', lambda: {'workers': 4, 'training_threads': 16})
    monkeypatch.setattr(focus.subprocess, 'run', lambda *args, **kw: SimpleNamespace(returncode=0))
    order = []
    monkeypatch.setattr(focus, 'verify', lambda path: order.append('verify'))
    monkeypatch.setattr(focus, 'sha', lambda path: 'sealed')
    monkeypatch.setattr(focus, 'restore', lambda plan: order.append('restore'))
    focus.run(auto_restore=True)
    assert order == ['verify', 'restore']
