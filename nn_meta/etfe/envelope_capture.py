"""Prepare ETFE envelope captures (option minute bars, SIP stock quotes) from a frozen DEMAND.json."""
from collections import defaultdict
import json
from pathlib import Path

import pandas as pd

from nn_meta.etfe import option_minute_capture as m,stock_quote_capture_v2 as q

ROOT=Path(__file__).resolve().parents[2]
DEMAND=ROOT/'nn_meta/validation/etfe-envelope-demand-20261006-r0/DEMAND.json'


def load_demand():
    raw=DEMAND.read_bytes();return json.loads(raw),m.sha(raw)


def bar_jobs(demand):
    groups=defaultdict(list)
    for sym,(lo,hi) in demand['bars'].items():
        t,_,e=demand['meta'][sym];groups[t,e].append((sym,lo,hi))
    jobs=[]
    for key in sorted(groups):
        rows=sorted(groups[key])
        for i in range(0,len(rows),100):
            chunk=rows[i:i+100];lo=min(r[1] for r in chunk);hi=max(r[2] for r in chunk)
            jobs.append(m.job('option_minute_bars',dict(symbols=','.join(r[0] for r in chunk),timeframe='1Min',
                start=pd.Timestamp(lo,tz='UTC').floor('min').isoformat(),end=pd.Timestamp(hi-1,tz='UTC').isoformat(),
                sort='asc',limit=10000),'envelope_holding_and_roll_bars'))
    return jobs


def quote_jobs(demand):
    jobs=[]
    for purpose,windows in (('expiry_itm_quote',demand['quotes_itm']),('stock_liquidation_quote',demand['quotes_liq'])):
        for sym,start,end in sorted(set(map(tuple,windows))):
            s=pd.Timestamp(start).tz_convert('UTC');e=pd.Timestamp(end).tz_convert('UTC')-pd.Timedelta(1,'ns')
            jobs.append(q.job('stock_quotes',dict(symbols=sym,start=s.isoformat(),end=e.isoformat(),feed='sip',asof='-',
                sort='asc',limit=10000),purpose))
    return jobs


def prepare(kind,root):
    demand,digest=load_demand();parent=dict(demand_sha256=digest,demand_schema=demand['schema'],estimate=demand['estimate'])
    if kind=='bars':
        jobs=bar_jobs(demand);return m.prepare(root,jobs,parent=parent,max_total_requests=4*demand['estimate']['bar_pages_estimate'])
    jobs=quote_jobs(demand);return q.prepare(root,jobs,parent=parent,max_total_requests=20*len(jobs))
