import json

import pytest
import requests

from nn_meta.etfe.preparation import (
    SCOPE, build_catalog, digest, end_exclusive_utc, file_sha, save_new, validate_scope,
)
from nn_meta.etfe.alpaca_probe import ReadOnlyProbe, select_contract


@pytest.fixture
def scope():
    return json.loads(SCOPE.read_text())


def test_all_variants_preserved_with_new_identity_and_minute_scope(scope):
    from nn_meta import config
    from nn_meta.tradingview_proposals import SWEEP_GRIDS
    from nn_meta.multitimeframe_catalog import build_catalog as old_catalog
    legacy = {k:v for k,v in config.SWEEP_GRIDS.items() if k not in SWEEP_GRIDS}
    result = build_catalog(scope, legacy, SWEEP_GRIDS)
    old = old_catalog(scope['symbols'], legacy, SWEEP_GRIDS)
    assert result['variants_per_symbol'] == 8451
    assert result['ticker_variant_combinations'] == 25353
    assert result['families'] == old['families']
    expected = {(r['strategy'],json.dumps(r['params'],sort_keys=True))
                for r in old['records'] if r['signal_minutes']==5}
    for tf in [1,5,15]:
        assert {(r['strategy'],json.dumps(r['params'],sort_keys=True))
                for r in result['records'] if r['signal_minutes']==tf} == expected
    assert not {r['variant_id'] for r in old['records']} & {r['variant_id'] for r in result['records']}
    assert not any(r['signal_minutes']==30 for r in result['records'])
    assert old['signal_minutes'] == [5,15,30]
    assert result['ready_for_build'] is False


@pytest.mark.parametrize('key,value', [
    ('symbols',['SPY','QQQ']), ('signal_minutes',[5,15,30]),
    ('options_provider','massive'), ('options_feed','indicative'),
    ('allow_massive_quotes',True), ('reuse_v7_checkpoints',True),
    ('reuse_model_weights',True), ('ready_for_build',True),
])
def test_scope_changes_require_new_explicit_contract(scope,key,value):
    scope[key] = value
    with pytest.raises(ValueError):
        validate_scope(scope)


def test_unverified_start_and_fixed_inclusive_end(scope):
    assert scope['history']['verified_start_utc'] is None
    assert end_exclusive_utc(scope) == '2026-10-03T04:00:00+00:00'
    scope['history']['end_date_inclusive'] = '2026-10-03'
    with pytest.raises(ValueError):
        validate_scope(scope)


def test_saved_artifact_cannot_be_overwritten(tmp_path):
    p=tmp_path/'plan.json'
    save_new(p,{'first':1})
    with pytest.raises(FileExistsError):
        save_new(p,{'first':2})
    assert json.loads(p.read_text())=={'first':1}


class Response:
    def __init__(self,body,status=200):
        self.body=body
        self.status_code=status
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def iter_content(self,size): yield self.body


class Session:
    def __init__(self,response): self.response=response;self.calls=[]
    def get(self,url,**kwargs):
        self.calls.append((url,kwargs))
        if isinstance(self.response,Exception): raise self.response
        return self.response


def client(tmp_path,response,**kwargs):
    session=Session(response)
    credentials={'data':('test-data-key-long','test-data-secret-long'),
                 'metadata':('test-metadata-key-long','test-metadata-secret-long')}
    return ReadOnlyProbe(tmp_path/'probe',credentials,session=session,**kwargs),session


def test_probe_retains_404_and_does_not_follow_redirect_or_fallback(tmp_path):
    c,s=client(tmp_path,Response(b'{"message":"not found"}',404))
    r,b=c.get('historical_quotes',{'symbols':'SPY240201C00490000'})
    assert r['status_code']==404 and r['complete_history'] is False
    assert len(s.calls)==1
    assert s.calls[0][0]=='https://data.alpaca.markets/v1beta1/options/quotes'
    assert s.calls[0][1]['allow_redirects'] is False
    assert not any('test-data-secret-long' in p.read_text() for p in c.output.iterdir())
    with pytest.raises(ValueError,match='allowlisted'):
        c.get('https://api.massive.com',{})
    assert len(s.calls)==1


