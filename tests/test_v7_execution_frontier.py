import json
from types import SimpleNamespace
import pandas as pd
import pytest
from nn_meta.v7.execution import CaptureUnavailable
from nn_meta.v7.execution_frontier import discover_execution
from nn_meta.v7.replay import replay


def case(tmp_path):
    from nn_meta.v7.quote_archive import QuoteArchive
    from nn_meta.v7.execution import QuotePolicy
    from nn_meta.v7.contracts import ContractReferences
    from nn_meta.v7.storage import identity,receipt
    entry=pd.Timestamp('2022-03-15T13:31Z').value;stop=entry+3*60*10**9
    contract='OLD220318C00100000'
    class Archive(QuoteArchive):
        policy=QuotePolicy()
        def __init__(self):pass
        def window(self,c,kind,start,end):
            rows=[dict(sip_timestamp=t,bid_price=(.79 if t>=stop else .99),
                ask_price=(.81 if t>=stop else 1.01),bid_size=10,ask_size=10)
                for t in range(entry-30*10**9,entry+10*60*10**9,10**9) if start<=t<end]
            return rows,dict(schema='massive-option-ticks-v1',provider='massive',contract='O:'+c,
                kind=kind,start_ns=start,end_ns=end,complete=True,records=len(rows),records_sha256=identity(rows))
    root=tmp_path/'references';source=root/contract/'2022-03-15';source.mkdir(parents=True)
    (source/'response.json').write_text(json.dumps(dict(status='OK',results=dict(ticker='O:'+contract,
        underlying_ticker='OLD',expiration_date='2022-03-18',contract_type='call',strike_price=100.,
        shares_per_contract=100,exercise_style='american',primary_exchange='XCBO'))))
    receipt(source,dict(query=dict(path='/v3/reference/options/contracts/O:'+contract,params=dict(as_of='2022-03-15')),http_status=200))
    sessions=SimpleNamespace(at=lambda s,d:dict(close_ns=pd.Timestamp(d+'T20:00Z').value),
        cutoff=lambda c:pd.Timestamp('2022-03-18T19:45Z').value)
    engine=SimpleNamespace(archive=Archive(),references=ContractReferences(root),sessions=sessions)
    p=dict(proposal_id='fixture',symbol='OLD',right='C',decision_ns=entry,exit_decision_ns=None)
    return p,list(range(entry,entry+10*60*10**9,60*10**9)),engine,contract


def test_frontier_equals_actual_completed_replay_and_has_no_missing_requests(tmp_path):
    p,clocks,e,c=case(tmp_path)
    expected=replay(p,clocks,e.archive,e.references,select_contract=lambda t:c,
        expiry_cutoff=e.sessions.cutoff,session_close=lambda t:e.sessions.at('OLD','2022-03-15')['close_ns'])
    found=discover_execution(p,clocks,e.archive,e.references,e.sessions,select_contract=lambda t:c)
    assert found['replay']==expected and found['replay']['label_complete']
    assert not found['pending'] and found['complete_frontier']
    assert {'entry_purchase','held_mark'}<={r.get('purpose') for r in found['observed_inputs']}
    assert not found['research_ready']


def test_missing_entry_records_exact_inclusive_deadline_without_guessing_fill(tmp_path):
    p,clocks,e,c=case(tmp_path)
    def missing(*args):raise CaptureUnavailable('missing')
    archive=SimpleNamespace(policy=e.archive.policy,window=missing)
    found=discover_execution(p,clocks,archive,e.references,e.sessions,select_contract=lambda t:c)
    request,=found['pending']
    assert request['start_ns']==p['decision_ns']+10**9
    assert request['end_ns']==p['decision_ns']+60*10**9+1
    assert request['purpose']=='entry_purchase'
    assert not found['replay']['fills'] and found['replay']['net_return'] is None


def test_missing_mark_latches_before_later_exit_or_roll_and_preserves_buy(tmp_path):
    p,clocks,e,c=case(tmp_path)
    calls=[]
    def window(contract,kind,start,end):
        calls.append((start,end))
        if len(calls)>1:raise CaptureUnavailable('held mark missing')
        return e.archive.window(contract,kind,start,end)
    archive=SimpleNamespace(policy=e.archive.policy,window=window)
    found=discover_execution(p,clocks,archive,e.references,e.sessions,select_contract=lambda t:c)
    assert len(calls)==2 and len(found['pending'])==1
    assert found['pending'][0]['purpose']=='held_mark'
    assert len(found['replay']['fills'])==1 and found['replay']['open_positions']
    assert found['replay']['net_return'] is None


def test_reference_gap_and_approved_blackout_are_distinct(tmp_path):
    from tests.test_v7_contract_blackouts import policy_at
    from nn_meta.v7.contract_blackouts import BlackoutReferences
    p,clocks,e,c=case(tmp_path)
    def missing(*args):raise FileNotFoundError('not captured')
    found=discover_execution(p,clocks,e.archive,SimpleNamespace(standard=missing),e.sessions,select_contract=lambda t:c)
    assert found['pending'][0]['kind']=='contract_reference'
    policy=policy_at(tmp_path/'policy')
    found=discover_execution(p,clocks,e.archive,BlackoutReferences(e.references,policy),e.sessions,select_contract=lambda t:c)
    assert found['pending']==[] and found['replay']['status']=='excluded_contract_reference_blackout'
    assert not found['complete_frontier'] and not found['replay']['label_complete']


def test_expiry_stock_gap_and_roll_purchase_use_actual_consumers():
    from nn_meta.v7.execution import QuotePolicy
    from nn_meta.v7.storage import identity
    entry=pd.Timestamp('2022-03-07T14:31Z').value
    roll=pd.Timestamp('2022-03-09T20:45Z').value
    old='SPY220309C00420000';new='SPY220311C00420000'
    def window(contract,kind,start,end):
        if contract==new:raise CaptureUnavailable('uncaptured roll')
        rows=[dict(sip_timestamp=start,bid_price=.99,ask_price=1.01,bid_size=10,ask_size=10)]
        return rows,dict(schema='massive-option-ticks-v1',provider='massive',contract='O:'+contract,
            kind=kind,start_ns=start,end_ns=end,complete=True,records=1,records_sha256=identity(rows))
    archive=SimpleNamespace(policy=QuotePolicy(),window=window)
    refs=SimpleNamespace(standard=lambda c,d:dict(underlying='SPY',right='C',metadata_receipt_sha256='fixture'))
    sessions=SimpleNamespace(at=lambda s,d:dict(close_ns=pd.Timestamp(d+'T21:00Z').value),
        cutoff=lambda c:roll if c==old else pd.Timestamp('2022-03-11T20:45Z').value)
    p=dict(proposal_id='fixture',symbol='SPY',right='C',decision_ns=entry,exit_decision_ns=None)
    no_stock=discover_execution(p,[entry,roll],archive,refs,sessions,select_contract=lambda t:old)
    assert no_stock['pending'][0]['kind']=='stock_quotes'
    assert len(no_stock['replay']['fills'])==1 and no_stock['replay']['net_return'] is None
    def choose(t):return old if t==entry else new
    rolled=discover_execution(p,[entry,roll],archive,refs,sessions,select_contract=choose,
        underlying_mark=lambda s,t:dict(price=400.,sip_timestamp=t))
    assert rolled['pending'][0]['purpose']=='roll_purchase'
    assert len(rolled['replay']['fills'])==2 and not rolled['replay']['open_positions']
    assert rolled['replay']['net_return'] is None
