import json
import pytest
from nn_meta.etfe import action_replay as ar
from nn_meta.etfe.acquisition import sha


def event(ident='a',at='2026-09-17T01:00:00Z',**kw):
    return dict(event_id=ident,at=at,ca={'id':'action','symbol':'SPY','ex_date':'2026-09-18','rate':'1.2'},action='update',region='us',event_type='cash_dividend_corporateaction_event',**kw)


def raw(events,tail=b''):return b': welcome\n\n'+b''.join(b'data: '+json.dumps(e).encode()+b'\n\n' for e in events)+tail


def receipt(error=None,since='2026-09-17T00:00:00Z'):
    return dict(status=200,error=error,headers={'content-type':'text/event-stream'},params={'since':since})

JOB=dict(day='2026-09-17',start='2026-09-17T00:00:00Z',end='2026-09-17T23:59:59.999999999Z')


def test_complete_and_capped_cursor():
    e=event();events,eof,cursor,tail=ar.parse_page(raw([e],b'data: {'),receipt('byte_limit'),JOB)
    assert events[0][1]==e and not eof and cursor==e['at'] and tail==7
    assert ar.parse_page(raw([]),receipt(),JOB)[1] is True


@pytest.mark.parametrize('change',['bounds','filter','region','backwards','conflict','eof_fragment','empty_cap'])
def test_reject_invalid_page(change):
    es=[event()];r=receipt();tail=b''
    if change=='bounds':es[0]['at']='2026-09-16T23:00:00Z'
    if change=='filter':es[0]['event_type']='other'
    if change=='region':es[0]['region']='non_us'
    if change=='backwards':es.append(event('b','2026-09-17T00:01:00Z'))
    if change=='conflict':es.append(event(at='2026-09-17T02:00:00Z'))
    if change=='eof_fragment':tail=b'data: {'
    if change=='empty_cap':es=[];r=receipt('byte_limit')
    with pytest.raises(ValueError):ar.parse_page(raw(es,tail),r,JOB)


class Fake:
    def __init__(self,values):self.values=iter(values);self.calls=[]
    def get(self,kind,params,max_bytes):self.calls.append(params);return next(self.values)


def response(es,error=None):return 200,raw(es),{'content-type':'text/event-stream'},error


def setup(monkeypatch):
    plan=dict(sha256='a'*64,jobs=[JOB],type_filter='cash_dividend_corporateaction_event',limits=dict(max_requests=96,max_seconds=900,max_page_bytes=4096,max_root_bytes=2**20,max_day_bytes=2**19,max_total_bytes=2**20))
    monkeypatch.setattr(ar,'verify',lambda _:plan);return plan


def run(root,http,budget=96):return ar.run(root,http,budget=budget,sleep=lambda _:None,resource_guard=lambda *_:None)


def test_inclusive_equal_time_resume_and_tamper(tmp_path,monkeypatch):
    plan=setup(monkeypatch);a=event();b=event('b');c=event('c','2026-09-17T02:00:00Z')
    assert run(tmp_path,Fake([response([a],'byte_limit')]),1)['stop_reason']=='request_budget'
    before={str(p.relative_to(tmp_path)):sha(p.read_bytes()) for p in tmp_path.glob('attempts/*/*')}
    h=Fake([response([a,b,c])]);assert run(tmp_path,h)['transport_complete'] and h.calls[0]['since']==a['at']
    assert all(sha((tmp_path/n).read_bytes())==v for n,v in before.items())
    pages,_,done,_=ar.committed(tmp_path,JOB,plan);assert done and [p['new_events'] for p in pages]==[1,2]
    (tmp_path/pages[0]['attempt']/'body').write_bytes(b'bad')
    with pytest.raises(ValueError,match='drift'):ar.committed(tmp_path,JOB,plan)


@pytest.mark.parametrize('conflict',[False,True])
def test_nonprogress_and_overlap_conflict(tmp_path,monkeypatch,conflict):
    setup(monkeypatch);a=event();other=event();other['ca']['rate']='2.0'
    r=run(tmp_path,Fake([response([a],'byte_limit'),response([other if conflict else a],'byte_limit')]))
    assert 'Conflicting' in r['stop_reason'] if conflict else 'no progress' in r['stop_reason']
    assert len(list(tmp_path.glob('days/*/page-*.json')))==1


def test_rate_limit_and_retry_receipt(tmp_path,monkeypatch):
    setup(monkeypatch);r=run(tmp_path,Fake([(429,b'limit',{'retry-after':'120'},None)]))
    assert r['stop_reason']=='provider_wait_required'
    h=Fake([]);assert run(tmp_path,h)['stop_reason']=='provider_wait_pending' and not h.calls
