import json
from pathlib import Path
import pandas as pd
import pytest

from nn_meta.etfe import stock_quote_capture as q, stock_quote_pilot as p


def item():
    return q.job('stock_quotes', dict(symbols='SPY', start='2024-01-19T14:30:00Z',
        end='2024-01-19T14:32:29.999999999Z', feed='sip', asof='-', sort='asc', limit=10000), 'fixture')


def raw(**changes):
    return dict(dict(t='2024-01-19T14:30:00.123456789Z', bp=100, ap=100.02,
        bs=2, **{'as':3}, bx='P', ax='Q', c=['R'], z='B'), **changes)


class HTTP:
    def __init__(self, bodies):
        self.bodies = iter(bodies)
        self.params = []
    def get(self, route, params, cap):
        self.params.append(params)
        return 200, json.dumps(next(self.bodies)).encode(), {}, None


def capture(root, http, budget=128):
    return q.capture(root, http, request_budget=budget, sleep=lambda _:None, check_resources=lambda *_:None)


def test_quote_scope_and_time_bounds():
    good = item()
    for changed in [dict(symbols='AAPL'), dict(feed='iex'), dict(asof='2024-01-19'),
                    dict(end='2026-10-03T04:00:00Z'), dict(end='2024-01-19T14:33:00Z')]:
        with pytest.raises(ValueError):
            q.job('stock_quotes', dict(good['params'], **changed), 'bad')
    with pytest.raises(ValueError):
        q.job('option_quotes', good['params'], 'bad')


def test_quote_strata_dst_early_close_and_unit_transition():
    calendar = [dict(date=day, open='09:30', close='13:00' if day=='2024-11-29' else '16:00') for day in p.DAYS]
    jobs = p.jobs(calendar)
    assert len(jobs) == 54
    assert any(j['params']['start']=='2024-11-29T17:59:30+00:00' for j in jobs)
    assert any(j['params']['start']=='2025-10-31T13:29:30+00:00' for j in jobs)
    assert any(j['params']['start']=='2025-11-03T14:29:30+00:00' for j in jobs)
    assert all(pd.Timestamp(j['params']['end']) < pd.Timestamp(q.END) for j in jobs)


def test_empty_page_paginates_and_resume_preserves_nanosecond_occurrences(tmp_path, monkeypatch):
    root = tmp_path/'quotes'
    plan = q.prepare(root, [item()])
    http = HTTP([dict(quotes={}, next_page_token='next'),
                 dict(quotes={'SPY':[raw(), raw()]}, next_page_token=None)])
    first = capture(root, http, 1)
    assert not first['capture_complete']
    checkpoint_path = next((root/'jobs').glob('*/page-000000.json'))
    checkpoint = checkpoint_path.read_bytes()
    second = capture(root, http)
    assert second['capture_complete']
    assert http.params[1]['page_token']=='next'
    assert checkpoint_path.read_bytes()==checkpoint
    assert capture(root, HTTP([]))['requests_this_run']==0
    monkeypatch.setattr(p, 'verify', lambda _:q.load_plan(root))
    monkeypatch.setattr(q, 'guard', lambda *_:None)
    result = p.normalize(root)
    assert result['rows']==2 and len(result['page_receipts'])==2
    assert p.audit(root)['raw_occurrences_preserved']
    assert p.normalize(root)==result
    import pyarrow.parquet as pq
    rows = [row for path in (root/'normalized').glob('*.parquet') for row in pq.read_table(path).to_pylist()]
    assert rows[0]['timestamp_ns']==pd.Timestamp(raw()['t']).value
    assert rows[0]['occurrence_id']!=rows[1]['occurrence_id']
    assert rows[0]['bid_size_raw']=='2' and rows[0]['bid_size_shares'] is None
    assert rows[0]['diagnostic_mid']==pytest.approx(100.01)
    next((root/'attempts').glob('*/body.json')).write_text('{}')
    with pytest.raises(ValueError, match='checksum'):
        q.committed(root, item())


def test_source_and_repeated_tokens_fail_closed(tmp_path):
    root = tmp_path/'quotes'
    q.prepare(root, [item()])
    result = capture(root, HTTP([dict(quotes={}, next_page_token='same')]*2))
    assert not result['capture_complete'] and result['stop_reason']=='Repeated page token'
    source = root/'source'/q.SOURCES[0]
    source.write_text('changed')
    with pytest.raises(ValueError, match='source changed'):
        q.load_plan(root)


def test_quote_budget_reserved_before_crash(tmp_path):
    root = tmp_path/'quotes'
    q.prepare(root, [item()])
    class Crash:
        def get(self, *args):
            raise OSError('network process death')
    with pytest.raises(OSError):
        capture(root, Crash())
    assert len(list((root/'request_reservations').glob('*.json')))==1
    for i in range(1,256):
        q.save(root/'request_reservations'/f'{i:06d}.json', {})
    result = capture(root, HTTP([]))
    assert result['requests_this_run']==0 and result['stop_reason']=='study_request_budget'


@pytest.mark.parametrize('changes,flag', [({'bp':101},'crossed_quote'), ({'bs':0},'invalid_bs'),
    ({'as':0.5},'invalid_as'), ({'ap':None},'invalid_ap'), ({'bp':True},'invalid_bp')])
def test_unusable_quote_is_retained_with_null_mid(changes, flag):
    record = p.typed('SPY', raw(**changes), item(), 0, 0,
                     dict(body_sha256='hash', received_at='observed'), 'plan')
    assert flag in record['quality_flags'] and record['diagnostic_mid'] is None
    assert record['bid_size_shares'] is None and record['ask_size_shares'] is None
