"""Candidate selection v2: census-dated existence and SPY/QQQ weekly targets 2/4.

Successor of `exact_windows.run` candidate selection (left unchanged). Existence comes from the
daily-bar census (usable from the session after first trade) instead of earlier bounded captures.
"""
from collections import Counter,defaultdict
from datetime import date
import json
from pathlib import Path
import time

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from nn_meta.etfe import acquisition as a,dated_policy as d,exact_windows as e,existence_census as x,window_demand as w

SIGNALS=a.ROOT/'nn_meta/validation/etfe-window-demand-20261006-r0'
CENSUS=a.ROOT/'nn_meta/data_cache_etfe/alpaca-fresh-existence-20261006-r0'
BASE_TARGETS=(0,1,5)
WEEKLY_TARGETS={'SPY':(2,4),'QQQ':(2,4)}  # user-admitted 2026-10-06; VOO lacks M/W expiries


def targets(ticker):
    return BASE_TARGETS+WEEKLY_TARGETS.get(ticker,())


def availability():
    days=[day for day,_ in d.read_calendar()]
    return x.available_from(x.first_traded(CENSUS),days)


def contract_index(avail):
    """(ticker, right, expiry) -> [(strike, symbol, available_from)] sorted by strike then symbol."""
    import pyarrow.parquet as pq_
    c=pq_.read_table(d.ROOT/'nn_meta/validation/etfe-dated-policy-20261006-r0/CONTRACTS.parquet',
        columns=['symbol','underlying','expiration_date','right','strike','status']).to_pylist()
    index=defaultdict(list)
    for r in c:
        if r['status']=='admitted' and avail.get(r['symbol']) is not None:
            index[r['underlying'],r['right'],r['expiration_date']].append((r['strike'],r['symbol'],avail[r['symbol']]))
    return {k:sorted(v) for k,v in index.items()}


def choices(index,ticker,day,right):
    """Same shape as exact_windows.choices: expiry -> sorted [(strike, symbol)] usable on `day`."""
    out={}
    for offset in range(6):
        exp=date.fromordinal(day.toordinal()+offset)
        rows=[(k,s) for k,s,f in index.get((ticker,right,exp),()) if f<=day]
        if rows:out[exp]=rows
    return out


def run(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=False);started=time.monotonic()
    plan=w.load(SIGNALS);index=contract_index(availability());summary={}
    for scope in plan['scopes']:
        ticker,m=scope['ticker'],scope['minutes'];tag=f'{ticker}-{m}'
        chart,count=e.weights(SIGNALS,tag);cache={};counts=Counter();records=[];writer=None;path=root/(tag+'.parquet')
        for channel,right in ((0,'call'),(2,'put')):
            for i in np.flatnonzero(count[:,channel]):
                bar=chart.iloc[i];at=bar.bar_end.value;day=date.fromisoformat(bar.session_date);spot=float(bar.Close)
                if (day,right) not in cache:cache[day,right]=choices(index,ticker,day,right)
                windows=w.reference_windows(at,m,bar.session_open.value,bar.session_close.value)
                weight=int(count[i,channel]);counts['signal_memberships']+=weight
                for target in targets(ticker):
                    symbol=e.nearest(cache[day,right],day,target,spot) if cache[day,right] else None
                    reason='selected' if symbol else 'no_available_contract'
                    counts[reason]+=1;counts[reason+'_memberships']+=weight;counts['decision_clocks']+=1
                    records.append(dict(ticker=ticker,minutes=m,chart_row=int(i),signal_at_ns=at,session_date=day,right=right,
                        target_dte=target,logical_memberships=weight,raw_spot=spot,candidate=symbol or '',reason=reason,
                        feature_start_ns=windows['feature'][0] if windows['feature'] else -1,
                        feature_end_ns=windows['feature'][1] if windows['feature'] else -1,
                        entry_start_ns=windows['entry'][0],entry_end_ns=windows['entry'][1]))
                    if len(records)>=20000:
                        t=pa.Table.from_pylist(records)
                        if writer is None:writer=pq.ParquetWriter(path,t.schema,compression='zstd')
                        writer.write_table(t);records=[]
        if records:
            t=pa.Table.from_pylist(records)
            if writer is None:writer=pq.ParquetWriter(path,t.schema,compression='zstd')
            writer.write_table(t)
        writer.close()
        summary[tag]=dict(data=path.name,data_sha256=a.sha(path.read_bytes()),counts=dict(counts))
        print(json.dumps(dict(scope=tag,counts=dict(counts))),flush=True)
    total=Counter()
    for v in summary.values():total.update(v['counts'])
    result=dict(schema='etfe-selection-v2',signals_plan_sha256=plan['sha256'],
        census_plan_sha256=json.loads((CENSUS/'PLAN.json').read_text())['sha256'],
        targets={t:list(targets(t)) for t in ('SPY','QQQ','VOO')},scopes=summary,totals=dict(total),
        selected_fraction=total['selected']/total['decision_clocks'],elapsed_seconds=time.monotonic()-started,
        holding_paths_realized=0,ready_for_build=False,ready_for_training=False)
    a.save(root/'SELECTION.json',result)
    return result
