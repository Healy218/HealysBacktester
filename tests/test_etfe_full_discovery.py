import json
import pytest
from nn_meta.etfe import full_discovery as f


def record(**changes):
    return dict(dict(symbol='SPY240119C00400000', underlying_symbol='SPY',
        expiration_date='2024-01-19', status='active'), **changes)


class HTTP:
    def __init__(self, bodies): self.bodies=iter(bodies)
    def get(self, *args): return 200, json.dumps(next(self.bodies)).encode(), {}, None


def capture(root, bodies, budget=1024):
    return f.capture(root, HTTP(bodies), request_budget=budget, sleep=lambda _:None, check_resources=lambda *_:None)


def test_full_range_six_queries_explicit_dates_and_statuses():
    jobs=f.full_jobs()
    assert len(jobs)==6
    assert {(j['params']['underlying_symbols'],j['params']['status']) for j in jobs}=={
        (s,status) for s in ('SPY','QQQ','VOO') for status in ('active','inactive')}
    for j in jobs:
        assert j['params']['expiration_date_gte']=='2024-01-02'
        assert j['params']['expiration_date_lte']=='2026-11-16'
        assert 'type' not in j['params'] and 'strike_price_gte' not in j['params']
    with pytest.raises(ValueError):
        f.job('contracts',dict(jobs[0]['params'],expiration_date_gte='2025-01-01'),'bad')


@pytest.mark.parametrize('changes',[dict(expiration_date='2024-01-01'),dict(expiration_date='2026-11-17'),
    dict(status='inactive'),dict(underlying_symbol='QQQ')])
def test_provider_outside_range_or_identity_rejected(changes):
    with pytest.raises(ValueError):
        list(f.rows(dict(option_contracts=[record(**changes)],next_page_token=None),f.full_jobs()[0]))


def test_empty_continuation_page_and_actual_resume(tmp_path):
    item=f.full_jobs()[0]
    f.prepare(tmp_path/'raw',[item])
    root=tmp_path/'raw'
    first=capture(root,[dict(option_contracts=[],next_page_token='next')],1)
    assert not first['capture_complete']
    pointer=next((root/'jobs').glob('*/page-000000.json'));before=pointer.read_bytes()
    second=capture(root,[dict(option_contracts=[record()],next_page_token=None)])
    assert second['capture_complete'] and pointer.read_bytes()==before
    assert len(list(f.iter_records(root,item)))==1
    assert capture(root,[])['requests_this_run']==0
    next((root/'attempts').glob('*/body.json')).write_text('{}')
    with pytest.raises(ValueError,match='checksum'):
        f.committed(root,item)


def test_full_study_request_budget_reserved_before_network(tmp_path):
    root=tmp_path/'raw';f.prepare(root,[f.full_jobs()[0]])
    folder=root/'request_reservations';folder.mkdir()
    for i in range(2048): (folder/f'{i:06d}.json').write_text('{}')
    result=capture(root,[])
    assert result['requests_this_run']==0 and result['stop_reason']=='study_request_budget'
