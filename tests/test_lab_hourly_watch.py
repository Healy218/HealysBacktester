import json
import pytest
from scripts import lab_hourly_watch as watch


class FakeRpc:
    def __init__(self, status='active'):
        self.status = status
        self.queue = []
        self.calls = []
        self.cwd = str(watch.ROOT)

    def call(self, method, params):
        self.calls.append(method)
        if method == 'thread/read':
            return {'thread': {'id': watch.THREAD, 'cwd': self.cwd, 'status': {'type': self.status}}}
        if method == 'thread/queue/list':
            return {'data': self.queue.copy()}
        if method == 'thread/queue/add':
            item = {'id': 'hourly', 'input': params['input']}
            self.queue.append(item)
            return {'queuedSubmission': item}
        if method == 'thread/queue/start':
            assert self.status == 'idle'
            self.queue.clear()
            return {'turn': {'id': 'health-check'}}
        if method == 'thread/resume':
            self.status = 'active'  # Resumption may race with user work.
            return {}
        raise AssertionError(method)


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setattr(watch, 'STATE', tmp_path)
    monkeypatch.setattr(watch, 'capture_runtime', lambda slot: tmp_path / f'runtime-{slot}.json')
    return dict(thread_id=watch.THREAD, cwd=str(watch.ROOT))


def test_hourly_dedup_busy_then_idle_and_next_hour(state):
    rpc = FakeRpc()
    assert watch.dispatch(rpc, state, 7200)['pending']
    assert watch.dispatch(rpc, state, 7260)['pending']
    assert rpc.calls.count('thread/queue/add') == 1
    assert 'thread/queue/start' not in rpc.calls
    rpc.status = 'idle'
    assert not watch.dispatch(rpc, state, 7320)['pending']
    watch.dispatch(rpc, state, 7380)
    assert rpc.calls.count('thread/queue/start') == 1
    watch.dispatch(rpc, state, 10800)
    assert rpc.calls.count('thread/queue/start') == 2


def test_busy_across_hours_coalesces_and_cancel_does_not_recreate(state):
    rpc = FakeRpc()
    watch.dispatch(rpc, state, 7200)
    watch.dispatch(rpc, state, 10800)
    assert rpc.calls.count('thread/queue/add') == 1
    rpc.queue.clear()
    watch.dispatch(rpc, state, 10860)
    assert rpc.calls.count('thread/queue/add') == 1


def test_check_is_read_only_and_wrong_target_is_rejected(state):
    rpc = FakeRpc()
    assert watch.dispatch(rpc, state, 7200, check=True)['target_verified']
    assert rpc.calls == ['thread/read', 'thread/queue/list']
    rpc.cwd = '/wrong-project'
    with pytest.raises(ValueError, match='different thread'):
        watch.dispatch(rpc, state, 7200)


def test_resume_does_not_interrupt_new_active_turn(state):
    rpc = FakeRpc('notLoaded')
    assert watch.dispatch(rpc, state, 7200)['pending']
    assert 'thread/queue/start' not in rpc.calls


def test_stopped_watcher_does_not_connect(state, monkeypatch):
    (watch.STATE / 'state.json').write_text(json.dumps(state | {'stopped': True}))
    monkeypatch.setattr(watch.sys, 'argv', ['watch'])
    monkeypatch.setattr(watch, 'Rpc', lambda: pytest.fail('stopped watcher connected'))
    watch.main()


def test_broker_success_does_not_hide_scanner_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(watch, 'PAPER', tmp_path)
    (tmp_path/'scanner-dispatch-status.json').write_text(json.dumps(
        dict(status='blocked', error='TLT: price vintage changed')))
    (tmp_path/'broker-status.json').write_text(json.dumps(dict(status='complete')))
    receipts = watch.paper_receipts()
    assert receipts['scanner-dispatch-status.json']['status'] == 'blocked'
    assert 'TLT' in receipts['scanner-dispatch-status.json']['error']
    assert receipts['broker-status.json']['status'] == 'complete'
    assert 'observation_error' in receipts['status.json']


