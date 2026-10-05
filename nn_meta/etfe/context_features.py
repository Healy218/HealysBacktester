"""Daily ETFE context mathematics and explicit next-open availability.

Raw-stock diagnostics remain unadmitted pending dated action reconstruction.
Option aggregates require supplied dated coverage/terms evidence, never today's
contract listing or an empty response promoted to a no-trade observation.
"""
import math
import numpy as np
import pandas as pd
from nn_meta.etfe.event_features import aware

STOCK_FIELDS=['rvol_5','rvol_21','beta_60d']
OPTION_FIELDS=['etfe_bar_iv_near','etfe_bar_iv_far','etfe_bar_iv_term_slope',
 'etfe_bar_iv_change_5','etfe_bar_put_call_volume_ratio','etfe_spy_bar_iv_near','etfe_rv_bar_iv_spread']


def daily_stock(bars):
    """Expected calendar bins must be present, including explicit invalid rows."""
    if bars.empty or not bars.index.is_unique or not bars.index.is_monotonic_increasing: raise ValueError('Ordered stock grid required')
    rows=[]
    for day,frame in bars.groupby('session_date',sort=True):
        opened=aware(frame.session_open.iloc[0]); closed=aware(frame.session_close.iloc[0])
        expected=pd.date_range(opened,closed,freq='min',inclusive='left')
        if not frame.index.equals(expected): raise ValueError('Complete expected minute grid required')
        valid=bool(frame.valid.all() and np.isfinite(frame.Close).all() and frame.Close.gt(0).all())
        rows.append(dict(session_date=day,session_ordinal=int(frame.session_ordinal.iloc[0]),
            session_open=opened,session_close=closed,close=float(frame.Close.iloc[-1]) if valid else np.nan,
            complete=valid))
    out=pd.DataFrame(rows).set_index('session_date')
    if len(out)>1 and not out.session_ordinal.diff().iloc[1:].eq(1).all():raise ValueError('Daily calendar gap')
    return out


def stock_context(daily,spy):
    if not daily.index.equals(spy.index) or not daily.session_open.equals(spy.session_open): raise ValueError('Paired complete calendar required')
    close=daily.close.where(daily.complete); benchmark=spy.close.where(spy.complete)
    logret=np.log(close).diff(); ret=close/close.shift()-1; market=benchmark/benchmark.shift()-1
    values=pd.DataFrame(index=daily.index)
    for n in (5,21):values[f'rvol_{n}']=math.sqrt(252)*logret.rolling(n,min_periods=n).std(ddof=1)
    paired=ret.notna()&market.notna(); stock=ret.where(paired); market=market.where(paired)
    variance=market.rolling(60,min_periods=60).var(ddof=1)
    values['beta_60d']=stock.rolling(60,min_periods=60).cov(market,ddof=1)/variance.where(variance>0)
    # d's completed data are not observable as daily context until d+1's open.
    values=values.shift(1); reasons=pd.DataFrame('observed_raw_unadmitted',index=values.index,columns=values.columns)
    for n in STOCK_FIELDS:reasons.loc[values[n].isna(),n]='insufficient_complete_daily_history_or_zero_variance'
    return values,reasons


def bs_price(spot,strike,years,sigma,right,rate=.0425,dividend=.012):
    if right not in ('call','put') or not all(math.isfinite(v) and v>0 for v in (spot,strike,years,sigma)):
        raise ValueError('Positive finite BS proxy inputs and known right required')
    d1=(math.log(spot/strike)+(rate-dividend+.5*sigma*sigma)*years)/(sigma*math.sqrt(years))
    d2=d1-sigma*math.sqrt(years); cdf=lambda x:.5*(1+math.erf(x/math.sqrt(2)))
    s=spot*math.exp(-dividend*years); k=strike*math.exp(-rate*years)
    return s*cdf(d1)-k*cdf(d2) if right=='call' else k*cdf(-d2)-s*cdf(-d1)


def proxy_iv(price,spot,strike,days,right):
    if isinstance(days,bool) or int(days)!=days or not 1<=days<=45:raise ValueError('Daily context uses actual 1–45 calendar DTE')
    if not math.isfinite(price) or price<=0:return np.nan,'invalid_premium'
    lo=1e-6; hi=5.; t=days/365
    if price<bs_price(spot,strike,t,lo,right) or price>bs_price(spot,strike,t,hi,right):
        return np.nan,'outside_proxy_bounds'
    for _ in range(100):
        mid=(lo+hi)/2; p=bs_price(spot,strike,t,mid,right)
        if abs(p-price)<=1e-8:return mid,'observed_proxy'
        if p<price:lo=mid
        else:hi=mid
    return np.nan,'proxy_solver_tolerance'


