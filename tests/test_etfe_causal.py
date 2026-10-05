from dataclasses import replace
from datetime import date
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nn_meta.etfe.causal_inputs import session_bars,technical_diagnostics,minute_context
from nn_meta.etfe.eligibility import DatedTerms,select_contract,feature_window,union_intervals
from nn_meta.etfe.signals import signal_batches


def fixture(days=3):
    calendar=[dict(date=str(date(2024,1,2+i)),open='09:30',close='16:00') for i in range(days)]
    index=pd.DatetimeIndex(np.concatenate([pd.date_range(d['date']+' 14:30',periods=390,freq='min',tz='UTC').to_numpy() for d in calendar]))
    x=np.arange(len(index));close=100+.003*x+np.sin(x/8)+.3*np.cos(x/3)
    raw=pd.DataFrame(dict(Open=close-.05,High=close+.2,Low=close-.2,Close=close,
                         Volume=100+(x%19)*20,input_valid=True),index=index)
    return raw,calendar


@pytest.mark.parametrize('minutes',[1,5,15])
def test_session_grid_prefix_and_technical_no_future(minutes):
    raw,calendar=fixture();full=session_bars(raw,calendar,minutes)
    at=raw.index[500]+pd.Timedelta(minutes=1)
    prefix=session_bars(raw.loc[raw.index<at],calendar,minutes,as_of=at)
    pd.testing.assert_frame_equal(prefix,full.loc[prefix.index])
    pd.testing.assert_frame_equal(technical_diagnostics(prefix),technical_diagnostics(full).loc[prefix.index])
    perturbed=raw.copy();perturbed.loc[perturbed.index>=at,['Open','High','Low','Close']]*=3
    pd.testing.assert_frame_equal(prefix,session_bars(perturbed,calendar,minutes,as_of=at))
    assert prefix.available_at.max()<=at


def test_missing_minutes_never_fill_or_compress_and_recursive_taint():
    raw,calendar=fixture();missing=raw.index[55];raw=raw.drop(missing)
    chart=session_bars(raw,calendar,5)
    assert len(chart)==3*78 and (~chart.valid).sum()==1
    bad=chart.loc[~chart.valid];assert bad[['Open','High','Low','Close','Volume']].isna().all().all()
    features=technical_diagnostics(chart)
    assert features.loc[features.index>=bad.index[0],['rsi14','macd_hist']].isna().all().all()
    assert features.ret_8.iloc[12:20].isna().all()
    assert np.isfinite(features.ret_8.iloc[21])


def test_early_close_and_incomplete_final_bucket():
    raw,calendar=fixture(1);calendar[0]['close']='13:00'
    chart=session_bars(raw,calendar,15)
    assert len(chart)==14 and chart.bar_end.iloc[-1]==pd.Timestamp('2024-01-02T18:00Z')
    features=technical_diagnostics(chart)
    assert features.tod.iloc[-1]==195/210
    assert features.is_last_hour.iloc[-1]==1


def test_minute_orb_and_vwap_do_not_see_future():
    raw,calendar=fixture(1);chart=session_bars(raw,calendar,5)
    ctx=minute_context(chart,raw)
    assert ctx['opening'].or_done.iloc[:2].eq(False).all()
    assert ctx['opening'].or_done.iloc[2]
    assert ctx['opening'].or_high.iloc[2]==raw.High.iloc[:15].max()
    expected=((raw.High+raw.Low+raw.Close).iloc[:5]/3*raw.Volume.iloc[:5]).sum()/raw.Volume.iloc[:5].sum()
    assert ctx['vwap'].vwap.iloc[0]==pytest.approx(expected)
    missing=raw.drop(raw.index[3]);ctx=minute_context(session_bars(missing,calendar,5),missing)
    assert not ctx['opening'].or_done.any() and ctx['vwap'].vwap.isna().all()


def candidates():
    return [dict(symbol='SPY240119C00100000',expiration_date='2024-01-19',right='call',strike=100.,
                 first_observed_at='2024-01-18T14:30:00Z')]


def terms(**changes):
    t=DatedTerms('SPY240119C00100000',pd.Timestamp('2024-01-01T00:00Z'),
        pd.Timestamp('2024-01-20T00:00Z'),pd.Timestamp('2024-01-01T00:00Z'),'a'*64,
        100.,100.,pd.Timestamp('2024-01-19T21:15Z'))
    return replace(t,**changes)


