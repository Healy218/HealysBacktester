import json
import numpy as np
import pandas as pd
import pytest
from nn_meta.session_calendar import SessionCalendar
from nn_meta.v7.stock_daily import aggregate_daily, build_shard, join_eligible
from tests.test_v7_coverage import stock_receipt


def fixture():
    calendar=dict(coverage_start='2022-03-14',coverage_end='2022-03-18',sessions=[
        dict(date='2022-03-14',open='09:30',close='16:00'),
        dict(date='2022-03-15',open='09:30',close='16:00'),
        dict(date='2022-03-16',open='09:30',close='13:00'),
        dict(date='2022-03-17',open='09:30',close='16:00')])
    stamps=pd.to_datetime(['2022-03-14T13:30Z','2022-03-15T13:29Z','2022-03-15T13:30Z',
        '2022-03-15T19:57Z','2022-03-15T20:00Z','2022-03-16T16:59Z','2022-03-16T17:00Z'])
    frame=pd.DataFrame(dict(timestamp=stamps,Open=100.,High=102.,Low=98.,Close=101.,Volume=10.))
    return frame,calendar


def test_regular_close_early_close_missing_days_and_exact_observation_clocks():
    raw,doc=fixture();daily=aggregate_daily(raw,SessionCalendar(doc),symbol='ABC',year=2022)
    assert daily.source_date.tolist()==['2022-03-15','2022-03-16','2022-03-17']
    assert daily.observed_minutes.tolist()==[2,1,0]
    assert daily.expected_minutes.tolist()==[390,210,390]
    assert daily.raw_volume.iloc[0]==20. and pd.isna(daily.raw_volume.iloc[-1])
    assert daily.last_observed_ns.iloc[0]==pd.Timestamp('2022-03-15T19:57Z').value
    assert daily.available_ns.iloc[0]==pd.Timestamp('2022-03-15T20:00Z').value
    assert str(daily.last_observed_ns.dtype)=='Int64'
    assert pd.isna(daily.raw_close.iloc[-1]) and pd.isna(daily.last_observed_ns.iloc[-1])
    prefix=aggregate_daily(raw.iloc[:5],SessionCalendar(doc),symbol='ABC',year=2022)
    pd.testing.assert_series_equal(prefix.iloc[0],daily.iloc[0])


def test_eligible_identity_is_exact_day_and_alias_count_must_reconcile():
    raw,doc=fixture();daily=aggregate_daily(raw,SessionCalendar(doc),symbol='NEW',year=2022)
    eligible=pd.DataFrame(dict(date=['2022-03-15','2022-03-17'],stock_ticker='NEW',
        membership_ticker='OLD',security_id='identity',observed_minutes=[2,0]))
    joined=join_eligible(eligible,daily)
    assert len(joined)==2 and joined.security_id.eq('identity').all()
    assert joined.membership_ticker.eq('OLD').all()
    bad=eligible.copy();bad.loc[0,'observed_minutes']=3
    with pytest.raises(ValueError,match='coverage inventory'):join_eligible(bad,daily)
    with pytest.raises(ValueError,match='Duplicate'):join_eligible(pd.concat([eligible,eligible]),daily)
    with pytest.raises(ValueError,match='coverage inventory'):join_eligible(eligible,daily.iloc[1:])


def test_shard_receipt_resume_and_input_mutation_rejected(tmp_path):
    raw,calendar=fixture();path,doc=stock_receipt(tmp_path,raw.timestamp)
    doc['task'].update(kind='stock',symbol='SPY',adjustment='raw')
    path.write_text(json.dumps(doc));(tmp_path/'calendar.json').write_text(json.dumps(calendar))
    out=tmp_path/'daily'
    report=build_shard(tmp_path,'SPY',2022,out,reserve_gib=0)
    assert report['regular_minutes']==3 and report['zero_sessions']==1
    assert build_shard(tmp_path,'SPY',2022,out,reserve_gib=0)==report
    (path.parent/'bars.parquet').write_bytes(b'changed')
    with pytest.raises(RuntimeError,match='hash mismatch'):
        build_shard(tmp_path,'SPY',2022,out,reserve_gib=0)


def test_invalid_raw_observations_rejected_and_empty_capture_not_filled():
    raw,doc=fixture();calendar=SessionCalendar(doc)
    for change in ('duplicate','infinite','subminute'):
        bad=raw.copy()
        if change=='duplicate':bad.loc[3,'timestamp']=bad.loc[2,'timestamp']
        if change=='infinite':bad.loc[2,'Close']=np.inf
        if change=='subminute':bad.loc[2,'timestamp']+=pd.Timedelta(nanoseconds=1)
        with pytest.raises(ValueError):aggregate_daily(bad,calendar,symbol='A',year=2022)
    empty=aggregate_daily(raw.iloc[:0],calendar,symbol='A',year=2022)
    assert empty.observed_minutes.eq(0).all() and empty.raw_close.isna().all()
