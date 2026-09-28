from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace as NS
import hashlib
import json
import sqlite3

import pytest

from integrations.alpaca_paper.v6_bridge import Journal, events_from_fresh_state, process_events
from integrations.alpaca_paper.v6_runtime import install_leg_capture, risk_events

NOW = datetime(2026,9,28,14,0,tzinfo=timezone.utc)
CONTRACT = 'AAPL261002C00200000'
FP = hashlib.sha256(b'paper').hexdigest()
CANCEL_SECONDS = 60


@pytest.fixture(autouse=True, params=['v1', 'v2'])
def bridge_version(request, monkeypatch):
    if request.param == 'v2':
        from integrations.alpaca_paper.v6_bridge_v2 import process_events as v2
        monkeypatch.setattr(__import__(__name__, fromlist=['']), 'process_events', v2)
        monkeypatch.setattr(__import__(__name__, fromlist=['']), 'CANCEL_SECONDS', 120)



def entry(key='one', contract=CONTRACT, roll=0):
    return dict(event_id=f'{key}|entry|{roll}',kind='entry',position_key=key,
                contract=contract,at=NOW.isoformat(),size_fraction=.1,roll=roll)


def close(e):
    return dict(event_id=e['position_key']+'|leg-close|'+str(e['roll']+1),kind='close',
                position_key=e['position_key'],contract=e['contract'],at=NOW.isoformat(),
                trigger_at=NOW.isoformat(),reason='strategy exit')


class Broker:
    def __init__(self):
        self.account=NS(id='paper',status='ACTIVE',trading_blocked=False,account_blocked=False,
                        options_trading_level=3,options_buying_power='100000',cash='100000')
        self.orders={};self.positions={};self.posts=0;self.cancels=[]
    def get_account(self): return self.account
    def get_all_positions(self): return list(self.positions.values())
    def get_orders(self,filter): return [o for o in self.orders.values() if o.status in ('new','partially_filled')]
    def get_option_contract(self,symbol): return NS(tradable=True,status='active',size='100')
    def get_order_by_client_id(self,key): return self.orders[key]
    def submit_order(self,order_data):
        self.posts+=1
        o=NS(id=str(self.posts),client_order_id=order_data.client_order_id,symbol=order_data.symbol,
             status='new',qty=str(order_data.qty),filled_qty='0',filled_avg_price=None,
             side=order_data.side.value)
        self.orders[o.client_order_id]=o
        return o
    def fill(self,qty=None):
        o=list(self.orders.values())[-1]
        qty=Decimal(str(qty if qty is not None else o.qty))
        before=Decimal(o.filled_qty)
        o.filled_qty=str(qty);o.filled_avg_price='2.10'
        o.status='filled' if qty==Decimal(o.qty) else 'partially_filled'
        held=Decimal(self.positions[o.symbol].qty) if o.symbol in self.positions else 0
        held+=(qty-before)*(1 if o.side=='buy' else -1)
        if held: self.positions[o.symbol]=NS(symbol=o.symbol,qty=str(held),avg_entry_price='2.10')
        else: self.positions.pop(o.symbol,None)
    def cancel_order_by_id(self,order_id):
        self.cancels.append(order_id)
        next(o for o in self.orders.values() if o.id==order_id).status='canceled'


class Data:
    def __init__(self): self.at=NOW;self.bid=2.;self.ask=2.2;self.bid_size=20
    def get_option_snapshot(self,request):
        quote=NS(bid_price=self.bid,ask_price=self.ask,bid_size=self.bid_size,
                 ask_size=10,timestamp=self.at)
        return {request.symbol_or_symbols:NS(latest_quote=quote,latest_trade=None,mark_price=None)}


def poll(events,journal,broker,data,now=NOW):
    data.at=now
    return process_events(events,journal=journal,trading=broker,data=data,
                          expected_fingerprint=FP,submit=True,now=now)


def test_partial_fill_cancel_then_close_and_restart_idempotency(tmp_path):
    j=Journal(tmp_path/'orders.sqlite3');b=Broker();d=Data();e=entry()
    poll([e],j,b,d);b.fill(3)
    assert poll([e],j,b,d)[0]['status']=='awaiting_broker'
    assert b.posts==1
    poll([e],j,b,d,NOW+timedelta(seconds=CANCEL_SECONDS+1))
    assert len(b.cancels)==1
    j=Journal(j.path)
    poll([close(e),e],j,b,d,NOW+timedelta(seconds=CANCEL_SECONDS+2))
    assert b.posts==2 and list(b.orders.values())[-1].qty=='3.0'
    b.fill()
    poll([close(e),e],j,b,d,NOW+timedelta(seconds=CANCEL_SECONDS+3))
    assert b.posts==2 and not b.positions


