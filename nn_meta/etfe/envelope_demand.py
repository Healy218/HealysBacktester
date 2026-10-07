"""Envelope path demand: every observation an isolated ETFE label path could need.

User-selected 2026-10-06 instead of an iterative ledger frontier. From selection v2 it derives:
A  held-contract 1-minute option bars, earliest feature/entry window through expiry close;
A' option trades over feature windows (trade features);
B  roll legs chosen at every expiry-session cutoff (close - 15 min) per underlying/right/target,
   bars from cutoff through their expiry close;
C  SIP stock quotes in the 30 s before each expiry cutoff (ITM classification);
D  SIP stock quotes in the first minute of each exercise settlement session (stock liquidation).
Requests group contracts sharing an expiry (<=100 symbols) over the group's widest window.
Daily-bar census trade counts bound bar rows: sum(min(390, n)) per contract-session.
"""
from collections import defaultdict
from datetime import date,timedelta
import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from nn_meta.etfe import dated_policy as d,existence_census as x,option_daily_capture as o,selection_v2 as s
from nn_meta.etfe.causal_inputs import stock_minutes
from nn_meta.etfe.causal_pilot import STOCK

CUTOFF=pd.Timedelta(minutes=15)
ITM_WINDOW=pd.Timedelta(seconds=30)
LIQUIDATION_WINDOW=pd.Timedelta(minutes=1)
END=pd.Timestamp('2026-10-02 16:00',tz='America/New_York')


def closes():
    body=json.loads(x.CALENDAR.read_bytes())
    return {date.fromisoformat(r['date']):(pd.Timestamp(f"{r['date']} {r['open']}",tz='America/New_York'),
            pd.Timestamp(f"{r['date']} {r['close']}",tz='America/New_York')) for r in body}


def spot_before(minutes,at):
    """Close of the newest completed regular SIP minute bar ending at or before `at`."""
    i=minutes.index.searchsorted(at-pd.Timedelta(minutes=1),side='right')-1
    return None if i<0 else float(minutes.Close.iloc[i])


def build(selection_root,out):
    selection_root,out=Path(selection_root),Path(out);out.mkdir(parents=True,exist_ok=False)
    sessions=closes();settle=dict(d.read_calendar());index=s.contract_index(s.availability())
    meta={sym:(t,r,e) for (t,r,e),rows in index.items() for _,sym,_ in rows}
    bars=defaultdict(lambda:[None,None]);trades=defaultdict(list);expiries=defaultdict(set)
    for path in sorted(selection_root.glob('*-*.parquet')):
        for b in pq.ParquetFile(path).iter_batches(batch_size=50000,columns=['candidate','feature_start_ns','feature_end_ns','entry_start_ns']):
            t=b.to_pandas();t=t[t.candidate!='']
            t['start']=t.feature_start_ns.where(t.feature_start_ns>=0,t.entry_start_ns)
            for sym,g in t.groupby('candidate'):
                lo=int(g.start.min());cur=bars[sym][0];bars[sym][0]=lo if cur is None else min(cur,lo)
                f=g[g.feature_start_ns>=0]
                trades[sym].extend(zip(f.feature_start_ns.tolist(),f.feature_end_ns.tolist()))
    for sym in bars:
        ticker,_,exp=meta[sym];expiries[ticker].add(exp)
    # B: roll legs at every session cutoff where the underlying has any expiring held contract.
    rolls=0;spots={t:stock_minutes(STOCK,t) for t in ('SPY','QQQ','VOO')};frontier=[(t,e) for t in expiries for e in expiries[t]];seen=set()
    while frontier:
        ticker,day=frontier.pop()
        if (ticker,day) in seen or day not in sessions:continue
        seen.add((ticker,day));cutoff=sessions[day][1]-CUTOFF
        if cutoff>END:continue
        spot=spot_before(spots[ticker],cutoff.tz_convert('UTC'))
        if spot is None:continue
        for right in ('call','put'):
            groups={e:v for e,v in s.choices(index,ticker,day,right).items() if e>day}  # roll needs a later expiry
            for target in s.targets(ticker):
                sym=s.e.nearest(groups,day,target,spot) if groups else None
                if not sym:continue
                rolls+=1;cur=bars[sym][0];at=int(cutoff.tz_convert('UTC').value)
                bars[sym][0]=at if cur is None else min(cur,at)
                exp=meta[sym][2];expiries[ticker].add(exp);frontier.append((ticker,exp))
    # Close every bar window at its expiry close (or the fixed end).
    for sym,v in bars.items():
        exp=meta[sym][2];v[1]=int(min(sessions[exp][1] if exp in sessions else END,END).tz_convert('UTC').value)
    quotes_itm=[];quotes_liq=[]
    for ticker,exps in expiries.items():
        for e in sorted(exps):
            if e not in sessions:continue
            cutoff=sessions[e][1]-CUTOFF
            if cutoff<=END:quotes_itm.append((ticker,(cutoff-ITM_WINDOW).isoformat(),cutoff.isoformat()))
            st=settle.get(e)
            if st in sessions and sessions[st][0]<=END:
                quotes_liq.append((ticker,sessions[st][0].isoformat(),(sessions[st][0]+LIQUIDATION_WINDOW).isoformat()))
    return dict(bars=dict(bars),trades=dict(trades),rolls=rolls,meta=meta,quotes_itm=quotes_itm,quotes_liq=quotes_liq)