def test_paper_receipts_include_concurrent_quote_recovery(tmp_path, monkeypatch):
    monkeypatch.setattr(watch, 'PAPER', tmp_path)
    attempts = [{'at': '2026-10-02T13:45:30Z', 'errors': [{'symbol': 'FLY', 'error': 'no fresh quote'}]}]
    (tmp_path/'position-monitor-status.json').write_text(json.dumps(dict(
        status='waiting_for_quote', checked_at='2026-10-02T13:45:30Z', attempts=attempts)))
    receipt = watch.paper_receipts()['position-monitor-status.json']
    assert receipt['status'] == 'waiting_for_quote'
    assert receipt['attempt_count'] == 1 and receipt['last_attempt'] == attempts[0]


def test_retained_work_includes_partial_waves_without_nested_double_counting(tmp_path):
    for sid, status, cohorts, targets in [('A', 'discovered', 10, 100),
                                           ('B', 'checkpointed', 8, 70)]:
        root = tmp_path / sid
        root.mkdir()
        payload = dict(status=status, cohorts_discovered=cohorts,
                       distinct_horizon_targets_covered=targets,
                       horizon_target_statuses={'capture_incomplete': targets})
        (root / 'progress.json').write_text(json.dumps(payload))
        nested = root / 'securities' / sid
        nested.mkdir(parents=True)
        (nested / 'progress.json').write_text(json.dumps(payload))
    current = watch.wave_work(tmp_path, 'discovered')
    assert current['cohorts_processed'] == 18
    assert current['horizon_targets_assessed'] == 170
    assert current['horizon_target_outcomes']['capture_incomplete'] == 170
    assert current['completed_securities'] == 1
    assert current['partial_securities'] == 1
    (tmp_path / 'B/progress.json').write_text(json.dumps(dict(
        status='running', cohorts_discovered=12, distinct_horizon_targets_covered=90)))
    newer = watch.wave_work(tmp_path, 'discovered')
    assert watch.work_delta(newer, current) == dict(
        cohorts_processed=4, horizon_targets_assessed=20, completed_securities=0)


def test_missing_wave_observation_does_not_claim_zero_progress(tmp_path):
    current = watch.wave_work(tmp_path / 'missing', 'discovered')
    assert current['observation_errors']
    assert watch.work_delta(current, {'cohorts_processed': 100}) is None


def test_same_slot_refresh_keeps_previous_hour_as_delta_baseline(tmp_path, monkeypatch):
    monkeypatch.setattr(watch, 'STATE', tmp_path)
    for slot in [3600, 7200]:
        (tmp_path / f'runtime-{slot}.json').write_text(json.dumps(
            dict(observed_at=slot, v7_work={})))
    assert watch.previous_observation(7200)['observed_at'] == 3600
    assert watch.previous_observation(10800)['observed_at'] == 7200


def test_successful_incubator_hidden_but_active_and_failure_visible(tmp_path):
    candidate = tmp_path / 'candidate'
    candidate.mkdir()
    for name in ['complete', 'evaluation']:
        (candidate / (name + '.json')).write_text('{"status":"rejected"}')
    latest = dict(status='candidate_already_frozen', stage='done', run_dir=str(tmp_path))
    service = dict(output='ActiveState=inactive\nResult=success\n')
    snapshot = dict(receipts={'incubator/continual-v6/r5/latest-run.json': latest},
                    services={'healys-v6-continual.service': service})
    assert watch.incubator_visibility(snapshot)['show'] is False
    latest.update(status='running', stage='training')
    service['output'] = 'ActiveState=active\n'
    assert watch.incubator_visibility(snapshot)['reason'] == 'incubating'
    service['output'] = 'ActiveState=failed\n'
    assert watch.incubator_visibility(snapshot)['reason'] == 'failure_needs_attention'


def test_legacy_queued_check_is_still_deduplicated(state):
    rpc = FakeRpc()
    rpc.queue = [{'id': 'legacy', 'input': [{'text': watch.LEGACY_PREFIX}]}]
    watch.dispatch(rpc, state, 7200)
    assert 'thread/queue/add' not in rpc.calls
