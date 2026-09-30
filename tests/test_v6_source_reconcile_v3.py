from datetime import datetime,timedelta,timezone
import json,sqlite3
from types import SimpleNamespace as NS

import pytest

from integrations.alpaca_paper.v6_source_reconcile_v3 import retire_unfilled_sources
from integrations.alpaca_paper.v6_bridge import Journal,events_from_fresh_state

NOW=datetime(2026,9,28,19,0,tzinfo=timezone.utc)


def setup(tmp_path):
    path=tmp_path/'portfolio.sqlite3'
    at=NOW-timedelta(minutes=10)
    source=dict(event_id='idea|entry|0',position_key='idea',contract='ANF261106P00134000',
                at=at.isoformat(),signal_close=at.isoformat(),roll=0,kind='entry',size_fraction=.1)
    position=dict(key='idea',symbol='ANF',state='open',contract=source['contract'],
                  opened_at=at.isoformat(),rolls=0,legs=[])
    payload=json.dumps(position)
    with sqlite3.connect(path) as db:
        db.executescript('''CREATE TABLE positions(key TEXT PRIMARY KEY,symbol,state,payload);
            CREATE TABLE metadata(key PRIMARY KEY,value);
            CREATE TABLE broker_source_entries(key,roll,payload);
            CREATE TABLE events(key,recorded_at,kind,payload);''')
        db.execute('INSERT INTO positions VALUES(?,?,?,?)',('idea','ANF','open',payload))
        db.execute("INSERT INTO metadata VALUES('equity','1.0')")
        db.execute('INSERT INTO broker_source_entries VALUES(?,?,?)',('idea',0,json.dumps(source)))
    return path,Journal(tmp_path/'broker.sqlite3'),source,payload


def test_expired_never_submitted_source_archived_without_inventing_pnl(tmp_path):
    p,j,e,payload=setup(tmp_path)
    result=retire_unfilled_sources(p,j,{}, {},now=NOW)
    assert len(result)==1
    with sqlite3.connect(p) as db:
        assert db.execute('select count(*) from positions').fetchone()[0]==0
        assert db.execute('select original_payload from broker_unfilled_sources').fetchone()[0]==payload
        assert db.execute('select value from metadata where key="equity"').fetchone()[0]=='1.0'
        assert db.execute('select count(*) from events').fetchone()[0]==0
    assert events_from_fresh_state(p,activated_at=NOW-timedelta(days=1))==[e]
    assert retire_unfilled_sources(p,j,{}, {},now=NOW)==[]


@pytest.mark.parametrize('state,filled,retired',[
    ('new','0',False),('pending_cancel','0',False),('uncertain_post',None,False),
    ('partially_filled','1',False),('canceled','1',False),('filled','2',False),
    ('canceled','0',True),('rejected','0',True)])
def test_pending_ambiguous_and_any_fill_protect_the_source(tmp_path,state,filled,retired):
    p,j,e,payload=setup(tmp_path)
    plan=dict(client_order_id='id',contract=e['contract'],qty=2)
    j.intent(e,plan);j.update(e['event_id'],state=state,filled_qty=filled)
    result=retire_unfilled_sources(p,j,{}, {r['client_order_id']:r for r in j.all()},now=NOW)
    assert bool(result)==retired


def test_broker_holding_and_open_entry_window_are_preserved(tmp_path):
    p,j,e,payload=setup(tmp_path)
    assert not retire_unfilled_sources(p,j,{e['contract']:NS(qty='1')},{},now=NOW)
    assert not retire_unfilled_sources(p,j,{}, {},now=NOW-timedelta(minutes=5))
    with sqlite3.connect(p) as db:assert db.execute('select payload from positions').fetchone()[0]==payload


def test_rolls_and_prior_simulated_legs_require_separate_reconciliation(tmp_path):
    p,j,e,payload=setup(tmp_path)
    pos=json.loads(payload);pos['rolls']=1
    with sqlite3.connect(p) as db:db.execute('update positions set payload=?',(json.dumps(pos),))
    assert not retire_unfilled_sources(p,j,{}, {},now=NOW)


def test_mismatched_source_rolls_back_without_archiving(tmp_path):
    p,j,e,payload=setup(tmp_path);e['contract']='WRONG'
    with sqlite3.connect(p) as db:db.execute('update broker_source_entries set payload=?',(json.dumps(e),))
    with pytest.raises(ValueError,match='differs'):retire_unfilled_sources(p,j,{}, {},now=NOW)
    with sqlite3.connect(p) as db:assert db.execute('select payload from positions').fetchone()[0]==payload


def historical_round_trip(j,e,*,closed=True):
    old=dict(e,event_id='older|entry|0',position_key='older')
    j.intent(old,dict(client_order_id='old-buy',contract=e['contract'],qty=3))
    j.update(old['event_id'],state='filled',filled_qty='3')
    if closed:
        exit=dict(old,event_id='older|close|0',kind='close')
        j.intent(exit,dict(client_order_id='old-sell',contract=e['contract'],qty=3))
        j.update(exit['event_id'],state='filled',filled_qty='3')
    return {r['client_order_id']:r for r in j.all()}


def test_closed_previous_signal_does_not_protect_new_unfilled_same_contract(tmp_path):
    p,j,e,payload=setup(tmp_path);recorded=historical_round_trip(j,e)
    before=j.all()
    assert len(retire_unfilled_sources(p,j,{},recorded,now=NOW))==1
    assert j.all()==before
    with sqlite3.connect(p) as db:
        saved,evidence=db.execute('select original_payload,evidence from broker_unfilled_sources').fetchone()
        assert saved==payload and json.loads(evidence)['contract_net_fills']=='0'
        assert db.execute('select count(*) from broker_source_entries').fetchone()[0]==1


@pytest.mark.parametrize('guard',['net_fill','pending_other','unknown_fill','active_chain','broker_holding'])
def test_same_contract_other_signal_guards_are_preserved(tmp_path,guard):
    from integrations.alpaca_paper.v6_bridge_v4 import Journal as StepJournal
    p,j,e,payload=setup(tmp_path);j=StepJournal(j.path)
    recorded=historical_round_trip(j,e,closed=guard!='net_fill')
    positions={}
    if guard in ['pending_other','unknown_fill']:
        old=dict(e,event_id='third|entry|0',position_key='third')
        j.intent(old,dict(client_order_id='third',contract=e['contract'],qty=3))
        j.update(old['event_id'],state='pending_cancel' if guard=='pending_other' else 'canceled',
                 filled_qty='0' if guard=='pending_other' else None)
        recorded={r['client_order_id']:r for r in j.all()}
    if guard=='active_chain':
        j.save_chain(dict(event=dict(e,event_id='third|entry|0',position_key='third'),state='active',plan={}))
    if guard=='broker_holding':positions={e['contract']:NS(qty='3')}
    assert not retire_unfilled_sources(p,j,positions,recorded,now=NOW)
    with sqlite3.connect(p) as db:assert db.execute('select payload from positions').fetchone()[0]==payload