def freeze(selection_root,out):
    """Persist the envelope (bars, quote windows, contract metadata) as a hash-bound artifact."""
    out=Path(out);dm=build(selection_root,out);est=estimate(dm)
    value=dict(schema='etfe-envelope-demand-v1',selection=json.loads((Path(selection_root)/'SELECTION.json').read_text())['schema'],
        selection_sha256=o.sha((Path(selection_root)/'SELECTION.json').read_bytes()),
        rules=dict(cutoff_minutes_before_close=15,roll_requires_later_expiry=True,itm_window_seconds=30,
            liquidation_window_seconds=60,option_trades='not captured; bars-only first run (user 2026-10-06)'),
        bars={k:list(v) for k,v in sorted(dm['bars'].items())},meta={k:[t,r,e.isoformat()] for k,(t,r,e) in sorted(dm['meta'].items()) if k in dm['bars']},
        quotes_itm=dm['quotes_itm'],quotes_liq=dm['quotes_liq'],estimate=est)
    o.save(out/'DEMAND.json',value)
    return est


def estimate(demand):
    """Bar rows bounded by census daily trade counts; requests grouped by expiry, 100 symbols each."""
    counts=defaultdict(dict)
    for item in o.load_plan(s.CENSUS)['jobs']:
        for _,body,_ in o.committed(s.CENSUS,item)[0]:
            for sym,row in o.rows(body,item):
                counts[sym][pd.Timestamp(row['t']).tz_convert('America/New_York').date()]=row['n']
    rows=0;groups=defaultdict(list)
    for sym,(lo,hi) in demand['bars'].items():
        a=pd.Timestamp(lo,tz='UTC').tz_convert('America/New_York').date();b=pd.Timestamp(hi,tz='UTC').tz_convert('America/New_York').date()
        rows+=sum(min(390,n) for day,n in counts.get(sym,{}).items() if a<=day<=b)
        t,_,e=demand['meta'][sym];groups[t,e].append(sym)
    requests=sum((len(v)+99)//100 for v in groups.values())
    return dict(contracts=len(demand['bars']),bar_rows_upper=rows,bar_requests_min=requests,
        bar_pages_estimate=requests+rows//10000,trade_windows=sum(len(v) for v in demand['trades'].values()),
        roll_legs=demand['rolls'],itm_quote_windows=len(demand['quotes_itm']),liquidation_quote_windows=len(demand['quotes_liq']))
