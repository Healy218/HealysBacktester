"""Frozen bounded materialization of diagnostic ETFE option features."""
from collections import Counter,defaultdict
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import time
import uuid

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from nn_meta.etfe.acquisition import ROOT,digest,save,sha,write_new,resources
from nn_meta.etfe.causal_pilot import verify as verify_pilot
from nn_meta.etfe.trade_demand import verify as verify_capture
from nn_meta.etfe.normalization import load_normalization
from nn_meta.etfe.option_features import compute_window,NAMES,MINUTE

PILOT=ROOT/'nn_meta/validation/etfe-causal-20261004-r0'
RAW=ROOT/'nn_meta/data_cache_etfe/alpaca-fresh-20261004-trade-windows-r0'
NORMAL=ROOT/'nn_meta/data_cache_etfe/normalized-20261004-trade-windows-r0'
SOURCES=('nn_meta/etfe/option_features.py','nn_meta/etfe/option_feature_pilot.py',
 'scripts/pilot_etfe_option_features.py','docs/specs/ETFE_OPTION_FEATURE_PILOT_20261004.md',
 'docs/specs/ETFE_FEATURE_MAP_20261003.json','docs/specs/ETFE_FEATURES_20261003.md')


def prepare(root):
    verify_pilot(PILOT);verify_capture(RAW);load_normalization(NORMAL)
    audit=json.loads((NORMAL/'DEMAND_AUDIT.json').read_text())
    if not audit['all_edges_captured'] or not audit['all_rows_within_half_open_demand']:raise ValueError('Audited complete trade transport required')
    registry=json.loads((ROOT/'docs/specs/ETFE_FEATURE_MAP_20261003.json').read_text())
    if [r['name'] for r in registry['fields'] if r['inherited_name'].startswith('opt_tick_')]!=NAMES:raise ValueError('Registered field order changed')
    paths=[NORMAL/n for n in ('PLAN.json','NORMALIZED.json','INDEPENDENT_AUDIT.json','DEMAND_AUDIT.json','DEMANDED_MINUTES.parquet')]
    paths += [PILOT/'COMPLETE.json',PILOT/'GLOBAL_DEMAND.json',PILOT/'INDEPENDENT_AUDIT.json']
    scopes=[];complete=json.loads((PILOT/'COMPLETE.json').read_text())
    for name,h in complete['scope_receipts'].items():
        path=PILOT/name
        if sha(path.read_bytes())!=h:raise ValueError('Scope receipt drift')
        r=json.loads(path.read_text());events=r['files'][1]
        if sha((PILOT/events['path']).read_bytes())!=events['sha256']:raise ValueError('Event payload drift')
        scopes.append(dict(**r['scope'],events=events));paths += [path,PILOT/events['path']]
    for entry in audit['normalized_inputs']+audit['bar_inputs']:
        p=ROOT/entry['path']
        if sha(p.read_bytes())!=entry['sha256']:raise ValueError('Market input drift')
        paths.append(p)
    plan=dict(schema='etfe-option-feature-component-plan-v1',sources={n:sha((ROOT/n).read_bytes()) for n in SOURCES},
        inputs={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in paths},scopes=scopes,fields=NAMES,
        packages={p:importlib.metadata.version(p) for p in ('numpy','pandas','pyarrow')},
        limits=dict(max_root_bytes=2**30,max_run_seconds=1800),model_feature_admitted=False,ready_for_training=False)
    plan['sha256']=digest(plan);root=Path(root);root.mkdir(parents=True,exist_ok=False);save(root/'PLAN.json',plan)
    for n in SOURCES:
        p=root/'source'/n;p.parent.mkdir(parents=True,exist_ok=True);write_new(p,(ROOT/n).read_bytes())
    return plan


