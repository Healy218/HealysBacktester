from datetime import date,timedelta
import json
import pytest
from scripts import capture_etfe_full_announcements_v2 as a


def test_full_queries_cover_each_date_once_within_provider_range():
    jobs=a.inventory()
    assert len(jobs)==36
    for symbol in ('SPY','QQQ','VOO'):
        days=[]
        for job in jobs:
            if job['symbol']!=symbol:continue
            start,stop=map(date.fromisoformat,(job['since'],job['until']))
            assert (stop-start).days<90
            assert job['date_type']=='ex_date'
            assert set(job['ca_types'].split(','))=={'dividend','merger','spinoff','split'}
            days.extend(start+timedelta(days=i) for i in range((stop-start).days+1))
        assert days==[date(2024,1,1)+timedelta(days=i) for i in range((date(2026,10,2)-date(2024,1,1)).days+1)]


def test_capture_resume_is_read_only_and_raw_tamper_fails(tmp_path,monkeypatch):
    root=tmp_path/'capture';a.prepare(root);calls=[]
    monkeypatch.setattr(a,'credentials',lambda:dict(metadata=('test-key','test-secret')))
    monkeypatch.setattr(a,'guard',lambda *_:None)
    monkeypatch.setattr(a.time,'sleep',lambda _:None)
    class Response:
        status_code=200
        def __enter__(self):return self
        def __exit__(self,*_):pass
        def iter_content(self,_):yield b'[]'
    monkeypatch.setattr(a.requests,'get',lambda *args,**kw:calls.append(kw['params']) or Response())
    assert a.run(root)['all_controls_observed'] and len(calls)==36
    before={str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}
    assert not a.run(root)['historical_availability_admitted'] and len(calls)==36
    assert before=={str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}
    (root/'00/body').write_text('[{}]')
    with pytest.raises(ValueError,match='Body drift'):a.run(root)


def test_failed_request_stops_campaign_and_cannot_claim_transport(tmp_path,monkeypatch):
    root=tmp_path/'capture';a.prepare(root);calls=[]
    monkeypatch.setattr(a,'credentials',lambda:dict(metadata=('test-key','test-secret')))
    monkeypatch.setattr(a,'guard',lambda *_:None)
    monkeypatch.setattr(a.time,'sleep',lambda _:None)
    class Response:
        status_code=422
        def __enter__(self):return self
        def __exit__(self,*_):pass
        def iter_content(self,_):yield b'{"error":"bad type"}'
    monkeypatch.setattr(a.requests,'get',lambda *args,**kw:calls.append(1) or Response())
    r=a.run(root)
    assert len(calls)==1 and not r['transport_complete'] and not r['all_controls_observed']
