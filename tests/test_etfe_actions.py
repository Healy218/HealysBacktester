import json
from pathlib import Path
import pytest
import pandas as pd
from nn_meta.etfe.action_capture import prepare,verify,inventory,action_rows,capture,chain,normalize
from nn_meta.etfe.acquisition import sha


def body(symbol='SPY',token=None,ident='id',process='2024-03-20',effective='2024-03-18'):
    return dict(corporate_actions={'cash_dividends':[dict(id=ident,symbol=symbol,process_date=process,ex_date=effective,rate='1.25')]},next_page_token=token)


class Fake:
    def __init__(self,responses):self.responses=iter(responses);self.calls=[]
    def get(self,kind,params,max_bytes):
        self.calls.append((kind,params));return next(self.responses)


def ok(b):return 200,json.dumps(b).encode(),{},None


def run(root,http,budget=64):return capture(root,http,budget=budget,sleep=lambda _:None,resource_guard=lambda *_:None)


def test_resume_normalize_and_probe_rejection(tmp_path):
    root=tmp_path/'study';plan=prepare(root)
    r=run(root,Fake([ok(body(token='next'))]),1);assert not r['capture_complete'] and r['stop_reason']=='request_budget'
    old={str(p.relative_to(root)):sha(p.read_bytes()) for p in root.rglob('*') if p.is_file()}
    http=Fake([ok(body(ident='id2')),ok(body('QQQ')),ok(body('VOO')),(403,b'Forbidden',{},None),(404,b'Not found',{},None)])
    assert run(root,http)['capture_complete'] and http.calls[0][1]['page_token']=='next'
    assert all(sha((root/n).read_bytes())==h for n,h in old.items())
    report=normalize(root);assert report['rows']==4 and not report['historical_availability_verified']
    f=pd.read_parquet(root/'ACTIONS.parquet');assert f.historical_available_at_ns.eq(-1).all()
    assert f.effective_date.eq('2024-03-18').all() and f.process_date.eq('2024-03-20').all()
    from scripts.audit_etfe_actions import audit
    assert audit(root)['occurrences_exact']
    with pytest.raises(FileExistsError):normalize(root)


@pytest.mark.parametrize('bad',[{}, {'corporate_actions':{},'next_page_token':''},body('OTHER'),body(process='2023-12-31')])
def test_reject_schema_symbol_process_date(bad):
    with pytest.raises(ValueError):list(action_rows(bad,inventory()[0]))


def test_null_fields_preserved_without_process_date_fallback(tmp_path):
    root=tmp_path/'study';prepare(root)
    responses=[ok(body(s,process=None,effective=None)) for s in ('SPY','QQQ','VOO')]+[(200,b'',{},None)]*2
    assert run(root,Fake(responses))['capture_complete'];normalize(root)
    f=pd.read_parquet(root/'ACTIONS.parquet');assert f.effective_date.isna().all() and f.process_date.isna().all()


def test_error_not_empty_history_and_retry_exhaustion(tmp_path):
    root=tmp_path/'study';prepare(root)
    r=run(root,Fake([(403,b'Forbidden',{},None)]));assert not r['capture_complete'] and 'failed:403' in r['stop_reason']
    assert not list(root.glob('jobs/*/page-*.json')) and len(list(root.glob('attempts/*/body')))==1
    with pytest.raises(ValueError):normalize(root)


def test_token_cycle_rejected_and_tamper_detected(tmp_path):
    root=tmp_path/'study';plan=prepare(root)
    r=run(root,Fake([ok(body(token='x')),ok(body(token='x',ident='second'))]));assert 'Repeated' in r['stop_reason']
    assert len(list(root.glob('jobs/*/page-*.json')))==1
    pointer=next(root.glob('jobs/*/page-*.json'));attempt=root/json.loads(pointer.read_text())['attempt']
    (attempt/'body').write_bytes(b'{}')
    with pytest.raises(ValueError,match='drift'):chain(root,plan['jobs'][0],plan)


def test_cooldown_blocks_resume(tmp_path):
    root=tmp_path/'study';prepare(root)
    r=run(root,Fake([(429,b'limit',{'retry-after':'120'},None)]));assert r['stop_reason']=='provider_wait_required'
    http=Fake([]);assert run(root,http)['stop_reason']=='provider_wait_pending' and not http.calls


def test_duplicate_native_occurrences_retained(tmp_path):
    root=tmp_path/'study';prepare(root)
    responses=[ok(body(token='next')),ok(body())]+[ok(body(s)) for s in ('QQQ','VOO')]+[(200,b'',{},None)]*2
    assert run(root,Fake(responses))['capture_complete'];r=normalize(root)
    assert r['rows']==4 and r['duplicate_native_ids']==1


def test_plan_mutation_rejected(tmp_path):
    root=tmp_path/'study';prepare(root);p=json.loads((root/'PLAN.json').read_text());p['jobs'][0]['params']['start']='2023-01-01'
    (root/'PLAN.json').write_text(json.dumps(p))
    with pytest.raises(ValueError,match='plan drift'):verify(root)


