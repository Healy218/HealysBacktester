import hashlib
import json
import pytest
from nn_meta.v7.epoch_references import list_terms

C='GME220722C00155000';D='2022-07-22'

def response(**changes):
    row=dict(ticker='O:'+C,underlying_ticker='GME',expiration_date=D,contract_type='call',
             strike_price=155,shares_per_contract=100,exercise_style='american',primary_exchange='BATO')
    row.update(changes)
    raw=json.dumps(dict(status='OK',results=[row])).encode()
    m=dict(query=dict(path='/v3/reference/options/contracts',params=dict(underlying_ticker='GME',expiration_date=D,
          strike_price=155,contract_type='call',as_of=D,expired='true',limit=1000)),missing_row_receipt_sha256='missing',
          response_sha256=hashlib.sha256(raw).hexdigest(),http_status=200,pagination_complete=True,
          exact_matches=int(row['ticker']=='O:'+C))
    return raw,json.dumps(m)

def test_exact_list_keeps_real_list_provenance():
    raw,meta=response();r=list_terms(C,D,'true',raw,meta,'missing')
    assert r['contract']==C and r['multiplier']==100
    assert r['reference_source']=='exact_dated_contract_list'
    assert r['metadata_receipt_sha256']==hashlib.sha256(meta.encode()).hexdigest()

def test_other_contract_is_not_renamed_into_requested_contract():
    assert list_terms(C,D,'true',*response(ticker='O:GME220729C00155000'),'missing') is None

@pytest.mark.parametrize('changes',[{'shares_per_contract':400},{'additional_underlyings':[{'underlying':'USD','amount':1}]}])
def test_nonstandard_match_is_not_admitted(changes):
    with pytest.raises(ValueError,match='standard'):list_terms(C,D,'true',*response(**changes),'missing')

def test_wrong_day_or_receipt_fails_closed():
    for day,anchor in [('2022-07-21','missing'),(D,'different')]:
        with pytest.raises(ValueError,match='integrity'):list_terms(C,day,'true',*response(),anchor)

def test_body_tampering_fails_closed():
    raw,meta=response()
    with pytest.raises(ValueError,match='integrity'):list_terms(C,D,'true',raw+b' ',meta,'missing')


def test_pending_plan_keeps_whole_original_target_membership():
    import sqlite3
    from scripts.plan_v7_pending_replay import selected_cohorts,pending_targets
    db=sqlite3.connect(':memory:')
    db.execute('CREATE TABLE jobs(symbol,decision_ns,exit_ns,censored_ns,is_put,exit_symbol,multiplicity)')
    rows=[('AAPL',10,20,-1,0,'AAPL',3),('AAPL',10,30,-1,0,'AAPL',5),('AAPL',11,30,-1,0,'AAPL',7)]
    db.executemany('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',rows)
    entry=dict(key=['AAPL',10,0],targets=[5],horizons=2,proposals=8)
    assert list(selected_cohorts(db,[entry]))==[(('AAPL',10,0),rows[:2])]
    with pytest.raises(ValueError,match='membership'):list(selected_cohorts(db,[{**entry,'horizons':1}]))
    with pytest.raises(ValueError,match='Duplicate'):list(selected_cohorts(db,[entry,entry]))
    db.execute('CREATE TABLE buckets(bucket_id,target,coverage)');db.execute('CREATE TABLE links(bucket_id,request_id)')
    for target in [5,30]:db.execute('INSERT INTO buckets VALUES(?,?,?)',(str(target),target,json.dumps(dict(source_key=list(rows[0][:6]),target_dte=target))))
    db.executemany('INSERT INTO links VALUES(?,?)',[('5','one'),('5','two')])
    assert pending_targets(db)=={('AAPL',10,0):{5}}
