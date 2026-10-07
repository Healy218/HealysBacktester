"""Build isolated-path labels for every selection-v2 decision-clock row (label kernel v1)."""
from collections import defaultdict
import datetime as dt
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from nn_meta.etfe import dated_policy as d,label_kernel as k,option_minute_capture as m,selection_v2 as s,stock_quote_capture_v2 as q

ROOT=Path(__file__).resolve().parents[2]
CACHE=ROOT/'nn_meta/data_cache_etfe'
BARS_RAW=CACHE/'alpaca-fresh-envelope-bars-20261006-r0';BARS=CACHE/'normalized-20261006-envelope-bars-r0'
QUOTES_RAW=CACHE/'alpaca-fresh-envelope-quotes-20261006-r0';QUOTES=CACHE/'normalized-20261006-envelope-quotes-r0'
SELECTION=ROOT/'nn_meta/validation/etfe-selection-v2-20261006-r0'
REFERENCES=ROOT/'nn_meta/validation/etfe-exercise-references-20261006-r0/REFERENCES.parquet'


def ns(stamp):
    return pd.Timestamp(stamp).value


def market(ticker):
    cal=json.loads(d.SOURCES['calendar'].joinpath('000-calendar.body').read_bytes())
    sessions={dt.date.fromisoformat(r['date']):(ns(pd.Timestamp(f"{r['date']} {r['open']}",tz='America/New_York')),
              ns(pd.Timestamp(f"{r['date']} {r['close']}",tz='America/New_York'))) for r in cal}
    equity={dt.date.fromisoformat(r['date']):dt.date.fromisoformat(r['settlement_date']) for r in cal}
    days=sorted(sessions);hol=set().union(*(d.bank_holidays(y) for y in {x.year for x in days}))
    avail=s.availability();contracts={};by_expiry=defaultdict(list)
    for r in pq.read_table(d.ROOT/'nn_meta/validation/etfe-dated-policy-20261006-r0/CONTRACTS.parquet',
            columns=['symbol','underlying','expiration_date','right','strike','status']).to_pylist():
        if r['status']!='admitted' or r['underlying']!=ticker:continue
        contracts[r['symbol']]=(ticker,r['right'],r['expiration_date'],r['strike'],avail.get(r['symbol']))
        if avail.get(r['symbol']) is not None:by_expiry[ticker,r['right'],r['expiration_date']].append((r['strike'],r['symbol']))
    bars={};plan=m.load_plan(BARS_RAW);windows={}
    for job in plan['jobs']:
        lo,hi=ns(job['params']['start']),ns(job['params']['end'])+1
        for sym in job['params']['symbols'].split(','):
            if sym.startswith(ticker):windows[sym]=(lo,hi)
    seal=json.loads((BARS/'NORMALIZED.json').read_text());tables=[]
    for key in seal['partition_receipts']:
        meta=json.loads((BARS/'partitions'/(key+'.json')).read_text())
        t=pq.read_table(BARS/meta['data'],columns=['symbol','timestamp_ns','vwap','volume','trade_count'])
        t=t.filter(pc.starts_with(t['symbol'],ticker))
        if t.num_rows:tables.append(t)
    t=pa.concat_tables(tables).to_pandas().sort_values(['symbol','timestamp_ns'],kind='stable')
    if t.duplicated(['symbol','timestamp_ns']).any():raise ValueError('Duplicate bar vintage')
    for sym,g in t.groupby('symbol',sort=False):
        lo,hi=windows[sym]
        bars[sym]=k.Bars(g.timestamp_ns.to_numpy(np.int64),g.vwap.to_numpy(float),g.volume.to_numpy(np.int64),
                        g.trade_count.to_numpy(np.int64),lo,hi)
    for sym,(lo,hi) in windows.items():
        if sym not in bars:bars[sym]=k.Bars(*(np.array([],dtype=x) for x in (np.int64,float,np.int64,np.int64)),lo,hi)
    qplan=q.load_plan(QUOTES_RAW)
    qwin=sorted((ns(j['params']['start']),ns(j['params']['end'])+1) for j in qplan['jobs'] if j['params']['symbols']==ticker)
    qseal=json.loads((QUOTES/'NORMALIZED.json').read_text());tables=[]
    for key in qseal['partition_receipts']:
        meta=json.loads((QUOTES/'partitions'/(key+'.json')).read_text())
        tq=pq.read_table(QUOTES/meta['data'],columns=['symbol','timestamp_ns','bid','ask','bid_size_raw','ask_size_raw'])
        tq=tq.filter(pc.equal(tq['symbol'],ticker))
        if tq.num_rows:tables.append(tq)
    tq=pa.concat_tables(tables).to_pandas().sort_values('timestamp_ns',kind='stable')
    quotes={ticker:k.Quotes(tq.timestamp_ns.to_numpy(np.int64),tq.bid.to_numpy(float),tq.ask.to_numpy(float),
        tq.bid_size_raw.to_numpy(np.int64),tq.ask_size_raw.to_numpy(np.int64),qwin)}
    refs={}
    for r in pq.read_table(REFERENCES).to_pylist():
        if r['symbol']==ticker:refs[ticker,r['session_date']]=r['reference']
    return k.Market(bars=bars,quotes=quotes,contracts=contracts,by_expiry={x:sorted(v) for x,v in by_expiry.items()},
        sessions=sessions,equity_settle=equity,settle_days=[x for x in days if x not in hol],references=refs,weekly={'SPY','QQQ'},
        expiry_overrides=EXPIRY_OVERRIDES)


