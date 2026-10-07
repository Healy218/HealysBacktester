"""Daily-bar existence census: first traded session per admitted ETFE contract."""
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from nn_meta.etfe import option_daily_capture as o

ROOT=Path(__file__).resolve().parents[2]
POLICY=ROOT/'nn_meta/validation/etfe-dated-policy-20261006-r0'
CALENDAR=ROOT/'nn_meta/data_cache_etfe/alpaca-fresh-20261004-calendar-r1/000-calendar.body'
FIRST_EXPIRY=dt.date(2024,1,18)
LAST_EXPIRY=dt.date(2026,10,9)  # latest expiry reachable by a 0-5 DTE entry or roll on 2026-10-02
LOOKBACK_DAYS=50
LAST_SESSION=dt.date(2026,10,2)


def contracts():
    c=pq.read_table(POLICY/'CONTRACTS.parquet',columns=['symbol','underlying','expiration_date','status']).to_pandas()
    c=c[(c.status=='admitted')&c.expiration_date.notna()]
    return c[(c.expiration_date>=FIRST_EXPIRY)&(c.expiration_date<=LAST_EXPIRY)]


def jobs():
    groups=defaultdict(list)
    for s,u,e in zip(*(contracts()[k] for k in ('symbol','underlying','expiration_date'))):groups[u,e].append(s)
    out=[]
    for (u,e),symbols in sorted(groups.items()):
        start=pd.Timestamp(max(e-dt.timedelta(days=LOOKBACK_DAYS),dt.date(2024,1,1)).isoformat(),tz='America/New_York')
        end=pd.Timestamp(min(e,LAST_SESSION).isoformat()+' 23:59:59',tz='America/New_York')
        symbols=sorted(symbols)
        for i in range(0,len(symbols),100):
            out.append(o.job('option_daily_bars',dict(symbols=','.join(symbols[i:i+100]),timeframe='1Day',
                start=start.tz_convert('UTC').isoformat(),end=end.tz_convert('UTC').isoformat(),sort='asc',limit=10000),
                'dated_contract_existence'))
    return out


def prepare(root):
    j=jobs()
    parent=dict(policy_resolution_sha256=o.sha((POLICY/'RESOLUTION.json').read_bytes()),
        expiry_range=[FIRST_EXPIRY.isoformat(),LAST_EXPIRY.isoformat()],lookback_days=LOOKBACK_DAYS,contracts=len(contracts()))
    return o.prepare(root,j,parent=parent,max_total_requests=2*len(j))


def first_traded(root):
    """Symbol -> earliest session date with a daily bar (volume >= 1)."""
    first={}
    for item in o.load_plan(root)['jobs']:
        history,_,done=o.committed(root,item)
        if not done:raise ValueError('Incomplete existence job')
        for _,body,_ in history:
            for sym,row in o.rows(body,item):
                if row['v']<1:continue
                day=pd.Timestamp(row['t']).tz_convert('America/New_York').date()
                if sym not in first or day<first[sym]:first[sym]=day
    return first


def available_from(first,trading_days):
    """Existence observed on a session is usable from the next trading session (strictly earlier date)."""
    days=sorted(trading_days);out={}
    import bisect
    for sym,d in first.items():
        i=bisect.bisect_right(days,d)
        out[sym]=days[i] if i<len(days) else None
    return out
