import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from nn_meta.v7.packed_references import PackedContractReferences, query, write_pack
from nn_meta.v7.contracts import ContractReferences
from nn_meta.v7.storage import identity, receipt, verify

CONTRACT='AAPL260918C00200000'
DAY='2026-09-14'


def response(**changes):
    row=dict(ticker='O:'+CONTRACT,underlying_ticker='AAPL',expiration_date='2026-09-18',
             contract_type='call',strike_price=200,shares_per_contract=100,
             exercise_style='american',primary_exchange='XNAS')
    row.update(changes)
    return json.dumps(dict(status='OK',results=row)).encode()


def record(body=None,status=200):
    return CONTRACT,DAY,status,response() if body is None else body,dict(
        query=query(CONTRACT,DAY),retrieved_at='2026-09-28T17:00:00+00:00',
        historical_publication_vintage_verified=False)


def test_exact_legacy_consumer_parity_and_raw_provenance(tmp_path):
    pack=tmp_path/'pack';binding=dict(requests=1)
    write_pack(pack,[record()],binding)
    legacy=tmp_path/'legacy'/CONTRACT/DAY;legacy.mkdir(parents=True)
    (legacy/'response.json').write_bytes(response())
    receipt(legacy,dict(identity=identity(query(CONTRACT,DAY)),query=query(CONTRACT,DAY),http_status=200))
    reader=PackedContractReferences([pack])
    actual=dict(reader.standard(CONTRACT,DAY));expected=dict(ContractReferences(tmp_path/'legacy').standard(CONTRACT,DAY))
    actual.pop('metadata_receipt_sha256');expected.pop('metadata_receipt_sha256')
    assert actual==expected
    assert str(pack/'complete.json') in reader.inputs
    with sqlite3.connect(pack/'references.sqlite3') as db:
        body,digest=db.execute('SELECT body,body_sha256 FROM responses').fetchone()
    assert body==response() and hashlib.sha256(body).hexdigest()==digest
    reader.close()


@pytest.mark.parametrize('status,changes,admission',[(404,{},'unavailable_404'),(200,{'shares_per_contract':150},'nonstandard'),(200,{'ticker':'O:WRONG'},'nonstandard')])
def test_missing_and_nonstandard_remain_unadmitted(tmp_path,status,changes,admission):
    pack=tmp_path/'pack'
    report=write_pack(pack,[record(response(**changes),status)],dict(requests=1))
    assert report[admission]==1 and report['standard']==0
    reader=PackedContractReferences([pack])
    with pytest.raises(ValueError):reader.standard(CONTRACT,DAY)
    reader.close()


def test_missing_pair_and_tampering_fail_closed(tmp_path):
    pack=tmp_path/'pack';write_pack(pack,[record()],dict(requests=1))
    reader=PackedContractReferences([pack])
    with pytest.raises(FileNotFoundError):reader.standard(CONTRACT,'2026-09-15')
    with sqlite3.connect(pack/'references.sqlite3') as db:db.execute('UPDATE responses SET body=?',(b'{}',))
    with pytest.raises(ValueError,match='integrity'):reader.standard(CONTRACT,DAY)
    with pytest.raises(ValueError,match='integrity'):PackedContractReferences([pack])
    reader.close()


def test_incomplete_batch_never_publishes_receipt(tmp_path):
    pack=tmp_path/'pack'
    with pytest.raises(ValueError,match='Incomplete'):
        write_pack(pack,[record()],dict(requests=2))
    assert not pack.exists()
    assert len(list(tmp_path.glob('pack.partial-*')))==1


def test_reused_capture_preserves_original_anchor(tmp_path):
    c,d,s,b,m=record();m['original_receipt_sha256']='original'
    report=write_pack(tmp_path/'pack',[(c,d,s,b,m)],dict(requests=1))
    assert report['reused']==1
    with sqlite3.connect(tmp_path/'pack/references.sqlite3') as db:
        assert json.loads(db.execute('SELECT receipt_json FROM responses').fetchone()[0])['original_receipt_sha256']=='original'


def test_http_fetch_retries_and_bounds_raw_body(monkeypatch):
    from scripts import run_v7_reference_campaign as campaign
    class R:
        def __init__(self,status,body):self.status_code=status;self.body=body
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def iter_content(self,n):yield self.body
    class Session:
        calls=0
        def get(self,*args,**kwargs):
            self.calls+=1
            assert kwargs['params']=={'as_of':DAY} and kwargs['allow_redirects'] is False
            return R(429,b'') if self.calls==1 else R(200,response())
    s=Session();monkeypatch.setattr(campaign.LOCAL,'session',s,raising=False)
    monkeypatch.setenv('MASSIVE_API_KEY','test');monkeypatch.setattr(campaign.time,'sleep',lambda _:None)
    result=campaign.fetch((CONTRACT,DAY,None))
    assert s.calls==2 and result[3]==response()
    monkeypatch.setattr(s,'get',lambda *a,**k:R(200,b'x'*65537))
    with pytest.raises(ValueError,match='bounded'):campaign.fetch((CONTRACT,DAY,None))


def test_sealed_demand_jobs_and_existing_pack_reuse(tmp_path,monkeypatch):
    from scripts import run_v7_reference_campaign as campaign
    plan=tmp_path/'plan';source=tmp_path/'plan.checkpoints'/'sid';source.mkdir(parents=True)
    with sqlite3.connect(source/'references.sqlite3') as db:
        db.execute('CREATE TABLE requests(contract,date)');db.execute('INSERT INTO requests VALUES(?,?)',(CONTRACT,DAY))
    receipt(source,{'identity':'source'})
    plan.mkdir();(plan/'report.json').write_text(json.dumps({'checkpoints':{'sid':campaign.sha(source/'complete.json')}}))
    jobs=list(campaign.batch_jobs(plan,256,{(CONTRACT,DAY):'retained'}))
    assert jobs[0][2]==[(CONTRACT,DAY,'retained')]
    pack=tmp_path/'pack';binding=dict(requests=1);write_pack(pack,[record()],binding)
    report=campaign.acquire(dict(destination=str(pack),binding=binding,budget=str(tmp_path)),None)
    assert report['status']=='reused_pack'
    with pytest.raises(ValueError,match='identity'):
        campaign.acquire(dict(destination=str(pack),binding=dict(requests=2),budget=str(tmp_path)),None)