def earliest_exits(tag):
    """Per chart row: earliest exit bar end (ns) among variants entering there, for calls and puts."""
    folder=s.SIGNALS/tag;chart=pq.read_table(folder/'chart.parquet',columns=['bar_end']).to_pandas()
    ends=chart.bar_end.astype('int64').to_numpy();n=len(ends);out={'call':np.full(n,-1,np.int64),'put':np.full(n,-1,np.int64)}
    best={'call':np.full(n,np.iinfo(np.int64).max,np.int64),'put':np.full(n,np.iinfo(np.int64).max,np.int64)}
    for path in sorted(folder.glob('*.npz')):
        if path.name.endswith('-union.npz'):continue
        with np.load(path,allow_pickle=False) as z:
            rows=int(z['rows'][0]);bits=np.unpackbits(z['packed'],axis=0,count=rows)
        if rows>n:raise ValueError('Packed rows exceed chart')  # packed prefix covers calculated bins only
        for v in range(bits.shape[2]):
            for right,(ein,eout) in (('call',(0,1)),('put',(2,3))):
                entries=np.flatnonzero(bits[:,ein,v]);exits=np.flatnonzero(bits[:,eout,v])
                if not len(entries) or not len(exits):continue
                j=np.searchsorted(exits,entries,side='right');ok=j<len(exits)
                np.minimum.at(best[right],entries[ok],exits[j[ok]])
    for right in out:
        has=best[right]<np.iinfo(np.int64).max;out[right][has]=ends[best[right][has]]
    return out


# OCC: options listed to expire 2025-01-09 (national day of mourning, markets closed) expired on
# 2025-01-08 closing prices; announced by 2025-01-02, before any 0-5 DTE entry into them.
EXPIRY_OVERRIDES={dt.date(2025,1,9):dt.date(2025,1,8)}


COLUMNS=['ticker','minutes','chart_row','signal_at_ns','session_date','right','target_dte','logical_memberships','candidate']


def run_ticker(ticker,out,policy=None):
    out=Path(out);started=time.monotonic();mk=market(ticker);kernel=k.Kernel(mk,policy);summary={}
    for path in sorted(SELECTION.glob(f'{ticker}-*.parquet')):
        tag=path.stem;exits=earliest_exits(tag);cache={};records=[];counts=defaultdict(int)
        t=pq.read_table(path,columns=COLUMNS).to_pandas();t=t[t.candidate!='']
        for r in t.itertuples(index=False):
            x=int(exits[r.right][r.chart_row]);x=None if x<0 else x
            key=(r.candidate,r.signal_at_ns,x,r.target_dte)
            if key not in cache:cache[key]=kernel.run(r.candidate,int(r.signal_at_ns),x,int(r.target_dte))
            p=cache[key];counts[p.status]+=1
            records.append(dict(ticker=ticker,minutes=r.minutes,chart_row=r.chart_row,signal_at_ns=r.signal_at_ns,right=r.right,
                target_dte=r.target_dte,contract=r.candidate,logical_memberships=r.logical_memberships,exit_signal_ns=x if x is not None else -1,
                status=p.status,reason=p.reason,debit_cents=p.debit,pnl_cents=p.pnl,quantity=p.quantity,entry_vwap=p.entry_vwap,
                exit_kind=p.exit_kind,terminal_ns=p.terminal_ns,rolls=p.rolls,pin=p.pin))
        table=pa.Table.from_pylist(records);dest=out/f'{tag}.parquet';pq.write_table(table,dest,compression='zstd')
        summary[tag]=dict(rows=len(records),unique_paths=len(cache),status=dict(counts),data_sha256=m.sha(dest.read_bytes()))
        print(json.dumps(dict(scope=tag,**summary[tag])),flush=True)
    return dict(ticker=ticker,scopes=summary,elapsed_seconds=time.monotonic()-started)


