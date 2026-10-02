from datetime import timedelta
import sqlite3
import pandas as pd
import pytest
from integrations.alpaca_paper.v6_bridge_v5 import Journal, process_events
from integrations.alpaca_paper.v6_source_reconcile_v4 import retire_unfilled_sources
from scripts.v6_portfolio_ten_minute_v1 import ForwardPortfolio, key_of
from tests.test_v6_alpaca_runtime import Broker, Data, NOW, FP, entry
from tests.test_v6_source_reconcile_v3 import setup as source_setup, NOW as SOURCE_NOW

@pytest.mark.parametrize('age,allowed', [(299,True),(301,True),(599,True),(600,True),(601,False),(-1,False)])
def test_broker_signal_close_window(tmp_path,age,allowed):
    j,b,d=Journal(tmp_path/'orders.sqlite3'),Broker(),Data()
    e=entry();e['signal_close']=(NOW-timedelta(seconds=age)).isoformat()
    result=process_events([e],journal=j,trading=b,data=d,expected_fingerprint=FP,submit=True,now=NOW)
    assert (b.posts==1)==allowed,result
    if not allowed: assert 'ten-minute' in result[0]['reason']


def test_empty_chain_after_crash_cannot_bypass_ten_minutes(tmp_path):
    j,b,d=Journal(tmp_path/'orders.sqlite3'),Broker(),Data()
    e=entry();e['signal_close']=(NOW-timedelta(seconds=590)).isoformat()
    plan=process_events([e],journal=j,trading=b,data=d,expected_fingerprint=FP,now=NOW)[0]['plan']
    j.save_chain(dict(event=e,plan=plan,state='active'))
    process_events([e],journal=j,trading=b,data=d,expected_fingerprint=FP,submit=True,now=NOW+timedelta(seconds=11))
    assert b.posts==0 and j.chains()[e['event_id']]['state']=='done'

@pytest.mark.parametrize('seconds,retired', [(-299,False),(0,False),(1,True)])
def test_source_retirement_respects_same_window(tmp_path,seconds,retired):
    p,j,e,raw=source_setup(tmp_path)
    result=retire_unfilled_sources(p,j,{}, {},now=SOURCE_NOW+timedelta(seconds=seconds))
    assert bool(result)==retired

@pytest.mark.parametrize('age,allowed',[(301,True),(599,True),(600,True),(601,False)])
def test_scanner_allocation_window_and_signal_timestamp(tmp_path,age,allowed):
    book=ForwardPortfolio(tmp_path/'book.sqlite3',scope={'test':1})
    from integrations.alpaca_paper.v6_runtime import install_leg_capture
    install_leg_capture(book.path)
    bar=pd.Timestamp('2026-10-02T14:00');close=bar.tz_localize('UTC')+pd.Timedelta(minutes=15)
    now=close+pd.Timedelta(seconds=age)
    rows=pd.DataFrame([dict(symbol='SPY',strategy='x',entry_ts=bar,dte=30,decision=.2,score=.7,
        decision_contract='SPY261106C00700000',option_tick_status='covered')])
    def quote(contract,after):return dict(contract=contract,bid=2.,ask=2.1,bid_size=10,ask_size=10,
        sip_timestamp_ns=(now-pd.Timedelta(seconds=1)).value,received_at=now.isoformat())
    args=dict(bar=bar,now=now,quote_loader=quote,contexts={key_of(rows.iloc[0]):{}},clock=lambda:now)
    if allowed:
        assert book.allocate(rows,**args)['opened']==1
        from integrations.alpaca_paper.v6_bridge import events_from_fresh_state
        source=events_from_fresh_state(book.path,activated_at=close-pd.Timedelta(days=1))[0]
        assert pd.Timestamp(source['signal_close'])==close
    else:
        with pytest.raises(ValueError,match='ten-minute'):book.allocate(rows,**args)


def test_quote_arriving_after_deadline_is_unfilled(tmp_path):
    book=ForwardPortfolio(tmp_path/'book.sqlite3',scope={'test':1})
    from integrations.alpaca_paper.v6_runtime import install_leg_capture
    install_leg_capture(book.path)
    bar=pd.Timestamp('2026-10-02T14:00');close=bar.tz_localize('UTC')+pd.Timedelta(minutes=15)
    before=close+pd.Timedelta(seconds=599);after=close+pd.Timedelta(seconds=601)
    rows=pd.DataFrame([dict(symbol='SPY',strategy='x',entry_ts=bar,dte=30,decision=.2,score=.7,
        decision_contract='SPY261106C00700000',option_tick_status='covered')])
    times=iter([before,after,after,after])
    def quote(contract,**kw):return dict(contract=contract,bid=2.,ask=2.1,bid_size=10,ask_size=10,
        sip_timestamp_ns=after.value,received_at=after.isoformat())
    result=book.allocate(rows,bar=bar,now=before,quote_loader=quote,contexts={},clock=lambda:next(times))
    assert result['unfilled']==1 and not book.open_positions()