def test_transient_retry_exhaustion_keeps_raw_attempts(tmp_path):
    root=tmp_path/'study';prepare(root)
    r=run(root,Fake([(503,b'unavailable',{},None)]*5))
    assert r['requests']==5 and r['stop_reason']=='retries_exhausted'
    assert len(list(root.glob('attempts/*/body')))==5 and not list(root.glob('jobs/*/page-*.json'))


def test_credentials_not_retained_from_body_or_headers():
    from nn_meta.etfe.action_capture import HTTP
    class Response:
        status_code=200
        headers={'x-request-id':'secret-value'}
        def __enter__(self):return self
        def __exit__(self,*_):pass
        def iter_content(self,_):yield b'{}'
    class Session:
        def get(self,*_,**kwargs):return Response()
    http=HTTP('key-value','secret-value');http.session=Session()
    assert http.get('actions',{},100)==(None,b'',{},'credential_echo')


def test_sse_complete_blocks_and_truncated_utf8():
    from nn_meta.etfe.action_evidence import parse_sse
    e=dict(at='2026-10-01T00:00:00Z',ca={'id':'a','symbol':'SPY'},event_id='event',action='update')
    raw=b': welcome\r\n\r\ndata: '+json.dumps(e).encode()+b'\r\n\r\ndata: {"cut":"\xc3'
    events,tail=parse_sse(raw)
    assert events==[(1,e)] and tail>0
    assert parse_sse(b': welcome\n\n')==([],0)


def test_sse_multiline_and_duplicate_observations():
    from nn_meta.etfe.action_evidence import parse_sse
    e=dict(at='2026-10-01T00:00:00Z',ca={'id':'a'},event_id='event',action='delete')
    lines=json.dumps(e,indent=2).splitlines();block='\n'.join('data: '+x for x in lines)+'\n\n'
    events,tail=parse_sse((block+block).encode())
    assert len(events)==2 and events[0][1]==events[1][1]==e and tail==0


@pytest.mark.parametrize('patch',[{'at':None},{'at':'2026-10-01'},{'action':'unknown'},{'event_id':None},{'ca':[]}])
def test_sse_invalid_mutations_rejected(patch):
    from nn_meta.etfe.action_evidence import parse_sse
    e=dict(at='2026-10-01T00:00:00Z',ca={},event_id='event',action='insert');e.update(patch)
    with pytest.raises(ValueError):parse_sse(('data: '+json.dumps(e)+'\n\n').encode())


def test_tail_scope_does_not_expand_price_window():
    from nn_meta.etfe.action_evidence import inventory
    jobs=inventory();assert len(jobs)==3
    assert all(j['params']['start']=='2026-10-03' and j['params']['end']=='2026-12-31' for j in jobs)
    assert {j['params']['symbols'] for j in jobs}=={'SPY','QQQ','VOO'}


def test_tail_capture_pagination_and_resume(tmp_path,monkeypatch):
    from nn_meta.etfe import action_evidence as tail
    plan=dict(sha256='a'*64,jobs=tail.inventory(),limits=dict(max_requests=32,max_seconds=900,max_page_bytes=1024,max_root_bytes=2**20))
    monkeypatch.setattr(tail,'verify',lambda _:plan)
    def call(http,budget=32):return tail.run(tmp_path,http,budget=budget,sleep=lambda _:None,resource_guard=lambda *_:None)
    first=Fake([ok(body(token='next',process='2026-10-30',effective='2026-09-18'))])
    assert call(first,1)['stop_reason']=='request_budget'
    old={str(p.relative_to(tmp_path)):sha(p.read_bytes()) for p in tmp_path.glob('attempts/*/*')}
    responses=[ok(body(ident='other',process='2026-10-30',effective='2026-09-18')),
        ok(body('QQQ',process='2026-10-08',effective='2026-09-21')),ok(dict(corporate_actions={},next_page_token=None))]
    http=Fake(responses);assert call(http)['capture_complete']
    assert http.calls[0][1]['page_token']=='next'
    assert all(sha((tmp_path/n).read_bytes())==h for n,h in old.items())


def test_tail_rate_limit_blocks_followup(tmp_path,monkeypatch):
    from nn_meta.etfe import action_evidence as tail
    monkeypatch.setattr(tail,'verify',lambda _:dict(sha256='a'*64,jobs=tail.inventory(),limits=dict(max_requests=32,max_seconds=900,max_page_bytes=1024,max_root_bytes=2**20)))
    def call(http):return tail.run(tmp_path,http,sleep=lambda _:None,resource_guard=lambda *_:None)
    assert call(Fake([(429,b'limit',{'retry-after':'120'},None)]))['stop_reason']=='provider_wait_required'
    http=Fake([]);assert call(http)['stop_reason']=='provider_wait_pending' and not http.calls