def test_roll_waits_for_confirmed_close_and_closes_in_liquidity_slices(tmp_path):
    j=Journal(tmp_path/'orders.sqlite3');b=Broker();d=Data();e=entry()
    poll([e],j,b,d);b.fill()
    replacement=entry(contract='AAPL261009C00200000',roll=1)
    events=[close(e),e,replacement]
    d.bid_size=4
    poll(events,j,b,d);b.fill()
    assert Decimal(b.positions[CONTRACT].qty)==6
    poll(events,j,b,d);b.fill()
    assert Decimal(b.positions[CONTRACT].qty)==2
    poll(events,j,b,d);b.fill()
    poll(events,j,b,d)
    assert list(b.orders.values())[-1].symbol==replacement['contract']
    assert len({o.client_order_id for o in b.orders.values()})==b.posts==5


def test_old_close_cannot_close_new_position_in_same_contract(tmp_path):
    j=Journal(tmp_path/'orders.sqlite3');b=Broker();d=Data();e=entry()
    poll([e],j,b,d);b.fill();poll([close(e),e],j,b,d);b.fill()
    newer=entry('two')
    events=[close(e),e,newer]
    poll(events,j,b,d);b.fill()
    poll(events,j,b,d)
    assert b.posts==3 and CONTRACT in b.positions


def test_actual_signal_deadline_not_scanner_completion(tmp_path):
    j=Journal(tmp_path/'orders.sqlite3');b=Broker();d=Data();e=entry()
    e['signal_close']=(NOW-timedelta(minutes=6)).isoformat()
    result=poll([e],j,b,d)
    assert result[0]['status']=='blocked' and b.posts==0


def test_durable_multi_roll_entries_survive_database_reopen(tmp_path):
    path=tmp_path/'source.sqlite3'
    with sqlite3.connect(path) as db:
        db.executescript('CREATE TABLE positions (key TEXT,symbol TEXT,state TEXT,payload TEXT);'
                         'CREATE TABLE events (key TEXT,recorded_at TEXT,kind TEXT,payload TEXT);')
    install_leg_capture(path)
    p=dict(key='one',contract=CONTRACT,opened_at=NOW.isoformat(),entry_ts='2026-09-28T13:45:00',
           entry_quote={'received_at':NOW.isoformat()},size_fraction=.1,rolls=0,legs=[])
    with sqlite3.connect(path) as db:
        db.execute('INSERT INTO positions VALUES (?,?,?,?)',('one','AAPL','open',json.dumps(p)))
        for roll in (1,2,3):
            p.update(rolls=roll,contract=f'AAPL2610{roll+9:02}C00200000')
            db.execute('UPDATE positions SET payload=?',(json.dumps(p),))
    events=events_from_fresh_state(path,activated_at=NOW-timedelta(seconds=1))
    assert [e['roll'] for e in events]==[0,1,2,3]
    assert events[0]['signal_close']=='2026-09-28 14:00:00+00:00'
    with pytest.raises(RuntimeError),sqlite3.connect(path) as db:
        p.update(rolls=4);db.execute('UPDATE positions SET payload=?',(json.dumps(p),))
        raise RuntimeError('crash rolls back source AND leg receipt')
    assert len(events_from_fresh_state(path,activated_at=NOW-timedelta(seconds=1)))==4


def test_broker_stop_persists_after_price_rebound(tmp_path):
    import pandas as pd
    class Calendar:
        sessions=['2026-10-02']
        def bounds(self,day): return (pd.Timestamp('2026-10-02 13:30'),pd.Timestamp('2026-10-02 20:00'))
    j=Journal(tmp_path/'orders.sqlite3');d=Data();d.bid=1.7;d.ask=1.8
    position=NS(symbol=CONTRACT,qty='3',avg_entry_price='2.10')
    events=risk_events(j,{CONTRACT:position},d,[entry()],Calendar(),now=NOW)
    assert events[0]['reason']=='broker premium stop'
    d.bid=2.;d.ask=2.2
    assert risk_events(j,{CONTRACT:position},d,[entry()],Calendar(),now=NOW)==events


def test_foreign_position_blocks_submission(tmp_path):
    j=Journal(tmp_path/'orders.sqlite3');b=Broker();d=Data()
    b.positions['AAPL']=NS(symbol='AAPL',qty='100')
    with pytest.raises(ValueError,match='outside'):
        poll([entry()],j,b,d)
    assert b.posts==0
