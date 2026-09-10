import json
from pathlib import Path

import pandas as pd
import pytest

from fa.monthly import freeze, verify, track, plan
from tests.test_fa_ranker import _archive


def inputs(tmp_path):
    archive=_archive(tmp_path)
    liquid=tmp_path/'liquid.json';liquid.write_text('["AAPL", "TSLA"]')
    baseline=tmp_path/'baseline.json';baseline.write_text('["SPY"]')
    return tmp_path/'cohorts',archive,liquid,baseline


def test_freeze_preserves_snapshot_and_exact_cutoff_on_retry(tmp_path):
    root,archive,liquid,baseline=inputs(tmp_path)
    a=freeze(root,archive,liquid,baseline,now='2026-09-01T00:15Z')
    assert a['cutoff']=='2026-08-31T23:59:59.999999999+00:00'
    assert a['tracking_start']=='2026-09-02T00:00:00+00:00'
    assert a['ranked']==1
    liquid.write_text('["ZZZ"]')
    b=freeze(root,archive,liquid,baseline,now='2026-09-05T00:00Z')
    assert a==b
    assert json.loads((root/'2026-08/inputs/liquid.json').read_text())==['AAPL','TSLA']
    data=json.loads((root/'2026-08/top10_2026-08.json').read_text())
    assert data['available_at']=='2026-09-01T00:15:00+00:00'


def test_late_new_freeze_and_tampered_retry_refused(tmp_path):
    args=inputs(tmp_path)
    with pytest.raises(ValueError,match='first seven'):freeze(*args,now='2026-09-10')
    freeze(*args,now='2026-09-01')
    (args[0]/'2026-08/inputs/baseline.json').write_text('["QQQ"]')
    with pytest.raises(ValueError,match='hash mismatch'):freeze(*args,now='2026-09-03')


def test_missing_inputs_leave_failure_evidence_but_no_cohort(tmp_path):
    root,archive,liquid,baseline=inputs(tmp_path)
    baseline.write_text('[]')
    with pytest.raises(ValueError,match='nonempty'):freeze(root,archive,liquid,baseline,now='2026-09-01')
    assert not (root/'2026-08').exists()
    assert list(root.glob('.pending-*/failure.json'))
    baseline.write_text('["SPY"]')
    assert freeze(root,archive,liquid,baseline,now='2026-09-01')['ranked']==1


def test_forward_tracking_uses_publication_and_frozen_baseline(tmp_path):
    root,archive,liquid,baseline=inputs(tmp_path)
    freeze(root,archive,liquid,baseline,now='2026-09-01')
    prices=tmp_path/'prices';prices.mkdir()
    dates=pd.date_range('2026-09-01',periods=4,freq='D')
    for ticker,values in [('AAPL',[1,100,110,120]),('SPY',[1,100,101,102])]:
        pd.DataFrame({'Close':values},index=dates).to_parquet(prices/(ticker+'.parquet'))
    baseline.write_text('["QQQ"]')
    report=track(root,prices,as_of='2026-09-04')[0]
    assert report['baseline']==['SPY']
    assert report['rows'][0]['excess_return']==pytest.approx(.18)
    assert not report['graduation_applied']
    assert track(root,prices,as_of='2026-09-04')==[report]


def test_tracking_rejects_missing_baseline_and_mismatched_dates(tmp_path):
    args=inputs(tmp_path);freeze(*args,now='2026-09-01')
    prices=tmp_path/'prices';prices.mkdir()
    dates=pd.date_range('2026-09-02',periods=4)
    pd.DataFrame({'Close':[100,101,102,103]},index=dates).to_parquet(prices/'AAPL.parquet')
    with pytest.raises(FileNotFoundError):track(args[0],prices,as_of='2026-09-05')
    pd.DataFrame({'Close':[100,101]},index=dates[:2]).to_parquet(prices/'SPY.parquet')
    with pytest.raises(ValueError,match='dates differ'):track(args[0],prices,as_of='2026-09-05')


def test_parallel_freezes_publish_one_cohort(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    args=inputs(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:freeze(*args,now='2026-09-01'),range(2)))
    assert results[0]==results[1]
    assert len(list(args[0].glob('2026-*')))==1


def test_preview_has_no_io_and_month_rollover():
    assert plan('2027-01-01')['month']=='2026-12'
    assert not plan('2026-09-08')['within_freeze_window']


def test_capture_after_cutoff_cannot_enter_ranking(tmp_path):
    root,archive,liquid,baseline=inputs(tmp_path)
    # Re-date every news capture past cutoff, while publication stays historical.
    path=archive/'news/2026-08.parquet'
    frame=pd.read_parquet(path);frame['ts_utc']=pd.Timestamp('2026-09-01T00:01Z');frame.to_parquet(path)
    result=freeze(root,archive,liquid,baseline,now='2026-09-01T00:15Z')
    assert result['ranked']==0  # Social alone cannot satisfy corroboration.
