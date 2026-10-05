from dataclasses import replace
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from nn_meta.etfe.event_features import (catalog_features, static_names, signal_history,
    IdentityEvidence, contract_features, sector_features)
from nn_meta.etfe.context_features import (stock_context, daily_stock, bs_price, proxy_iv,
    surface_summary, option_context, OPTION_FIELDS)
from nn_meta.etfe.causal_inputs import session_bars
from tests.test_etfe_causal import fixture


def catalog():return json.loads(Path('nn_meta/validation/etfe-setup-20261004-0dte-r0/catalog.json').read_text())['records']


def test_all_catalog_parameters_and_onehots():
    records=catalog();v,r=catalog_features(records)
    assert v.shape==(8451,77) and v.columns.tolist()==static_names()
    assert v.filter(like='strat_').sum(axis=1).eq(1).all()
    assert v.filter(like='timeframe_').sum(axis=1).eq(1).all()
    setup=v.strat_tv_setup.eq(1)
    assert v.loc[setup,'param_setup_max_bars'].eq(60).all()
    assert v.loc[setup,'param_setup_stop_atr'].eq(1.2).all()
    assert v.loc[~setup,'param_setup_max_bars'].isna().all()
    assert v.loc[~setup,'param_setup_ORB'].isna().all()
    assert r.eq('structural_absence').equals(v.isna())


def proof(key='X',**values):
    return IdentityEvidence(key,pd.Timestamp('2024-01-01',tz='UTC'),pd.Timestamp('2024-02-01',tz='UTC'),
        pd.Timestamp('2024-01-01',tz='UTC'),'a'*64,values)


def test_dated_contract_0dte_and_missing_future_evidence():
    p=proof(right='call',strike=100.,expiration_date='2024-01-19');at='2024-01-19T15:00Z'
    v,r=contract_features('X',at,100.,direction='long',evidence=[p]);assert v==dict(dte_frac=0.,moneyness=0.)
    late=replace(p,available_at=pd.Timestamp('2024-01-20',tz='UTC'))
    assert all(math.isnan(v) for v in contract_features('X',at,100,direction='long',evidence=[late])[0].values())
    with pytest.raises(ValueError,match='Ambiguous'):contract_features('X',at,100,direction='long',evidence=[p,p])
    with pytest.raises(ValueError,match='mismatch'):contract_features('X',at,100,direction='short',evidence=[p])
    p=proof(right='call',strike=101.,expiration_date='2024-01-24')
    assert contract_features('X',at,100,direction='long',evidence=[p])[0]['dte_frac']==1
    with pytest.raises(ValueError,match='range'):contract_features('X','2024-01-18T15:00Z',100,direction='long',evidence=[p])


def test_sector_requires_dated_identity():
    assert all(math.isnan(v) for v in sector_features('SPY','2024-01-19T15:00Z')[0].values())
    v,r=sector_features('SPY','2024-01-19T15:00Z',evidence=[proof('SPY',sector='idx_etf')])
    assert v['sec_idx_etf']==1 and sum(v.values())==1


def test_age_uses_prefix_and_variant_direction_not_target_replication():
    raw,cal=fixture(1);bars=session_bars(raw,cal,5);r=next(x for x in catalog() if x['strategy']=='ma' and x['signal_minutes']==5)
    channels=[pd.DataFrame(False,index=bars.index,columns=[r['variant_id']]) for _ in range(4)]
    channels[0].iloc[[2,5,8],0]=True;channels[2].iloc[[4,8],0]=True
    out=signal_history(bars,[r],iter([([r],channels)]),observation_start=bars.bar_end.iloc[5])
    long=out[out.direction.eq('long')];short=out[out.direction.eq('short')]
    assert long.previous_position.tolist()==[2,5]
    np.testing.assert_allclose(long.bars_since_signal,math.log1p(3))
    assert short.previous_position.tolist()==[4] and short.dir_short.eq(1).all()
    assert long.ma_gap.iloc[-1]==pytest.approx((bars.Close.iloc[7:9].mean()-bars.Close.iloc[5:9].mean())/bars.Close.iloc[8])


def daily(n=75):
    idx=pd.Index([str(t.date()) for t in pd.bdate_range('2024-01-01',periods=n)],name='session_date')
    x=np.arange(n);cl=100*np.exp(.001*x+.01*np.sin(x))
    return pd.DataFrame(dict(close=cl,complete=True,session_open=pd.to_datetime(idx,utc=True)),index=idx)


def test_daily_prefix_next_open_and_hand_computed_vol_beta():
    d=daily();v,r=stock_context(d,d)
    assert v.rvol_5.iloc[:6].isna().all() and v.rvol_21.iloc[:22].isna().all()
    assert v.rvol_5.iloc[6]==pytest.approx(np.std(np.diff(np.log(d.close.iloc[:6])),ddof=1)*np.sqrt(252))
    assert v.beta_60d.iloc[:61].isna().all();np.testing.assert_allclose(v.beta_60d.iloc[61:],1,atol=1e-12)
    pv,pr=stock_context(d.iloc[:65],d.iloc[:65]);pd.testing.assert_frame_equal(pv,v.iloc[:65]);pd.testing.assert_frame_equal(pr,r.iloc[:65])
    changed=d.copy();changed.loc[changed.index[64]:,'close']*=3
    cv,_=stock_context(changed,changed);pd.testing.assert_frame_equal(cv.iloc[:65],v.iloc[:65])


