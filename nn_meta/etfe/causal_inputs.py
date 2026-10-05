"""Causal raw-price diagnostics from freshly normalized ETFE observations.

These calculations are not action-adjusted/admitted model features. Missing
minutes occupy explicit null grid rows and never become synthetic OHLCV.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from nn_meta.etfe.acquisition import sha
from nn_meta.etfe.normalization import load_normalization, partition_receipt

PRICE_COLUMNS = ['Open','High','Low','Close','Volume']
FEATURES = ['ma_gap','px_vs_fast','rsi14','macd_hist','bb_z','ret_1','ret_8','ret_26',
            'session_gap','gap_abs_z','tod','dow','is_first_hour','is_last_hour','dow_tod']


def normalized_partitions(root, route):
    root=Path(root);plan=load_normalization(root)
    seal=json.loads((root/'NORMALIZED.json').read_text())
    audit=json.loads((root/'INDEPENDENT_AUDIT.json').read_text())
    if (not seal['normalized_complete'] or seal['plan_sha256']!=plan['sha256']
            or audit['plan_sha256']!=plan['sha256'] or audit['rows']!=seal['rows']
            or not audit['raw_occurrence_sequence_preserved']):
        raise ValueError('Complete reconciled fresh normalization required')
    for key,h in seal['partition_receipts'].items():
        p=root/'partitions'/(key+'.json')
        if sha(p.read_bytes())!=h:raise ValueError('Partition receipt drift')
        meta=json.loads(p.read_text())
        if meta['route']==route:
            partition_receipt(root,key)
            yield meta,root/meta['data']


def stock_minutes(root, ticker, *, end=None):
    chunks=[]
    columns=['symbol','timestamp_ns','stock_session','open','high','low','close','volume','quality_flags']
    for _,p in normalized_partitions(root,'stock_bars'):
        frame=pq.read_table(p,columns=columns,filters=[('symbol','=',ticker)]).to_pandas()
        frame=frame[frame.stock_session.eq('stock_regular')]
        if end is not None:frame=frame[frame.timestamp_ns<pd.Timestamp(end).value]
        if not frame.empty:chunks.append(frame)
    if not chunks:raise ValueError('No normalized stock observations')
    frame=pd.concat(chunks,ignore_index=True).sort_values('timestamp_ns')
    if frame.timestamp_ns.duplicated().any():raise ValueError('Duplicate stock minute requires vintage selection')
    frame.index=pd.to_datetime(frame.timestamp_ns,utc=True)
    frame=frame.rename(columns=dict(zip(['open','high','low','close','volume'],PRICE_COLUMNS)))
    frame['input_valid']=frame.quality_flags.map(len).eq(0)&np.isfinite(frame[PRICE_COLUMNS]).all(axis=1)
    frame.loc[~frame.input_valid,PRICE_COLUMNS]=np.nan
    return frame[PRICE_COLUMNS+['input_valid']]


def session_bars(raw, calendar, minutes, *, as_of=None):
    if minutes not in (1,5,15):raise ValueError('ETFE timeframes are 1/5/15')
    if raw.index.tz is None or not raw.index.is_unique or not raw.index.is_monotonic_increasing:
        raise ValueError('Unique ordered aware minute observations required')
    if (raw.index.asi8 % 60_000_000_000).any():raise ValueError('Unaligned raw minutes')
    as_of=pd.Timestamp(as_of) if as_of is not None else raw.index[-1]+pd.Timedelta(minutes=1)
    if as_of.tzinfo is None:raise ValueError('Aware as_of required')
    pieces=[]
    for ordinal,s in enumerate(calendar):
        opened=pd.Timestamp(s['date']+' '+s['open'],tz='America/New_York').tz_convert('UTC')
        closed=pd.Timestamp(s['date']+' '+s['close'],tz='America/New_York').tz_convert('UTC')
        if opened>=as_of:break
        grid=pd.date_range(opened,closed,freq='min',inclusive='left')
        day=raw.reindex(grid).copy();day['observed']=grid.isin(raw.index)
        valid=day['input_valid'].eq(True)&day.observed
        day.loc[~valid,PRICE_COLUMNS]=np.nan;day['valid_minute']=valid.astype(int)
        group=np.arange(len(day))//minutes
        grouped=day.groupby(group,sort=True)
        bars=grouped.agg(Open=('Open','first'),High=('High','max'),Low=('Low','min'),
            Close=('Close','last'),Volume=('Volume','sum'),valid_minutes=('valid_minute','sum'),
            observed_minutes=('observed','sum'))
        bars.index=grid[::minutes];bars.index.name='bar_open'
        bars['bar_end']=bars.index+pd.Timedelta(minutes=minutes)
        bars=bars[bars.bar_end.le(min(closed,as_of))]
        bars['valid']=bars.valid_minutes.eq(minutes)
        bars.loc[~bars.valid,PRICE_COLUMNS]=np.nan
        bars['session_date']=s['date'];bars['session_ordinal']=ordinal
        bars['session_open']=opened;bars['session_close']=closed
        bars['available_at']=bars.bar_end  # declared final-vintage stock-close model
        bars['reason']=np.where(bars.valid,'observed_raw_unadmitted','incomplete_minute_bin')
        pieces.append(bars)
    if not pieces:raise ValueError('No closed regular-session bins')
    return pd.concat(pieces)


def technical_diagnostics(bars, *, fast=10, slow=30):
    c=bars.Close;f=c.rolling(fast).mean();s=c.rolling(slow).mean()
    delta=c.diff();loss=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean().replace(0,np.nan)
    gain=delta.clip(lower=0).ewm(alpha=1/14,adjust=False).mean()
    macd=c.ewm(span=12,adjust=False).mean()-c.ewm(span=26,adjust=False).mean()
    out=pd.DataFrame(index=bars.index)
    out['ma_gap']=(f-s)/c;out['px_vs_fast']=c/f-1
    out['rsi14']=(100-100/(1+gain/loss))/100
    out['macd_hist']=(macd-macd.ewm(span=9,adjust=False).mean())/c
    # Recursive state cannot silently bridge a missing required minute.
    tainted=(~bars.valid).cummax()
    out.loc[tainted,['rsi14','macd_hist']]=np.nan
    out['bb_z']=(c-c.rolling(20).mean())/(2*c.rolling(20).std().replace(0,np.nan))
    for n in (1,8,26):
        complete=bars.valid.rolling(n+1).sum().eq(n+1)
        out[f'ret_{n}']=(c/c.shift(n)-1).where(complete)
    daily=bars.groupby('session_date',sort=True).agg(first=('Open',lambda x:x.iloc[0]),last=('Close',lambda x:x.iloc[-1]))
    gaps=daily['first']/daily['last'].shift()-1
    z=(gaps.abs()-gaps.abs().rolling(60).mean())/gaps.abs().rolling(60).std().replace(0,np.nan)
    out['session_gap']=bars.session_date.map(gaps);out['gap_abs_z']=bars.session_date.map(z)
    elapsed=(bars.index-pd.DatetimeIndex(bars.session_open)).total_seconds()
    duration=(pd.DatetimeIndex(bars.session_close)-pd.DatetimeIndex(bars.session_open)).total_seconds()
    out['tod']=elapsed/duration;out['dow']=bars.index.tz_convert('America/New_York').weekday/4
    out['is_first_hour']=(elapsed<3600).astype(float)
    out['is_last_hour']=((pd.DatetimeIndex(bars.session_close)-pd.DatetimeIndex(bars.bar_end)).total_seconds()<3600).astype(float)
    out['dow_tod']=out.dow*out.tod
    out.loc[~bars.valid,:]=np.nan
    if np.isinf(out.to_numpy()).any():raise ValueError('Infinite diagnostic feature')
    return out[FEATURES]


def minute_context(bars, raw):
    """ORB needs all 15 opening minutes; VWAP uses only completed raw minutes."""
    orb=[];vwap=[]
    for day,chart in bars.groupby('session_date',sort=True):
        opened=chart.session_open.iloc[0];closed=chart.session_close.iloc[0]
        grid=pd.date_range(opened,closed,freq='min',inclusive='left');m=raw.reindex(grid)
        valid=m.input_valid.eq(True)
        m=m.copy();m.loc[~valid,PRICE_COLUMNS]=np.nan
        prefix_valid=valid.cummin()
        pv=((m.High+m.Low+m.Close)/3*m.Volume).cumsum();vol=m.Volume.cumsum()
        for stamp,row in chart.iterrows():
            n=int((row.bar_end-opened).total_seconds()/60)
            done=n>=15 and bool(valid.iloc[:15].all())
            orb.append(dict(or_high=m.High.iloc[:15].max() if done else np.nan,
                or_low=m.Low.iloc[:15].min() if done else np.nan,or_done=done,available_at=row.bar_end))
            vwap.append(pv.iloc[n-1]/vol.iloc[n-1] if n and prefix_valid.iloc[n-1] and vol.iloc[n-1]>0 else np.nan)
    return dict(opening=pd.DataFrame(orb,index=bars.index),
        vwap=pd.DataFrame(dict(vwap=vwap,available_at=bars.bar_end),index=bars.index))
