"""Bounded trade capture derived exactly from audited ETFE component demand."""
from collections import defaultdict
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from nn_meta.etfe.acquisition import ROOT,sha,digest,save,write_new,job,prepare,load_plan,capture,guard,audit
from nn_meta.etfe.causal_pilot import verify as verify_pilot,OPTIONS
from nn_meta.etfe.causal_inputs import normalized_partitions

SOURCES=('nn_meta/etfe/trade_demand.py','scripts/capture_etfe_trade_demand.py',
         'docs/specs/ETFE_TRADE_CAPTURE_20261004.md')


def jobs_from_demand(demand):
    groups=defaultdict(list);edges=[];seen=set()
    for entry in demand['physical']:
        if entry['route']!='option_trades':continue
        for a,b in entry['uncaptured_intervals']:
            if not isinstance(a,int) or not isinstance(b,int) or a>=b or a%60_000_000_000 or b%60_000_000_000:
                raise ValueError('Aligned nonempty half-open minute demand required')
            if not any(x<=a<b<=y for x,y in entry['intervals']):raise ValueError('Uncaptured window outside demand')
            key=(entry['symbol'],a,b)
            if key in seen:raise ValueError('Duplicate demand edge')
            seen.add(key);groups[(a,b)].append(entry['symbol'])
    by_symbol=defaultdict(list)
    for s,a,b in seen:by_symbol[s].append((a,b))
    for intervals in by_symbol.values():
        ordered=sorted(intervals)
        if any(a<previous[1] for previous,(a,b) in zip(ordered,ordered[1:])):
            raise ValueError('Overlapping demand edges require prior union')
    jobs=[]
    for (a,b),symbols in sorted(groups.items()):
        for offset in range(0,len(symbols),100):
            batch=sorted(symbols)[offset:offset+100]
            item=job('option_trades',dict(symbols=','.join(batch),sort='asc',limit=10000,
                start=pd.Timestamp(a,tz='UTC').isoformat(),end=pd.Timestamp(b-1,tz='UTC').isoformat()),
                f'phase_B_trade_demand:{a}:{b}:{offset}')
            jobs.append(item)
            edges.extend(dict(symbol=s,start_ns=a,end_exclusive_ns=b,job_id=item['id']) for s in batch)
    if not jobs:raise ValueError('No uncaptured trade demand')
    return jobs,edges


def preflight(edges):
    densities=[];raw_bytes=0;rows=0
    for root in OPTIONS[:2]:
        for _,path in normalized_partitions(root,'option_trades'):
            frame=pq.read_table(path,columns=['symbol','timestamp_ns','raw_json']).to_pandas()
            if frame.empty:continue
            densities.extend(frame.groupby(['symbol',frame.timestamp_ns//60_000_000_000]).size().tolist())
            rows+=len(frame);raw_bytes+=frame.raw_json.str.len().sum()
    minutes=sum((e['end_exclusive_ns']-e['start_ns'])//60_000_000_000 for e in edges)
    if not densities:raise ValueError('Measured fresh trade sample required')
    bytes_per_row=float(raw_bytes/rows)
    return dict(prior_sample_rows=rows,prior_observed_contract_minutes=len(densities),
        sample_raw_row_bytes=bytes_per_row,requested_contract_minutes=minutes,
        density_quantiles={str(q):float(np.quantile(densities,q)) for q in (.5,.95,1.)},
        estimated_raw_bytes={str(q):int(minutes*np.quantile(densities,q)*bytes_per_row*1.5) for q in (.5,.95,1.)},
        forecast_is_not_coverage_or_completion_guarantee=True)


def prepare_trade_capture(root,pilot):
    pilot=Path(pilot).resolve();p=verify_pilot(pilot)
    a=json.loads((pilot/'INDEPENDENT_AUDIT.json').read_text());d=json.loads((pilot/'GLOBAL_DEMAND.json').read_text())
    if (a['plan_sha256']!=p['sha256'] or a['global_demand_sha256']!=sha((pilot/'GLOBAL_DEMAND.json').read_bytes())
        or a['complete_sha256']!=sha((pilot/'COMPLETE.json').read_bytes())
        or not a['logical_to_physical_reconciliation'] or not a['hashes_verified']):raise ValueError('Audited demand required')
    jobs,edges=jobs_from_demand(d)
    if len(edges)!=225 or len(jobs)!=103:raise ValueError('This bounded study requires the declared 225-edge inventory')
    parent=dict(kind='etfe-phase-B-trade-capture-v1',pilot=str(pilot),pilot_plan_sha256=p['sha256'],
        bindings={n:sha((pilot/n).read_bytes()) for n in ('PLAN.json','COMPLETE.json','GLOBAL_DEMAND.json','INDEPENDENT_AUDIT.json')},
        sources={n:sha((ROOT/n).read_bytes()) for n in SOURCES},edges=edges,preflight=preflight(edges),
        study_limits=dict(max_requests=512,max_active_seconds=1800,max_invocations=8),
        ready_for_build=False,ready_for_training=False)
    plan=prepare(root,jobs,parent=parent)
    for n in SOURCES:
        target=Path(root)/'trade_source'/n;target.parent.mkdir(parents=True,exist_ok=True)
        write_new(target,(ROOT/n).read_bytes())
    return plan


def verify(root):
    root=Path(root);plan=load_plan(root);parent=plan['parent']
    if parent['kind']!='etfe-phase-B-trade-capture-v1':raise ValueError('Trade study required')
    for n,h in parent['sources'].items():
        if sha((ROOT/n).read_bytes())!=h or sha((root/'trade_source'/n).read_bytes())!=h:raise ValueError('Trade source drift')
    pilot=Path(parent['pilot'])
    for n,h in parent['bindings'].items():
        if sha((pilot/n).read_bytes())!=h:raise ValueError('Demand binding drift')
    if verify_pilot(pilot)['sha256']!=parent['pilot_plan_sha256']:raise ValueError('Pilot drift')
    jobs,edges=jobs_from_demand(json.loads((pilot/'GLOBAL_DEMAND.json').read_text()))
    if jobs!=plan['jobs'] or edges!=parent['edges']:raise ValueError('Demand identity drift')
    return plan


def run(root,http,request_budget=None):
    import fcntl
    root=Path(root);plan=verify(root)
    with (root/'study.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        runs=[json.loads(p.read_text()) for p in (root/'runs').glob('*.json')]
        limits=plan['parent']['study_limits'];used=sum(r['requests_this_run'] for r in runs)
        active=sum(r['elapsed_seconds'] for r in runs)
        if len(runs)>=limits['max_invocations'] or used>=limits['max_requests'] or active>=limits['max_active_seconds']:
            raise ValueError('Trade study budget exhausted; no automatic extension')
        remaining=limits['max_requests']-used;started=time.monotonic()
        def checked_resources(path,resource_limits):
            if active+time.monotonic()-started>=limits['max_active_seconds']:raise RuntimeError('study_active_time_budget')
            guard(path,resource_limits)
        return capture(root,http,request_budget=min(request_budget if request_budget is not None else 128,remaining),
                       check_resources=checked_resources)


def report(root):
    plan=verify(root);result=audit(root)
    if not result['capture_complete']:raise ValueError('Trade capture incomplete')
    result.update(demand_edges=len(plan['parent']['edges']),demand_sha256=plan['parent']['bindings']['GLOBAL_DEMAND.json'],
                  empty_response_is_not_no_trade=True)
    save(Path(root)/'COVERAGE.json',result)
    return result
