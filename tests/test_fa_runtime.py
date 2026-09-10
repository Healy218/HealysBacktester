from pathlib import Path
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


def test_packed_backup_publishes_manifest_only_after_restore(tmp_path,monkeypatch):
    from scripts import fa_runtime,verify_backup_sample
    import tarfile
    source=tmp_path/'cache';source.mkdir();(source/'one.parquet').write_bytes(b'original')
    calls=[]
    def run(args,**kwargs):
        if args[-1].endswith('manifest.json'):
            assert calls[-1]=='restored'
            manifest=json.loads(Path(args[-2]).read_text());assert manifest['files']==1
            calls.append('manifest')
        else:
            tarpath=next(Path(x) for x in args if x.endswith('.tar'))
            with tarfile.open(tarpath) as tar:assert tar.extractfile('one.parquet').read()==b'original'
            calls.append('uploaded')
    def verify(*args,**kwargs):assert calls==['uploaded'];calls.append('restored')
    monkeypatch.setattr(fa_runtime.subprocess,'run',run)
    monkeypatch.setattr(verify_backup_sample,'verify',verify)
    cfg={'packed_backup':{'source':str(source),'destination':'gs://test/snapshots'},'gsutil':'gsutil','state':str(tmp_path/'state')}
    result=fa_runtime.packed_backup(cfg)
    assert calls==['uploaded','restored','manifest'] and result['shards']==1


def test_packed_backup_restore_failure_never_publishes_manifest(tmp_path,monkeypatch):
    from scripts import fa_runtime,verify_backup_sample
    source=tmp_path/'cache';source.mkdir();(source/'one.parquet').write_bytes(b'original')
    calls=[]
    monkeypatch.setattr(fa_runtime.subprocess,'run',lambda args,**kwargs:calls.append(args))
    def fail(*args,**kwargs):raise ValueError('restore differs')
    monkeypatch.setattr(verify_backup_sample,'verify',fail)
    cfg={'packed_backup':{'source':str(source),'destination':'gs://test/snapshots'},'gsutil':'gsutil','state':str(tmp_path/'state')}
    with pytest.raises(ValueError,match='restore differs'):fa_runtime.packed_backup(cfg)
    assert len(calls)==1 and not (tmp_path/'state/packed-backup.json').exists()
