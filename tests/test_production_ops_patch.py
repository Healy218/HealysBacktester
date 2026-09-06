from datetime import datetime, timezone
from pathlib import Path
import json
import pandas as pd
import pytest
from nn_meta.live.scanner import require_recent_bars, is_rth
from nn_meta.live.feeds.barstore import aggregate_15m, COLS
from nn_meta.live.state import Outbox, preview_state


def test_final_close_and_stale_rejection():
    assert is_rth(datetime(2026,9,4,20,3,tzinfo=timezone.utc))
    assert not is_rth(datetime(2026,9,4,20,4,tzinfo=timezone.utc))
    bars=pd.DataFrame({'Close':[1.]},index=pd.to_datetime(['2026-09-04 19:45']))
    with pytest.raises(ValueError,match='stale'):
        require_recent_bars(bars,pd.Timestamp('2026-09-08 13:46'))


def test_incomplete_bucket_not_exposed():
    index=pd.date_range('2026-09-04 19:45',periods=15,freq='min')
    data=pd.DataFrame(1.,index=index,columns=COLS)
    assert aggregate_15m(data,now=pd.Timestamp('2026-09-04 19:55')).empty
    with pytest.raises(ValueError,match='Incomplete'):
        aggregate_15m(data.drop(index[4]),now=pd.Timestamp('2026-09-04 20:01'))
    assert len(aggregate_15m(data,now=pd.Timestamp('2026-09-04 20:01')))==1


def test_calendar_handles_holiday_and_early_close(monkeypatch,tmp_path):
    path=tmp_path/'calendar.json'
    path.write_text(json.dumps({'coverage_start':'2026-09-04','coverage_end':'2026-09-08',
        'sessions':[{'date':'2026-09-04','open':'09:30','close':'13:00'}]}))
    monkeypatch.setenv('NN_META_SESSION_CALENDAR',str(path))
    assert is_rth(datetime(2026,9,4,17,3,tzinfo=timezone.utc))
    assert not is_rth(datetime(2026,9,4,17,4,tzinfo=timezone.utc))
    assert not is_rth(datetime(2026,9,7,14,0,tzinfo=timezone.utc))


def test_preview_acknowledgement_does_not_touch_real_outbox(tmp_path):
    path=tmp_path/'.v4_outbox.json';outbox=Outbox(path)
    key=outbox.enqueue({'message':'test','title':'test'},key='one')
    before=path.read_bytes()
    with preview_state(tmp_path) as preview:
        Outbox(preview/path.name).acknowledge(key)
    assert path.read_bytes()==before


def test_legacy_retries_failed_delivery(tmp_path,monkeypatch):
    from nn_meta.live import scanner as sc
    bars=pd.DataFrame(1.,index=pd.date_range('2026-09-04 13:30',periods=40,freq='15min'),columns=COLS)
    stamp=bars.index[-1]
    sig=sc.Signal(symbol='SPY',strategy='rsi',direction=0,right='C',bar_ts=stamp,dte=5,spot=1.,param_label='test')
    monkeypatch.setattr(sc,'detect_fresh_signal',lambda *a:sig)
    scan=sc.Scanner(lambda s:bars,state_path=tmp_path/'state.json',spec={'symbols':{'SPY':{}}})
    assert len(scan.scan_once(now=(stamp+pd.Timedelta(minutes=16)).tz_localize('UTC').to_pydatetime()))==1
    class Fail:
        def send(self,*a,**k):return False
    class Success:
        def send(self,*a,**k):return True
    assert scan.deliver_pending(Fail())==0
    assert scan.deliver_pending(Success())==1
    assert scan.deliver_pending(Success())==0


def test_bulk_download_bounds_inflight_and_keeps_resume(monkeypatch,tmp_path):
    from nn_meta import download_universe as d
    monkeypatch.setattr(d.config,'DONE_MANIFEST',tmp_path/'done.txt')
    monkeypatch.setattr(d.config,'BARS_DAILY_DIR',tmp_path)
    monkeypatch.setattr(d.config,'DOWNLOAD_WORKERS',2)
    monkeypatch.setattr(d,'_aggs_daily',lambda *a:[])
    wait=d.wait;observed=[]
    def bounded(futures,**kwargs):
        observed.append(len(futures));assert len(futures)<=4
        return wait(futures,**kwargs)
    monkeypatch.setattr(d,'wait',bounded)
    uni=pd.DataFrame({'ticker':[f'X{i}' for i in range(25)],'life_start':'2026-09-01','life_end':'2026-09-04'})
    d.bulk_download(uni,'unused')
    assert len((tmp_path/'done.txt').read_text().splitlines())==25
    assert observed
    before=(tmp_path/'done.txt').read_bytes();d.bulk_download(uni,'unused')
    assert (tmp_path/'done.txt').read_bytes()==before