def test_prior_date_and_reference_availability_fail_closed():
    args=dict(right='call',target=0,spot=100.)
    r=select_contract(candidates(),'2024-01-18T20:00Z',**args)
    assert r['reason']=='no_prior_date_observed_candidate'
    r=select_contract(candidates(),'2024-01-19T15:00Z',**args)
    assert r['acquisition_candidate'] and r['selected_contract'] is None
    r=select_contract(candidates(),'2024-01-19T15:00Z',**args,discovery_complete=True,source_admitted=True,
        terms=[terms(available_at=pd.Timestamp('2024-01-19T16:00Z'))])
    assert r['selected_contract'] is None
    r=select_contract(candidates(),'2024-01-19T15:00Z',**args,discovery_complete=True,source_admitted=True,terms=[terms()])
    assert r['selection_eligible'] and not r['entry_eligible']
    r=select_contract(candidates(),'2024-01-19T21:00Z',**args,discovery_complete=True,source_admitted=True,terms=[terms()])
    assert r['selected_contract'] is None


def test_weekly_and_dte_and_ambiguous_terms():
    r=select_contract(candidates(),'2024-01-19T15:00Z',right='call',target=2,spot=100.)
    assert r['reason']=='weekly_listing_evidence_unresolved'
    c=candidates();c[0]['expiration_date']='2024-01-25'
    assert not select_contract(c,'2024-01-19T15:00Z',right='call',target=5,spot=100.)['acquisition_candidate']
    with pytest.raises(ValueError,match='Ambiguous'):
        select_contract(candidates(),'2024-01-19T15:00Z',right='call',target=0,spot=100.,terms=[terms(),terms()],discovery_complete=True,source_admitted=True)


def test_feature_demand_half_open_union_and_0dte_clock():
    a,b=feature_window('2024-01-19T15:00Z',5)
    assert a==pd.Timestamp('2024-01-19T14:54Z') and b==pd.Timestamp('2024-01-19T14:59Z')
    assert union_intervals([(1,3),(3,6),(2,4),(8,9)])==[(1,6),(8,9)]


def catalog_representatives(minutes):
    catalog=json.loads(Path('nn_meta/validation/etfe-setup-20261004-0dte-r0/catalog.json').read_text())
    seen={}
    for r in catalog['records']:
        if r['signal_minutes']==minutes:seen.setdefault(r['strategy'],r)
    return list(seen.values())


@pytest.mark.parametrize('minutes',[1,5,15])
def test_all_twenty_signal_families_prefix_invariance(minutes):
    raw,calendar=fixture();full=session_bars(raw,calendar,minutes)
    records=catalog_representatives(minutes);assert len(records)==20
    cutoff=len(full)-7;prefix=full.iloc[:cutoff]
    def collect(bars):
        result={}
        for batch,channels in signal_batches(bars,records,raw):
            for record in batch:result[record['variant_id']]=np.column_stack([f[record['variant_id']].to_numpy() for f in channels])
        return result
    a,b=collect(full),collect(prefix)
    assert set(a)==set(b)=={r['variant_id'] for r in records}
    for key in a:np.testing.assert_array_equal(a[key][:cutoff],b[key])


def test_independent_demand_overlap_and_uncovered_windows():
    from scripts.audit_etfe_causal import merge,subtract
    assert merge([(1,3),(3,6),(2,4),(8,9)])==[[1,6],[8,9]]
    assert subtract([1,10],[[2,4],[6,8]])==[[1,2],[4,6],[8,10]]
    assert subtract([1,10],[[0,10]])==[]
    assert subtract([1,10],[[10,12]])==[[1,10]]


def test_unknown_priority_terms_never_skip_to_another_contract():
    c=candidates()+[dict(candidates()[0],symbol='SPY240119C00101000',strike=101.)]
    r=select_contract(c,'2024-01-19T15:00Z',right='call',target=0,spot=100.,
        discovery_complete=True,source_admitted=True,
        terms=[terms(symbol='SPY240119C00101000',strike=101.)])
    assert r['selected_contract'] is None and r['reason']=='dated_terms_or_expiry_clock_unresolved'