def test_daily_gaps_and_zero_variance_do_not_fill():
    d=daily();d.loc[d.index[10],'complete']=False
    v,_=stock_context(d,d);assert v.rvol_5.iloc[11:17].isna().all()
    d=daily();d['close']=100.;v,_=stock_context(d,d);assert v.beta_60d.isna().all()
    raw,cal=fixture(1);bars=session_bars(raw.drop(raw.index[20]),cal,1)
    assert not daily_stock(bars).complete.iloc[0]
    with pytest.raises(ValueError,match='grid'):daily_stock(bars.drop(bars.index[20]))


@pytest.mark.parametrize('right',['call','put'])
def test_iv_roundtrip_and_bounds(right):
    for days in (1,20,21,45):
        p=bs_price(100,100,days/365,.3,right);iv,r=proxy_iv(p,100,100,days,right)
        assert iv==pytest.approx(.3,abs=1e-7) and r=='observed_proxy'
    assert math.isnan(proxy_iv(200,100,100,20,right)[0])
    with pytest.raises(ValueError):proxy_iv(1,100,100,0,right)


def surface():
    close=pd.Timestamp('2024-01-18T21:00Z');opened=pd.Timestamp('2024-01-19T14:30Z');rows=[]
    for i,(days,right,vol) in enumerate(((5,'call',10),(5,'put',80),(30,'call',5))):
        rows.append(dict(symbol=str(i),underlying='SPY',right=right,strike=100.,
            expiration_date=str((close+pd.Timedelta(days=days)).date()),closing_vwap=bs_price(100,100,days/365,.3+i*.1,right),
            closing_end=close,closing_available_at=close+pd.Timedelta(seconds=1),terms_available_at=close-pd.Timedelta(days=1),daily_volume=vol))
    p=dict(sha256='b'*64,underlying='SPY',symbols=[r['symbol'] for r in rows],session_date='2024-01-18',available_at=close+pd.Timedelta(seconds=1),
        catalog_complete=True,capture_complete=True,dated_terms_complete=True)
    return rows,close,opened,p


def test_surface_medians_clipped_ratio_and_no_unknown_zero():
    rows,c,o,p=surface();v,a=surface_summary(rows,100,c,o,proof=p)
    assert v['near']==pytest.approx(.35,abs=1e-7) and v['far']==pytest.approx(.5,abs=1e-7)
    assert v['ratio']==5 and v['raw_ratio']==pytest.approx(80/15)
    v,a=surface_summary(rows,100,c,o);assert all(math.isnan(x) for x in v.values())
    rows[0]['closing_available_at']=o+pd.Timedelta(seconds=1)
    assert surface_summary(rows,100,c,o,proof=p)[1]['reason']=='required_observation_unavailable'


def test_surface_identity_and_freshness():
    rows,c,o,p=surface();bad=dict(p,symbols=[])
    with pytest.raises(ValueError,match='identity'):surface_summary(rows,100,c,o,proof=bad)
    rows[0]['closing_end']=c-pd.Timedelta(seconds=61)
    v,a=surface_summary(rows,100,c,o,proof=p);assert a['eligible']==2
    assert v['near']==pytest.approx(.4,abs=1e-7)


def test_option_context_no_forward_fill_and_exact_five_session_lag():
    idx=pd.RangeIndex(9);s=pd.DataFrame(dict(near=np.arange(9)/10,far=np.arange(9)/10+.2,ratio=1.),index=idx)
    stock=pd.DataFrame(dict(rvol_21=.8),index=idx);v=option_context(s,s,stock)
    assert v.iloc[0].isna().all();assert v.iloc[6][OPTION_FIELDS[3]]==pytest.approx(.5)
    s.loc[5,'near']=np.nan;v=option_context(s,s,stock)
    assert pd.isna(v.loc[6,OPTION_FIELDS[0]]) and pd.isna(v.loc[6,OPTION_FIELDS[3]])


def test_bs_known_value_and_zero_call_volume():
    assert bs_price(100,100,1,.2,'call',rate=.05,dividend=0)==pytest.approx(10.450583572185565)
    rows,c,o,p=surface()
    for r in rows:
        if r['right']=='call':r['daily_volume']=0
    v,a=surface_summary(rows,100,c,o,proof=p);assert math.isnan(v['ratio']) and math.isnan(v['raw_ratio'])


def test_surface_late_proof_and_daily_context_future_invariance():
    rows,c,o,p=surface();p['available_at']=o+pd.Timedelta(seconds=1)
    assert surface_summary(rows,100,c,o,proof=p)[1]['reason']=='dated_surface_coverage_unresolved'
    s=pd.DataFrame(dict(near=np.arange(10)*.01+.2,far=.5,ratio=1.))
    stock=pd.DataFrame(dict(rvol_21=.3),index=s.index);v=option_context(s,s,stock)
    s.loc[5:,'near']=4
    pd.testing.assert_frame_equal(v.iloc[:6],option_context(s,s,stock).iloc[:6])


def test_catalog_rejects_bad_parameter_and_missing_setup_identity():
    r=next(x for x in catalog() if x['strategy']=='tv_setup')
    with pytest.raises(ValueError,match='Setup'):catalog_features([dict(r,params={})])
    with pytest.raises(ValueError,match='numeric'):catalog_features([dict(r,params=dict(r['params'],setup_stop_atr='1.2'))])
