"""Vectorized daily IV proxies from observed Massive aggregates and raw stock closes.

These preserve the declared fixed-rate European approximation used by the V7
baseline. They are features, never executable quotes or standard-deliverable proof.
"""
import numpy as np
import pandas as pd
from nn_meta.v7.daily import SurfacePolicy


def surface_panel(day, stocks, options, *, policy=SurfacePolicy()):
    from nn_options_signal.build_dataset import implied_vol, bs_price
    if pd.Timestamp(day).date().isoformat() != day:
        raise ValueError('Exact ISO surface date required')
    if (not len(stocks) or not {'stock_ticker','raw_close','observed_minutes'}.issubset(stocks)
            or stocks.stock_ticker.isna().any() or stocks.stock_ticker.duplicated().any()
            or not stocks.stock_ticker.str.fullmatch(r'[A-Z0-9.]+').all()):
        raise ValueError('Unique named raw stock observations required')
    stocks=stocks.copy()
    observed=stocks.observed_minutes.gt(0)
    if (not pd.api.types.is_integer_dtype(stocks.observed_minutes) or stocks.observed_minutes.lt(0).any()
            or not np.isfinite(stocks.loc[observed,'raw_close']).all()
            or stocks.loc[observed,'raw_close'].le(0).any()
            or not stocks.loc[~observed,'raw_close'].isna().all()):
        raise ValueError('Raw price and observed-minute status disagree')
    stocks['root']=stocks.stock_ticker.str.replace('.','',regex=False)
    if stocks.root.duplicated().any():raise ValueError('Ambiguous normalized option roots')
    if not {'ticker','close','volume'}.issubset(options) or options.ticker.isna().any():
        raise ValueError('Complete daily option observations required')
    roots=options.ticker.str[2:-15]
    keep=roots.isin(stocks.root)
    frame=options.loc[keep,['ticker','close','volume']].copy()
    frame['root']=roots[keep]
    if (not frame.ticker.str.fullmatch(r'O:[A-Z0-9]+\d{6}[CP]\d{8}').all()
            or frame.ticker.duplicated().any()):
        raise ValueError('Malformed or duplicate selected option observations')
    frame['expiry']=pd.to_datetime(frame.ticker.str[-15:-9],format='%y%m%d')
    frame['right']=frame.ticker.str[-9]
    frame['strike']=frame.ticker.str[-8:].astype(float)/1000
    frame['dte']=(frame.expiry-pd.Timestamp(day)).dt.days
    if (not np.isfinite(frame[['close','volume','strike']].to_numpy()).all()
            or (frame[['close','volume']]<0).any().any() or frame.strike.le(0).any()):
        raise ValueError('Invalid selected option daily values')
    counts=frame.groupby('root').size()
    frame=frame[(frame.dte>=1)&(frame.dte<=policy.maximum_dte)&(frame.close>=policy.minimum_premium)]
    admitted_counts=frame.groupby('root').size()
    volumes=frame.groupby(['root','right']).volume.sum().unstack('right').reindex(columns=['C','P'])
    ratio=volumes.P/volumes.C.where(volumes.C>0)
    frame=frame.join(stocks.set_index('root').raw_close,on='root',validate='many_to_one')
    atm=frame[frame.raw_close.notna() & (np.abs(np.log(frame.strike/frame.raw_close))<policy.near_atm_log_band)].copy()
    if len(atm):
        premium,spot,strike,tenor,calls=(atm.close.to_numpy(),atm.raw_close.to_numpy(),
            atm.strike.to_numpy(),atm.dte.to_numpy()/365.,atm.right.eq('C').to_numpy())
        atm['iv']=implied_vol(premium,spot,strike,tenor,calls,r=policy.risk_free_rate,q=policy.dividend_yield)
        ceiling=bs_price(spot,strike,tenor,5.,policy.risk_free_rate,policy.dividend_yield,calls)
        atm.loc[premium>ceiling,'iv']=np.nan
    else:atm['iv']=pd.Series(dtype=float)
    result=stocks.set_index('root')
    result['source_date']=day
    result['atm_iv_near']=atm[atm.dte<=20].groupby('root').iv.median()
    result['atm_iv_far']=atm[atm.dte>20].groupby('root').iv.median()
    result['pc_ratio']=ratio
    for field,values in [('option_contract_observations',admitted_counts),('raw_option_contract_observations',counts),
                         ('near_iv_observations',atm[atm.dte<=20].groupby('root').iv.count()),
                         ('far_iv_observations',atm[atm.dte>20].groupby('root').iv.count())]:
        result[field]=values.reindex(result.index,fill_value=0).astype('int64')
    result['capture_complete']=True
    result['stock_observed']=result.observed_minutes.gt(0)
    result['surface_status']=np.select([~result.stock_observed,result.raw_option_contract_observations.eq(0),
        result.option_contract_observations.eq(0)],['no_stock_observation','no_option_observation','no_admitted_tenor_premium'],
        default='observed_options')
    # A missing stock observation cannot supply IV. Put/call volume remains an
    # observed statistic, with stock absence explicitly flagged for the consumer.
    if np.isinf(result[['atm_iv_near','atm_iv_far','pc_ratio']].to_numpy()).any():
        raise ValueError('Surface proxy overflow')
    return result.reset_index().rename(columns={'root':'option_root'})
