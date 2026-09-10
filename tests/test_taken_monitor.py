from datetime import datetime, timezone
import json

import numpy as np
import pandas as pd
import pytest

from nn_meta.live import taken_monitor as mon
from nn_meta.live.taken_trades import handle
from tests.test_taken_trades import queued, callback, message, rows

NOW = datetime(2026, 9, 9, 17, 0, tzinfo=timezone.utc)


def bars():
    idx=pd.date_range('2026-09-09 13:30',periods=13,freq='15min')
    return pd.DataFrame(dict(Open=100.,High=101.,Low=99.,Close=100.,Volume=1000.),index=idx)


def context():
    from nn_meta import config
    cfg=dict(config.SIM_CONFIG, TREND_FILTER_WINDOW=0)
    return dict(strategy='ma',params={},direction=0,spot=100.,entry_ts='2026-09-09 13:45:00',sim_start='2026-09-09 13:30:00',sim_config=cfg)


def signal_stub(monkeypatch, exit_at=None, opposite_at=None):
    def signals(strategy,b,p):
        e,x,se,sx=[pd.DataFrame(False,index=b.index,columns=[0]) for _ in range(4)]
        e.iloc[1,0]=True
        if exit_at is not None:x.iloc[exit_at,0]=True
        if opposite_at is not None:se.iloc[opposite_at,0]=True
        return e,x,se,sx
    monkeypatch.setattr('nn_meta.proposals.single_signals',signals)


def test_open_mark_is_not_a_sell_signal(monkeypatch):
    signal_stub(monkeypatch)
    event,last=mon.evaluate(context(),bars(),NOW)
    assert event is None and last=='2026-09-09 16:30:00'


def test_signal_exit_and_opposite_entry_are_detected(monkeypatch):
    signal_stub(monkeypatch,exit_at=8)
    event,_=mon.evaluate(context(),bars(),NOW)
    assert event['bar']=='2026-09-09 15:30:00'
    signal_stub(monkeypatch,opposite_at=9)
    event,_=mon.evaluate(context(),bars(),NOW)
    assert event['bar']=='2026-09-09 15:45:00'


def test_underlying_stop_and_short_stop(monkeypatch):
    signal_stub(monkeypatch)
    b=bars();b.iloc[8,b.columns.get_loc('Low')]=94.
    event,_=mon.evaluate(context(),b,NOW)
    assert event['reason']=='underlying stop $95.00'
    def short_signals(strategy,b,p):
        e,x,se,sx=[pd.DataFrame(False,index=b.index,columns=[0]) for _ in range(4)]
        se.iloc[1,0]=True
        return e,x,se,sx
    monkeypatch.setattr('nn_meta.proposals.single_signals',short_signals)
    b=bars();b.iloc[8,b.columns.get_loc('High')]=106.
    event,_=mon.evaluate(dict(context(),direction=1),b,NOW)
    assert event['reason']=='underlying stop $105.00'


def test_forming_bar_cannot_trigger_exit(monkeypatch):
    signal_stub(monkeypatch,exit_at=11)
    # 16:30 bar has not closed at 16:35 and its crash is excluded.
    b=bars();b.iloc[-1,b.columns.get_loc('Low')]=1.
    signal_stub(monkeypatch)
    event,_=mon.evaluate(context(),b,datetime(2026,9,9,16,35,tzinfo=timezone.utc))
    assert event is None


def test_missing_or_revised_entry_is_not_guessed(monkeypatch):
    signal_stub(monkeypatch)
    with pytest.raises(ValueError,match='warmup'):
        mon.evaluate(context(),bars().iloc[2:],NOW)
    b=bars();b.iloc[1,b.columns.get_loc('Close')]=101.
    with pytest.raises(ValueError,match='changed'):
        mon.evaluate(context(),b,NOW)


def test_exit_persists_and_retries_delivery_without_closing_trade(tmp_path):
    from tests.test_alert_batches import API
    q,ident=queued(tmp_path);handle(q,callback(ident),'123')
    event=dict(reason='test strategy exit',bar='2026-09-09 16:30:00',stock_close=12.)
    evaluator=lambda ctx,b,now:(event,str(b.index[-1]))
    assert mon.scan(q,'v31',lambda c,n:bars(),NOW,evaluator,lambda occ:None)==1
    assert rows(q)[0]['status']=='exit_due'
    class Fails(API):
        def call(self,*a,**k):raise RuntimeError('unavailable')
    with pytest.raises(RuntimeError):mon.send_pending(q,Fails())
    assert rows(q)[0]['notice_sent']==0
    api=API();mon.send_pending(q,api);mon.send_pending(q,api)
    assert len(api.calls)==1 and 'SELL WATCH' in api.calls[0][1]['text']
    assert rows(q)[0]['status']=='exit_due'
    handle(q,message('/sold '+ident,uid=2),'123')
    assert rows(q)[0]['status']=='closed'


def test_closed_positions_are_excluded_and_errors_visible(tmp_path):
    q,ident=queued(tmp_path);handle(q,callback(ident),'123')
    def fail(*a):raise ValueError('missing bars')
    assert mon.scan(q,'v31',fail,NOW)==0
    assert rows(q)[0]['monitor_error']=='ValueError: exit check failed'
    assert 'CHECK FAILED' in handle(q,message('/selllist',uid=2),'123')
    handle(q,message('/sold '+ident,uid=3),'123')
    assert mon.scan(q,'v31',fail,NOW)==0


def test_monitor_cron_preserves_other_jobs():
    from scripts.configure_taken_monitor import updated_cron
    old='* * * * * existing-job\n'
    new=updated_cron(old,'/repo')
    assert old in new and '4,19,34,49' in new
    assert updated_cron(new,'/repo')==new


def test_monitor_failure_notice_is_once_until_recovery(tmp_path):
    from tests.test_alert_batches import API
    q,ident=queued(tmp_path);handle(q,callback(ident),'123')
    def fail(*a):raise ValueError('private provider details')
    mon.scan(q,'v31',fail,NOW)
    api=API();mon.send_pending(q,api);mon.send_pending(q,api)
    assert len(api.calls)==1 and 'needs attention' in api.calls[0][1]['text']
    assert 'private provider details' not in api.calls[0][1]['text']


def test_expiring_open_contract_prompts_review(tmp_path):
    q,ident=queued(tmp_path);handle(q,callback(ident),'123')
    ctx=json.loads(rows(q)[0]['context']);ctx['contract']='MARA260909C00011500'
    with q.connect() as db:db.execute('UPDATE taken_trades SET context=?',(json.dumps(ctx),))
    b=bars();b.index=b.index+pd.Timedelta(hours=3)
    late=datetime(2026,9,9,19,49,tzinfo=timezone.utc)
    evaluator=lambda ctx,b,now:(None,str(b.index[-1]))
    mon.scan(q,'v31',lambda c,n:b,late,evaluator,lambda occ:None)
    assert rows(q)[0]['status']=='exit_due'
    assert 'close or roll' in rows(q)[0]['exit_notice']
