from datetime import datetime, timezone
import json
import pandas as pd
import pytest
from nn_meta.live.eod_panel import provisional_bar, render_panel, recap
from nn_meta.live.feeds.barstore import COLS


def frames():
    history=pd.DataFrame(1.,index=pd.date_range('2026-09-04 13:30',periods=26,freq='15min'),columns=COLS)
    minutes=pd.DataFrame(1.,index=pd.date_range('2026-09-04 19:45',periods=15,freq='min'),columns=COLS)
    return history,minutes


def test_preview_excludes_future_and_cannot_change_history():
    history,minutes=frames();before=history.copy()
    minutes.loc['2026-09-04 19:55':,'High']=10000
    result,n=provisional_bar(history,minutes,'2026-09-04 19:55')
    assert n==10 and result.iloc[-1].High==1 and result.iloc[-1].Volume==10
    pd.testing.assert_frame_equal(history,before)
    assert result.index[-1]==pd.Timestamp('2026-09-04 19:45')


def test_missing_minute_and_stale_history_are_refused():
    history,minutes=frames()
    with pytest.raises(ValueError,match='missing'):
        provisional_bar(history,minutes.drop(minutes.index[2]),'2026-09-04 19:55')
    with pytest.raises(ValueError,match='history'):
        provisional_bar(history[history.index<'2026-09-04 19:30'],minutes,'2026-09-04 19:55')


def test_combined_panel_labels_and_stale_preview(tmp_path):
    path=tmp_path/'.v4_watchlist.json'
    path.write_text(json.dumps({'a':{'date':'2026-09-04','alerted':True,'symbol':'SPY',
        'direction':0,'strategy':'rsi','entry_ts':'2026-09-04T19:30:00'}}))
    before=path.read_bytes()
    confirmed=recap(tmp_path,'2026-09-04')
    reports={'v4':{'day':'2026-09-04','observed_at':'2026-09-04T19:54:00+00:00',
        'scored_symbols':1,'total_symbols':118,'errors':0,'candidates':[{'symbol':'AAPL',
            'strategy':'rsi','direction':0,'minutes':9,'mode':'ev','decision':.1}]}}
    text=render_panel('2026-09-04',confirmed,reports,datetime(2026,9,4,19,55,tzinfo=timezone.utc))
    assert 'CONFIRMED CLOSED-BAR RECAP' in text and 'EXPERIMENTAL PARTIAL-BAR VIEW' in text
    assert '1/118' in text and '9/15' in text and 'unvalidated' in text
    assert path.read_bytes()==before
    text=render_panel('2026-09-04',confirmed,reports,datetime(2026,9,4,20,0,tzinfo=timezone.utc))
    assert 'v4: preview stale/unavailable' in text


def test_scheduler_uses_session_close_and_holidays():
    from nn_meta.session_calendar import SessionCalendar
    from scripts.eod_panel_tick import phase
    cal=SessionCalendar({'coverage_start':'2026-09-04','coverage_end':'2026-09-08',
        'sessions':[{'date':'2026-09-04','open':'09:30','close':'13:00'}]})
    assert phase(pd.Timestamp('2026-09-04T16:46:00Z'),cal)[1]=='prewarm'
    assert phase(pd.Timestamp('2026-09-04T16:55:00Z'),cal)[1]=='send'
    assert phase(pd.Timestamp('2026-09-04T16:56:00Z'),cal)[1]=='idle'
    assert phase(pd.Timestamp('2026-09-07T19:55:00Z'),cal)[1]=='closed'