def surface_summary(contracts,spot,closed,next_open,*,proof=None):
    """One record per dated contract, with reconciled full-session volume.

    Proof is supplied by the future admission layer; current raw transport alone
    cannot populate it. Each contract's close/terms clocks are still checked.
    """
    closed=aware(closed); next_open=aware(next_open)
    if next_open<=closed or not math.isfinite(spot) or spot<=0:raise ValueError('Valid close/next-open context required')
    empty=dict(near=np.nan,far=np.nan,ratio=np.nan,raw_ratio=np.nan)
    if proof is None:return empty,dict(reason='dated_surface_coverage_unresolved',contracts=len(contracts))
    if (len(proof['sha256'])!=64 or any(c not in '0123456789abcdef' for c in proof['sha256'])
            or proof['session_date']!=str(closed.tz_convert('America/New_York').date())
            or aware(proof['available_at'])>next_open
            or not all(proof.get(k) is True for k in ('catalog_complete','capture_complete','dated_terms_complete'))):
        return empty,dict(reason='dated_surface_coverage_unresolved',contracts=len(contracts))
    if len({r['symbol'] for r in contracts})!=len(contracts):raise ValueError('Duplicate contract surface')
    if set(proof['symbols'])!={r['symbol'] for r in contracts} or any(r['underlying']!=proof['underlying'] for r in contracts):
        raise ValueError('Surface coverage identity mismatch')
    near=[];far=[];vol={'call':0.,'put':0.};statuses={};eligible=0
    for row in contracts:
        right=row['right'];strike=row['strike'];premium=row['closing_vwap'];end=aware(row['closing_end'])
        dte=(pd.Timestamp(row['expiration_date']).date()-closed.tz_convert('America/New_York').date()).days
        if right not in vol or not math.isfinite(strike) or strike<=0:raise ValueError('Invalid dated contract economics')
        if not 1<=dte<=45:continue
        if aware(row['terms_available_at'])>closed or aware(row['closing_available_at'])>next_open:
            return empty,dict(reason='required_observation_unavailable',symbol=row['symbol'])
        if not closed-pd.Timedelta(seconds=60)<=end<=closed:
            statuses[row['symbol']]='no_fresh_closing_bar';continue
        if not math.isfinite(premium) or premium<.20:continue
        volume=row['daily_volume']
        if not math.isfinite(volume) or volume<0:raise ValueError('Invalid reconciled daily volume')
        vol[right]+=volume;eligible+=1
        if abs(math.log(strike/spot))>=.01:continue
        iv,reason=proxy_iv(premium,spot,strike,dte,right);statuses[row['symbol']]=reason
        if math.isfinite(iv):(near if dte<=20 else far).append(iv)
    raw=vol['put']/vol['call'] if vol['call']>0 else np.nan
    return dict(near=float(np.median(near)) if near else np.nan,far=float(np.median(far)) if far else np.nan,
        ratio=float(np.clip(raw,0,5)),raw_ratio=raw),dict(reason='complete_surface_diagnostic',contracts=len(contracts),eligible=eligible,
        near_count=len(near),far_count=len(far),call_volume=vol['call'],put_volume=vol['put'],contract_reasons=statuses)


def option_context(surfaces,spy_surfaces,stock):
    if not surfaces.index.equals(spy_surfaces.index) or not surfaces.index.equals(stock.index):raise ValueError('Consecutive paired surface calendar required')
    prior=surfaces.shift(1); values=pd.DataFrame(index=surfaces.index)
    values[OPTION_FIELDS[0]]=prior.near; values[OPTION_FIELDS[1]]=prior.far
    values[OPTION_FIELDS[2]]=prior.far-prior.near
    # Exact five-session endpoints; missing intermediate days are not filled.
    values[OPTION_FIELDS[3]]=prior.near-prior.near.shift(5)
    values[OPTION_FIELDS[4]]=prior.ratio
    values[OPTION_FIELDS[5]]=spy_surfaces.near.shift(1)
    values[OPTION_FIELDS[6]]=stock.rvol_21-prior.near
    return values
