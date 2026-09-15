"""Explicit exchange-clock inputs for V7; only completed minutes are consumed."""
from __future__ import annotations
import numpy as np
import pandas as pd
from nn_meta.session_calendar import SessionCalendar


def chart_context(bars, minute_bars, calendar_document, minutes):
    from v3.tv_htf_log_profile import auto_htf_period
    if minutes not in (1,5,15,30) or bars.empty or minute_bars.empty:
        raise ValueError('Nonempty 1/5/15/30 chart and minute inputs required')
    for frame in (bars,minute_bars):
        if (not isinstance(frame.index,pd.DatetimeIndex) or frame.index.tz is None
                or not frame.index.is_monotonic_increasing or not frame.index.is_unique):
            raise ValueError('Unique ordered timezone-aware input required')
    calendar=SessionCalendar(calendar_document)
    days=bars.index.tz_convert('America/New_York').strftime('%Y-%m-%d')
    available=bars.index+pd.Timedelta(minutes=minutes)
    period=auto_htf_period(str(minutes))
    sessions=sorted(calendar.sessions); ordinal={d:i for i,d in enumerate(sessions)}
    keys=[];opens=[];closes=[]
    for stamp,day in zip(bars.index,days):
        bounds=calendar.bounds(day)
        if bounds is None:raise ValueError('Non-session chart bar')
        opening,closing=[v.tz_localize('UTC') for v in bounds]
        if stamp<opening or stamp+pd.Timedelta(minutes=minutes)>closing or (stamp-opening).value % (minutes*60_000_000_000):
            raise ValueError('Chart bar not aligned to covered regular session')
        opens.append(opening);closes.append(closing)
        keys.append(ordinal[day]//2 if period=='2D' else (day,int((stamp-opening).total_seconds()//(int(period)*60))))
    reset=np.array([True]+[days[i]!=days[i-1] for i in range(1,len(days))])
    change=pd.Series([True]+[keys[i]!=keys[i-1] for i in range(1,len(keys))],index=bars.index,dtype=bool)
    change.attrs['htf_period']=period
    # Working assumptions are named/bound, not presented as captured Pine parity.
    flags=pd.DataFrame({'vwap_reset':reset,'htf_change':change,'available_at':bars.index},index=bars.index)
    opening_rows=[];vw=[]
    minute_days=minute_bars.index.tz_convert('America/New_York').strftime('%Y-%m-%d')
    for day in sorted(set(days)):
        indexes=np.flatnonzero(days==day);opening=opens[indexes[0]];closing=closes[indexes[0]]
        source=minute_bars[(minute_days==day)&(minute_bars.index>=opening)&(minute_bars.index<closing)]
        before=source[source.index<opening+pd.Timedelta(minutes=15)]
        expected=pd.date_range(opening,periods=15,freq='min')
        complete=before.index.equals(expected)
        pv=((source.High+source.Low+source.Close)/3*source.Volume).cumsum()
        volume=source.Volume.cumsum()
        for i in indexes:
            done=complete and available[i]>=opening+pd.Timedelta(minutes=15)
            opening_rows.append((i,{'or_high':float(before.High.max()) if done else np.nan,
                'or_low':float(before.Low.min()) if done else np.nan,'or_done':done,'available_at':available[i]}))
            n=source.index.searchsorted(available[i]-pd.Timedelta(minutes=1),side='right')
            vw.append((i,float(pv.iloc[n-1]/volume.iloc[n-1]) if n and volume.iloc[n-1]>0 else np.nan))
    orb=pd.DataFrame([v for _,v in sorted(opening_rows)],index=bars.index)
    vwap=pd.DataFrame({'vwap':[v for _,v in sorted(vw)],'available_at':available},index=bars.index)
    return {'minutes':minutes,'available_at':available,'flags':flags,'opening':orb,'vwap':vwap,
            'session_open':pd.DatetimeIndex(opens),'session_close':pd.DatetimeIndex(closes),
            'htf_period':period,'policy':'local-exchange-open; 2D consecutive captured-session pairs; minute-HLC3 VWAP; complete 15m OR',
            'external_parity':False}