def test_probe_pagination_does_not_claim_complete_history(tmp_path):
    c,s=client(tmp_path,Response(b'{"bars":{},"next_page_token":"more"}'),max_requests=1)
    r,_=c.get('option_bars',{'limit':1})
    assert r['next_page_available'] is True and r['complete_history'] is False
    with pytest.raises(ValueError,match='budget'):
        c.get('option_bars',{'limit':1})


def test_transport_failure_does_not_leak_exception_or_claim_empty_market(tmp_path):
    c,_=client(tmp_path,requests.ConnectionError('test-data-secret-long'))
    r,b=c.get('calendar',{})
    assert r['transport_error']=='request_failed' and r['status_code'] is None and b is None
    assert 'test-data-secret-long' not in next(c.output.glob('*.json')).read_text()


def test_response_byte_budget_stops_before_persisting_payload(tmp_path):
    c,_=client(tmp_path,Response(b'x'*100),max_response_bytes=10)
    with pytest.raises(ValueError,match='byte budget'):
        c.get('option_trades',{})
    assert not list(c.output.glob('*.body'))


def test_unexpected_credential_echo_never_written(tmp_path):
    c,_=client(tmp_path,Response(b'{"echo":"test-data-secret-long"}'))
    with pytest.raises(ValueError,match='credential material'):
        c.get('option_bars',{})
    assert not list(c.output.glob('*.body'))


def test_contract_example_must_belong_to_requested_underlying():
    body={'option_contracts':[{'underlying_symbol':'SPY','symbol':'QQQ240216C00400000'}]}
    assert select_contract(body,'SPY') is None
    body['option_contracts'].append({'underlying_symbol':'SPY','symbol':'SPY240216C00490000'})
    assert select_contract(body,'SPY')=='SPY240216C00490000'


@pytest.fixture
def frozen_setup(tmp_path,scope):
    root=tmp_path/'repo'
    declared=root/'docs/specs/ETFE_SCOPE_20261003.json'
    declared.parent.mkdir(parents=True)
    declared.write_text(json.dumps(scope))
    source=root/'producer.py'
    source.write_text('# frozen setup producer\n')
    out=root/'setup'
    out.mkdir()
    catalog=dict(expert='etfe',symbols=scope['symbols'],signal_minutes=[1,5,15],
        families={'example':1},variants_per_symbol=3,ticker_variant_combinations=9,
        ready_for_build=False)
    catalog['catalog_sha256']=digest(catalog)
    plan=dict(scope=scope,scope_sha256=file_sha(declared),catalog_sha256=catalog['catalog_sha256'],
        runtime=dict(pool='etfe',provider='alpaca'),
        readiness=dict(ready_for_build=False,ready_for_training=False),
        source_bindings={'producer.py':file_sha(source)})
    plan['plan_sha256']=digest(plan)
    for name,obj in [('scope.json',scope),('catalog.json',catalog),('plan.json',plan)]:
        save_new(out/name,obj)
    save_new(out/'PREPARED.json',dict(status='prepared_not_admitted',expert='etfe',
        files={n:file_sha(out/n) for n in ['scope.json','catalog.json','plan.json']},
        plan_sha256=plan['plan_sha256']))
    return root,out


def test_integrity_verifier_distinguishes_original_and_normalized_scope(frozen_setup):
    from nn_meta.etfe.verification import verify_setup
    root,out=frozen_setup
    assert file_sha(root/'docs/specs/ETFE_SCOPE_20261003.json')!=file_sha(out/'scope.json')
    result=verify_setup(out,source_root=root)
    assert result['ready_for_training'] is False


@pytest.mark.parametrize('target',['source','catalog','scope_declaration'])
def test_integrity_verifier_rejects_changed_sources_or_artifacts(frozen_setup,target):
    from nn_meta.etfe.verification import verify_setup
    root,out=frozen_setup
    paths={'source':root/'producer.py','catalog':out/'catalog.json',
           'scope_declaration':root/'docs/specs/ETFE_SCOPE_20261003.json'}
    paths[target].write_text(paths[target].read_text()+'\n')
    with pytest.raises(ValueError):verify_setup(out,source_root=root)
