"""Full thirteen-source V7 projections with timeframe-aware causal context."""
from __future__ import annotations
from copy import deepcopy
import inspect
import numpy as np
import pandas as pd


def source_frames(bars,context,*,minimum_tick=.01,observation_index=None,aliases=None):
    from nn_meta.tradingview_features import SOURCE_MAP,_settings,ROOT
    from indicators.tradingview_registry import build_catalog
    from nn_meta.v7.setup import setup_scanner
    from v3.tv_amd_po3 import AmdConfig
    settings=_settings(build_catalog(ROOT),minimum_tick,'local_research')
    allowed = {alias for alias, _, _ in SOURCE_MAP}
    if aliases is not None and (not set(aliases) or not set(aliases).issubset(allowed)):
        raise ValueError('Unknown or empty source selection')
    frames={};minutes=context['minutes'];as_of=context['available_at'][-1]
    for alias,_,calculator in SOURCE_MAP:
        if aliases is not None and alias not in aliases:
            continue
        kwargs=deepcopy(settings[alias])
        if alias=='setup':calculator=setup_scanner
        params=inspect.signature(calculator).parameters
        if 'bar_minutes' in params:kwargs['bar_minutes']=minutes
        if 'as_of' in params:kwargs['as_of']=as_of
        if alias=='amd':kwargs['config']=AmdConfig(**kwargs['config'])
        if alias=='setup':
            kwargs.update(vwap_observations=context['vwap'],opening_observations=context['opening'])
        if alias=='htf':
            flags=context['flags'].htf_change.copy();flags.attrs['htf_period']=context['htf_period']
            kwargs.update(chart_period=str(minutes),htf_change=flags)
        if alias in ('footprint','htf') and observation_index is not None:
            positions=bars.index.get_indexer(observation_index)
            if (positions<0).any():raise ValueError('Unknown projection observation')
            kwargs['observation_positions']=[int(i) for i in positions]
        frame=calculator(bars,**kwargs)
        if 'available_at' in frame:
            expected=frame.index+pd.Timedelta(minutes=minutes)
            if not pd.DatetimeIndex(frame.available_at).equals(expected):
                raise ValueError(f'{alias}: wrong feature availability')
        frames[alias]=frame
    return frames


def project(bars,frames,context):
    from nn_meta.tradingview_features import FEATURE_SPECS,PHASE_CODES
    from v3.pine_compat import atr
    from v3._tv_trend_support import pine_ohlc
    scale=atr(pine_ohlc(bars),14).replace(0,np.nan)
    index=frames['footprint'].index
    columns={}
    for spec in FEATURE_SPECS:
        frame=frames[spec.source].loc[index];raw=frame[spec.field]
        value=raw.map(PHASE_CODES).astype(float) if spec.transform=='phase' else raw.astype(float)
        if spec.transform=='price_atr':value=(value-bars.Close.loc[index])/scale.loc[index]
        elif spec.transform=='range_atr':value=value/scale.loc[index]
        elif spec.transform=='percent':value=value/100.
        if spec.valid_when:value=value.where(frame[spec.valid_when])
        if spec.source=='probability' and spec.field.endswith('reference_win_pct'):
            side=spec.field.split('_')[0]
            value=value.where(frame[f'total_{side}_wins']+frame[f'total_{side}_losses']>0)
        columns[spec.name]=value
    result=pd.DataFrame(columns,index=index)
    if np.isinf(result.to_numpy()).any():raise ValueError('Infinite feature projection')
    result.attrs.update(contract='v7-timeframe-tv13-v1',minutes=context['minutes'],
                        context_policy=context['policy'],external_parity=False)
    return result


def technical(bars,context,fast=10,slow=30):
    # Preserve bar-count lookbacks; exchange-clock fields must not count
    # observed rows as elapsed time when minutes are missing or close is early.
    from nn_meta.build_meta_dataset import technical_features
    result=technical_features(bars,fast,slow)
    elapsed=(bars.index-context['session_open']).total_seconds()/60
    remaining=(context['session_close']-(bars.index+pd.Timedelta(minutes=context['minutes']))).total_seconds()/60
    duration=(context['session_close']-context['session_open']).total_seconds()/60
    result['tod']=elapsed/duration
    result['is_first_hour']=(elapsed<60).astype(float)
    result['is_last_hour']=(remaining<60).astype(float)
    result['dow_tod']=result.dow*result.tod
    return result