def stress_profiles():
    """The reference's 27 declared profiles (integration_ledger.stress_profiles), unchanged."""
    from nn_meta.etfe.integration_ledger import stress_profiles as reference
    return reference()


def stressed_bars(mk,policy):
    """Chronological bar removal per contract/session, mirroring integration_ledger.stressed_bars."""
    if not policy.get('remove_every_tenth') and not policy.get('remove_edge_blocks'):return mk.bars
    dates=sorted(mk.sessions);opens=np.array([mk.sessions[x][0] for x in dates]);closes=np.array([mk.sessions[x][1] for x in dates])
    out={}
    for sym,b in mk.bars.items():
        if not len(b.start):out[sym]=b;continue
        j=np.searchsorted(opens,b.start,side='right')-1;inside=(j>=0)&(b.start<closes[np.maximum(j,0)])
        keep=inside.copy()
        eligible=inside&(b.vwap>0)&(b.volume>0)&(b.count>0)
        if policy.get('remove_every_tenth'):
            rank=pd.Series(eligible.astype(int)).groupby(j).cumsum().to_numpy()
            keep&=~(eligible&(rank%10==0))
        for side,block in policy.get('remove_edge_blocks',[]):
            anchor=opens[np.maximum(j,0)]+5*block*k.MINUTE if side=='first' else closes[np.maximum(j,0)]-(30-5*block)*k.MINUTE
            keep&=~((b.start>=anchor)&(b.start<anchor+5*k.MINUTE))
        out[sym]=k.Bars(b.start[keep],b.vwap[keep],b.volume[keep],b.count[keep],b.lo,b.hi)
    return out


def run_stress(ticker,out,names=None):
    """All declared profiles for one ticker; minimal per-row outcome columns per profile."""
    out=Path(out);base=market(ticker);profiles=stress_profiles();summary={}
    for name,policy in profiles.items():
        if names and name not in names:continue
        started=time.monotonic();mk=k.Market(**{**base.__dict__,'bars':stressed_bars(base,policy)})
        kern=k.Kernel(mk,{x:v for x,v in policy.items() if x not in ('remove_every_tenth','remove_edge_blocks')})
        dest=out/name;dest.mkdir(parents=True,exist_ok=True);counts=defaultdict(int);pnl=0;debit=0
        for path in sorted(SELECTION.glob(f'{ticker}-*.parquet')):
            tag=path.stem;exits=earliest_exits(tag);rows=[]
            t=pq.read_table(path,columns=COLUMNS).to_pandas();t=t[t.candidate!='']
            for r in t.itertuples(index=False):
                x=int(exits[r.right][r.chart_row]);x=None if x<0 else x
                p=kern.run(r.candidate,int(r.signal_at_ns),x,int(r.target_dte));counts[p.status]+=1
                if p.status=='settled':pnl+=p.pnl;debit+=p.debit
                rows.append((r.chart_row,r.signal_at_ns,r.right,r.target_dte,p.status,p.debit,p.pnl))
            pq.write_table(pa.Table.from_pylist([dict(chart_row=a,signal_at_ns=b_,right=c,target_dte=d_,status=e,debit_cents=f,pnl_cents=g)
                for a,b_,c,d_,e,f,g in rows]),dest/f'{tag}.parquet',compression='zstd')
        summary[name]=dict(policy=policy,status=dict(counts),settled_pnl_cents=pnl,settled_debit_cents=debit,
            elapsed_seconds=time.monotonic()-started)
        print(json.dumps(dict(ticker=ticker,profile=name,status=dict(counts),pooled_R=pnl/debit if debit else None)),flush=True)
    return summary
