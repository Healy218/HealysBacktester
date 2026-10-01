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
