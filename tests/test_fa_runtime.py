import json
from datetime import datetime,timezone,timedelta
import pandas as pd
import pytest
from scripts.fa_runtime import daily_prices,health


def config(tmp_path):
    baseline=tmp_path/'baseline.json';baseline.write_text('["SPY"]')
    calendar=tmp_path/'calendar.json';calendar.write_text(json.dumps(dict(coverage_start='2026-01-01',coverage_end='2027-01-01',
                sessions=[dict(date=d) for d in ['2026-09-08','2026-09-09']])))
    return dict(baseline=str(baseline),calendar=str(calendar),cohorts=str(tmp_path/'cohorts'),prices=str(tmp_path/'prices'))


def bars(values=(100,101),dates=('2026-09-08T04:00Z','2026-09-09T04:00Z')):
    return pd.DataFrame({'close':values},index=pd.MultiIndex.from_arrays([['SPY']*len(dates),pd.to_datetime(dates)],names=['symbol','timestamp']))


def test_adjusted_daily_snapshot_normalizes_session_dates(tmp_path):
    cfg=config(tmp_path)
    out=daily_prices(cfg,now='2026-09-10T18:00Z',fetch=lambda names:bars())
    assert out['last']=='2026-09-09' and out['symbols']==1 and out['adjustment']=='all'
    df=pd.read_parquet(tmp_path/'prices/SPY.parquet')
    assert list(df.index)==list(pd.to_datetime(['2026-09-08','2026-09-09']))


def test_incomplete_price_refresh_preserves_previous_files(tmp_path):
    cfg=config(tmp_path);daily_prices(cfg,now='2026-09-10T18:00Z',fetch=lambda names:bars())
    path=tmp_path/'prices/SPY.parquet';original=path.read_bytes()
    with pytest.raises(ValueError,match='Incomplete'):
        daily_prices(cfg,now='2026-09-10T18:00Z',fetch=lambda names:bars((99,),('2026-09-09T04:00Z',)))
    assert path.read_bytes()==original


def test_not_yet_due_monthly_is_explicit_but_failure_is_not_hidden(tmp_path,capsys):
    from scripts.job_receipts import record
    cfg=dict(state=str(tmp_path),archive=str(tmp_path/'archive'),job_hours={'fa-monthly':768},capture_hours={},
             not_before={'fa-monthly':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()})
    assert health(cfg)==0 and 'awaiting-first-scheduled-run' in capsys.readouterr().out
    record(tmp_path,'fa-monthly','failed',returncode=1)
    assert health(cfg)==1
