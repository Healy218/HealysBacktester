"""Real recovery, malformed-response and timestamp boundary tests, no network."""
import json
from pathlib import Path
import pytest

from nn_meta.etfe.acquisition import audit, capture, iter_records, job, prepare
from scripts.acquire_etfe_alpaca import bootstrap_jobs, interval


def trade(stamp='2024-01-18T14:30:00.009729024Z'):
    return dict(t=stamp, p=1.13, s=3, c='I', x='X')


def trade_job():
    return job('option_trades', dict(symbols='SPY240119C00475000',
        start='2024-01-18T14:30:00Z', end='2024-01-18T14:30:59.999999999Z',
        sort='asc', limit=2), 'test')


def body(records, token=None):
    return dict(trades={'SPY240119C00475000':records}, next_page_token=token)


class Fake:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.params = []

    def get(self, route, params, max_bytes):
        self.params.append(params)
        response = next(self.responses)
        if isinstance(response, BaseException):
            raise response
        if isinstance(response, tuple):
            return response
        return 200, json.dumps(response).encode(), {}, None


def run(root, fake, **kwargs):
    return capture(root, fake, sleep=lambda _:None, check_resources=lambda *_:None, **kwargs)


def test_resume_and_occurrence_identity_match_uninterrupted(tmp_path):
    item = trade_job()
    resumed, clean = tmp_path/'resumed', tmp_path/'clean'
    for root in (resumed, clean):
        prepare(root, [item])
    first = Fake([body([trade()], 'a')])
    report = run(resumed, first, request_budget=1)
    assert report['stop_reason'] == 'request_budget'
    assert not report['capture_complete']
    before = {str(p):p.read_bytes() for p in (resumed/'jobs').rglob('page-*.json')}
    final = Fake([body([], 'b'), body([trade()])])
    report = run(resumed, final)
    assert report['capture_complete']
    assert final.params[0]['page_token'] == 'a'
    assert all(Path(p).read_bytes() == raw for p,raw in before.items())
    run(clean, Fake([body([trade()], 'a'), body([], 'b'), body([trade()])]))
    resumed_rows = list(iter_records(resumed, item))
    assert [r['raw'] for r in resumed_rows] == [r['raw'] for r in iter_records(clean, item)]
    assert len(resumed_rows) == 2
    assert resumed_rows[0]['source'] != resumed_rows[1]['source']
    assert report['partitions'][0]['min_timestamp_ns'] == 1705588200009729024
    no_calls = Fake([])
    assert run(resumed, no_calls)['requests_this_run'] == 0


def test_interruption_after_committed_page_resumes(tmp_path):
    root = tmp_path/'capture'
    prepare(root, [trade_job()])
    with pytest.raises(KeyboardInterrupt):
        run(root, Fake([body([trade()], 'a'), KeyboardInterrupt()]))
    fake = Fake([body([trade()])])
    assert run(root, fake)['capture_complete']
    assert fake.params[0]['page_token'] == 'a'


def test_corrupt_committed_body_refuses_network(tmp_path):
    root = tmp_path/'capture'
    prepare(root, [trade_job()])
    run(root, Fake([body([trade()])]))
    next((root/'attempts').glob('*/body.json')).write_text('{}')
    fake = Fake([])
    with pytest.raises(ValueError, match='checksum'):
        run(root, fake)
    assert not fake.params


@pytest.mark.parametrize('invalid', [{}, {'trades':{},'next_page_token':''},
    body([trade('2024-01-18T14:31:00Z')]), {'trades':{'QQQ':[]},'next_page_token':None}])
def test_invalid_response_never_commits(tmp_path, invalid):
    root = tmp_path/'capture'
    prepare(root, [trade_job()])
    result = run(root, Fake([invalid]))
    assert result['stop_reason']
    assert not result['capture_complete']
    assert result['partitions'][0]['pages'] == 0


def test_repeated_token_keeps_partition_incomplete(tmp_path):
    root = tmp_path/'capture'
    prepare(root, [trade_job()])
    report = run(root, Fake([body([], 'a'), body([], 'a')]))
    assert report['stop_reason'] == 'Repeated page token'
    assert report['partitions'][0]['pages'] == 1
    assert not report['capture_complete']


def test_http_error_is_not_no_trade_and_does_not_retry_auth(tmp_path):
    root = tmp_path/'capture'
    prepare(root, [trade_job()])
    fake = Fake([(403,b'{"message":"forbidden"}',{},None)])
    report = run(root, fake)
    assert report['requests_this_run'] == 1
    assert report['partitions'][0]['disposition'] == 'transport_incomplete'


def test_rate_wait_survives_restart(tmp_path):
    root = tmp_path/'capture'
    prepare(root, [trade_job()])
    report = run(root, Fake([(429,b'{}',{'retry-after':'120'},None)]))
    assert report['stop_reason'] == 'provider_wait_required'
    fake = Fake([])
    report = run(root, fake)
    assert report['stop_reason'] == 'provider_wait_pending'
    assert not fake.params


def test_empty_terminal_is_not_demonstrated_no_trade(tmp_path):
    root = tmp_path/'capture'
    prepare(root, [trade_job()])
    report = run(root, Fake([body([])]))
    assert report['capture_complete']
    assert report['partitions'][0]['disposition'] == 'empty_response'
    assert report['ready_for_build'] is False


def test_fixed_end_and_provider_contracts():
    jobs = bootstrap_jobs()
    assert len(jobs) == 18
    assert interval('2026-10-02','2026-10-03')['end'] == '2026-10-03T03:59:59.999999999+00:00'
    item = trade_job()
    with pytest.raises(ValueError):
        job(item['route'],dict(item['params'],feed='opra'),'invalid')
    with pytest.raises(ValueError):
        job(item['route'],dict(item['params'],end='2026-10-03T04:00:00Z'),'invalid')