def verify(root):
    root=Path(root);p=json.loads((root/'PLAN.json').read_text())
    if digest({k:v for k,v in p.items() if k!='sha256'})!=p['sha256']:raise ValueError('Plan drift')
    for n,h in p['sources'].items():
        if sha((ROOT/n).read_bytes())!=h or sha((root/'source'/n).read_bytes())!=h:raise ValueError('Component source drift')
    for n,h in p['inputs'].items():
        if sha((ROOT/n).read_bytes())!=h:raise ValueError('Component input drift')
    if any(importlib.metadata.version(n)!=v for n,v in p['packages'].items()):raise ValueError('Package drift')
    verify_pilot(PILOT);verify_capture(RAW);load_normalization(NORMAL)
    return p


def market_inputs():
    a=json.loads((NORMAL/'DEMAND_AUDIT.json').read_text());grid=pd.read_parquet(NORMAL/'DEMANDED_MINUTES.parquet')
    coverage={(r.symbol,int(r.minute_open_ns)):dict(trade_transport_complete=True,bar_transport_complete=True) for r in grid.itertuples()}
    trades=defaultdict(list);bars=defaultdict(list)
    for entries,target in ((a['normalized_inputs'],trades),(a['bar_inputs'],bars)):
        for f in entries:
            path=ROOT/f['path']
            if sha(path.read_bytes())!=f['sha256']:raise ValueError('Market hash drift')
            for batch in pq.ParquetFile(path).iter_batches(batch_size=5000):
                for r in batch.to_pylist():
                    key=(r['symbol'],r['timestamp_ns']//MINUTE*MINUTE)
                    if key in coverage:target[key].append(r)
    return coverage,trades,bars


def guard(root,plan,started):
    if time.monotonic()-started>plan['limits']['max_run_seconds']:raise RuntimeError('Component time budget')
    r=resources(root)
    if r['disk_free']<max(100*2**30,.2*r['disk_total'])+256*2**20:raise RuntimeError('Disk reserve')
    if r['ram_available']<max(2*2**30,.2*r['ram_total'])+256*2**20:raise RuntimeError('RAM reserve')
    if sum(p.stat().st_size for p in root.rglob('*') if p.is_file())+64*2**20>plan['limits']['max_root_bytes']:raise RuntimeError('Root budget')


def save_frame(root,name,frame):
    path=root/name
    if path.exists():raise ValueError('No overwrite')
    frame.to_parquet(path,index=False)
    with path.open('rb') as f:os.fsync(f.fileno())
    return dict(path=name,rows=len(frame),sha256=sha(path.read_bytes()))


def run_scope(root,scope,plan,market,started):
    coverage,trades,bars=market;events=pd.read_parquet(PILOT/scope['events']['path']);m=scope['minutes'];tag=f"{scope['ticker']}-{m}"
    unique=events[events.acquisition_candidate.notna()].drop_duplicates(['acquisition_candidate','signal_at_ns'])
    windows=[];lookup={}
    for i,e in enumerate(unique.itertuples()):
        if i%100==0:guard(root,plan,started)
        s=e.acquisition_candidate;at=pd.Timestamp(e.signal_at_ns,tz='UTC');a=e.feature_start_ns;b=e.feature_end_ns
        if a!=at.value-(m+1)*MINUTE or b!=at.value-MINUTE:raise ValueError('Event window changed')
        key=(s,e.signal_at_ns);wid=digest([s,e.signal_at_ns,m]);lookup[key]=wid
        row=dict(window_id=wid,symbol=s,signal_at_ns=e.signal_at_ns,minutes=m,feature_start_ns=a,feature_end_ns=b,
                 inside_stock_session=e.feature_inside_stock_session,model_feature_admitted=False)
        if e.feature_inside_stock_session:
            tr=[x for t in range(a,b,MINUTE) for x in trades.get((s,t),[])];br=[x for t in range(a,b,MINUTE) for x in bars.get((s,t),[])]
            cv={t:coverage[(s,t)] for t in range(a,b,MINUTE) if (s,t) in coverage}
            result=compute_window(s,at,m,tr,br,cv)
            # Reverse every observed occurrence and add deliberately extreme future rows.
            future_trade=dict(symbol=s,timestamp_ns=b,price=1e9,size=999999,condition='I')
            future_bar=dict(symbol=s,timestamp_ns=b,vwap=1e9,volume=999999,trade_count=999999)
            check=compute_window(s,at,m,list(reversed(tr))+[future_trade],list(reversed(br))+[future_bar],cv)
            if check['reasons']!=result['reasons'] or check['missing']!=result['missing'] or check['audit']!=result['audit']:raise ValueError('Order/future mask drift')
            for name in NAMES:
                x,y=result['values'][name],check['values'][name]
                if x is not None and not np.isclose(x,y,rtol=1e-12,atol=1e-12):raise ValueError('Order/future numerical drift')
            row['audit_json']=json.dumps(result['audit'],sort_keys=True)
        else:
            result=dict(values={n:None for n in NAMES},missing={n:1 for n in NAMES},
                reasons={n:'outside_stock_session_option_hours_unresolved' for n in NAMES})
            row['audit_json']='{}'
        for n in NAMES:
            row['diagnostic__'+n]=result['values'][n];row['missing__diagnostic__'+n]=result['missing'][n];row['reason__'+n]=result['reasons'][n]
        windows.append(row)
    frame=pd.DataFrame(windows)
    for n in NAMES:
        frame['diagnostic__'+n]=frame['diagnostic__'+n].astype('float64');frame['missing__diagnostic__'+n]=frame['missing__diagnostic__'+n].astype('uint8')
    links=pd.DataFrame(dict(event_ordinal=np.arange(len(events),dtype='int64'),
        window_id=[lookup.get((r.acquisition_candidate,r.signal_at_ns)) for r in events.itertuples()],model_feature_admitted=False))
    attempt=uuid.uuid4().hex
    files=[save_frame(root,f'{tag}-{attempt}-windows.parquet',frame),save_frame(root,f'{tag}-{attempt}-links.parquet',links)]
    result=dict(scope=dict(ticker=scope['ticker'],minutes=m),plan_sha256=plan['sha256'],files=files,
        logical_rows=len(events),candidate_links=int(links.window_id.notna().sum()),windows=len(frame),
        complete_diagnostic_windows=int(frame[[f'missing__diagnostic__{n}' for n in NAMES]].sum(axis=1).eq(0).sum()),
        reasons={n:dict(Counter(frame['reason__'+n])) for n in NAMES},
        all_real_windows_order_future_checked=True,model_feature_admitted=False)
    save(root/f'{tag}.json',result);return result


def run(root,max_scopes=None):
    import fcntl
    root=Path(root);plan=verify(root);started=time.monotonic();results=[];processed=0;market=None
    with (root/'writer.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for scope in plan['scopes']:
            path=root/f"{scope['ticker']}-{scope['minutes']}.json"
            if path.exists():
                r=json.loads(path.read_text())
                if r['plan_sha256']!=plan['sha256']:raise ValueError('Scope plan drift')
                for f in r['files']:
                    if sha((root/f['path']).read_bytes())!=f['sha256']:raise ValueError('Completed payload drift')
            else:
                if max_scopes is not None and processed>=max_scopes:break
                guard(root,plan,started)
                if market is None:market=market_inputs()
                r=run_scope(root,scope,plan,market,started);processed+=1
            results.append(r);print(json.dumps({k:r[k] for k in ('scope','logical_rows','windows','complete_diagnostic_windows')}),flush=True)
        report=dict(plan_sha256=plan['sha256'],complete=len(results)==9,processed_scopes=processed,
            scope_receipts={f"{r['scope']['ticker']}-{r['scope']['minutes']}.json":sha((root/f"{r['scope']['ticker']}-{r['scope']['minutes']}.json").read_bytes()) for r in results},
            logical_rows=sum(r['logical_rows'] for r in results),windows=sum(r['windows'] for r in results),
            candidate_links=sum(r['candidate_links'] for r in results),complete_diagnostic_windows=sum(r['complete_diagnostic_windows'] for r in results),
            elapsed_seconds=time.monotonic()-started,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
            model_feature_admitted=False,ready_for_training=False)
        save(root/('run-'+uuid.uuid4().hex+'.json'),report)
        if report['complete'] and not (root/'COMPLETE.json').exists():save(root/'COMPLETE.json',report)
        return report
