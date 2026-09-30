import pytest

from scripts import v6_handover_update_20260930 as update


class Rpc:
    def __init__(self, status='active', cwd=None):
        self.status = status
        self.cwd = cwd or str(update.ROOT)
        self.queue = []
        self.calls = []

    def call(self, method, params):
        self.calls.append(method)
        if method == 'thread/read':
            return {'thread': {'id': update.THREAD, 'cwd': self.cwd, 'status': {'type': self.status}}}
        if method == 'thread/queue/list':
            return {'data': list(self.queue)}
        if method == 'thread/queue/add':
            item = {'id': 'ours', 'input': params['input']}
            self.queue.append(item)
            return {'queuedSubmission': item}
        if method == 'thread/queue/start':
            assert params['queuedSubmissionId'] == 'ours'
            self.queue.clear()
            return {'turn': {'id': 'turn'}}
        if method == 'thread/resume':
            self.status = 'idle'
            return {}
        raise AssertionError(method)


def test_check_does_not_queue_or_start():
    rpc = Rpc()
    assert update.dispatch(rpc, {}, check=True)['message_sent'] is False
    assert rpc.calls == ['thread/read', 'thread/queue/list']


def test_wrong_project_refuses_dispatch():
    with pytest.raises(ValueError, match='another terminal'):
        update.dispatch(Rpc(cwd='/somewhere/else'), {})


def test_busy_thread_retries_same_message_then_starts(tmp_path, monkeypatch):
    monkeypatch.setattr(update, 'STATE', tmp_path)
    monkeypatch.setattr(update, 'capture_runtime', lambda: None)
    rpc = Rpc()
    state = {}
    update.dispatch(rpc, state)
    update.dispatch(rpc, state)
    assert rpc.calls.count('thread/queue/add') == 1
    assert 'thread/queue/start' not in rpc.calls
    rpc.status = 'idle'
    result = update.dispatch(rpc, state)
    assert result['submitted'] and result['turn_id'] == 'turn'
    update.dispatch(rpc, state)
    assert rpc.calls.count('thread/queue/start') == 1


def test_resume_auto_consumption_does_not_duplicate(tmp_path, monkeypatch):
    monkeypatch.setattr(update, 'STATE', tmp_path)
    monkeypatch.setattr(update, 'capture_runtime', lambda: None)

    class AutoResume(Rpc):
        def call(self, method, params):
            result = super().call(method, params)
            if method == 'thread/resume':
                self.queue.clear()
            return result

    rpc = AutoResume(status='notLoaded')
    result = update.dispatch(rpc, {})
    assert result['submitted']
    assert 'thread/queue/start' not in rpc.calls
    assert rpc.calls.count('thread/queue/add') == 1
