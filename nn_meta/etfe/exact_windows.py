"""Factor complete diagnostic signal memberships into auditable acquisition windows."""
from bisect import bisect_left
from collections import Counter,defaultdict
from datetime import date
import json
from pathlib import Path
import time
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from nn_meta.etfe import acquisition as a,window_demand as w
from nn_meta.etfe.causal_inputs import normalized_partitions
from nn_meta.etfe.eligibility import union_intervals

INPUTS=[w.STOCK,a.ROOT/'nn_meta/data_cache_etfe/normalized-20261004-strata-r0',
        a.ROOT/'nn_meta/data_cache_etfe/normalized-20261004-january-surfaces-r0',
        a.ROOT/'nn_meta/data_cache_etfe/normalized-20261004-trade-windows-r0']
SOURCES=['nn_meta/etfe/exact_windows.py','scripts/build_etfe_exact_windows.py']


def subtract(interval,covered):
    pending=[interval]
    for c,d in union_intervals(covered):
        result=[]
        for x,y in pending:
            if d<=x or c>=y:result.append((x,y))
            else:
                if x<c:result.append((x,c))
                if d<y:result.append((d,y))
        pending=result
    return pending


def prior_observations():
    records={}
    cols=['symbol','underlying','expiration_date','right','strike','timestamp_ns','quality_flags','occurrence_id']
    for root in INPUTS:
        for route in ('option_bars','option_trades'):
            for _,path in normalized_partitions(root,route):
                for batch in pq.ParquetFile(path).iter_batches(batch_size=5000,columns=cols):
                    for r in batch.to_pylist():
                        if r['quality_flags']:continue
                        key=r['symbol']
                        if key not in records or r['timestamp_ns']<records[key]['timestamp_ns']:records[key]=r
    for r in records.values():
        r['first_date']=pd.Timestamp(r['timestamp_ns'],tz='UTC').tz_convert('America/New_York').date()
    return records


def choices(records,ticker,day,right):
    groups=defaultdict(list)
    for r in records.values():
        if r['underlying']==ticker and r['right']==right and r['first_date']<day and 0<=(r['expiration_date']-day).days<=5:
            groups[r['expiration_date']].append((r['strike'],r['symbol']))
    return {e:sorted(rows) for e,rows in groups.items()}


def nearest(groups,day,target,spot):
    for e in sorted(groups,key=lambda e:(abs((e-day).days-target),e)):
        rows=groups[e];i=bisect_left(rows,(spot,''));candidate=min(rows[max(0,i-1):min(len(rows),i+1)],key=lambda x:(abs(x[0]-spot),x[0],x[1]))
        # Equal strike entries need the lexical-first symbol on either side.
        candidate=rows[bisect_left(rows,(candidate[0],''))]
        if .85*spot<=candidate[0]<=1.15*spot:return candidate[1]
    return None


def weights(source,tag):
    folder=source/tag;chart=pq.read_table(folder/'chart.parquet').to_pandas();total=np.zeros((len(chart),4),dtype=np.uint16);seen=set();checks=0
    for path in sorted(folder.glob('*.json')):
        r=json.loads(path.read_text())
        if a.sha((folder/'chart.parquet').read_bytes())!=r['chart_sha256']:raise ValueError('Chart drift')
        expected={v['variant_id']:v['events'] for v in r['census']};members=set()
        for name,h in r['files'].items():
            p=folder/name
            if a.sha(p.read_bytes())!=h:raise ValueError('Packed signal drift')
            if name.endswith('-union.npz'):continue
            with np.load(p,allow_pickle=False) as z:
                n=int(z['rows'][0]);ids=z['variants'].tolist();bits=np.unpackbits(z['packed'],axis=0,count=n)
            if n!=r['calculated_bins'] or bits.shape!=(n,4,len(ids)):raise ValueError('Packed signal dimensions')
            for i,vid in enumerate(ids):
                if vid in seen or bits[:,:,i].sum(axis=0).tolist()!=expected[vid]:raise ValueError('Variant membership/count mismatch')
                seen.add(vid);members.add(vid)
            total[:n]+=bits.sum(axis=2,dtype=np.uint16);checks+=len(ids)
        if members!=set(expected):raise ValueError('Missing variant membership')
    if checks!=2817:raise ValueError('Scope does not contain all catalog variants')
    return chart,total


def prepare(root,source):
    root,source=Path(root),Path(source).resolve();p=w.load(source);complete=json.loads((source/'SIGNALS.json').read_text())
    if not complete['complete'] or complete['checkpoints']!=180:raise ValueError('Full computational checkpoint census required')
    inputs={str(source/n):a.sha((source/n).read_bytes()) for n in ('PLAN.json','SIGNALS.json','CONTEXT.json','CONTEXT_AUDIT.json')}
    for scope in p['scopes']:
        for path in (source/f"{scope['ticker']}-{scope['minutes']}").glob('*.json'):inputs[str(path)]=a.sha(path.read_bytes())
    for r in INPUTS:
        for n in ('PLAN.json','NORMALIZED.json','INDEPENDENT_AUDIT.json'):inputs[str(r/n)]=a.sha((r/n).read_bytes())
    plan=dict(schema='etfe-exact-window-factorization-v1',source=str(source),source_plan_sha256=p['sha256'],inputs=inputs,
        sources={n:a.sha((a.ROOT/n).read_bytes()) for n in SOURCES},ready_for_build=False,ready_for_training=False)
    plan['sha256']=a.digest(plan);root.mkdir(parents=True,exist_ok=False);a.save(root/'PLAN.json',plan)
    for n in SOURCES:
        dest=root/'source'/n;dest.parent.mkdir(parents=True,exist_ok=True);a.write_new(dest,(a.ROOT/n).read_bytes())
    return plan


def load(root):
    root=Path(root);p=json.loads((root/'PLAN.json').read_text())
    if a.digest({k:v for k,v in p.items() if k!='sha256'})!=p['sha256']:raise ValueError('Plan drift')
    if w.load(p['source'])['sha256']!=p['source_plan_sha256']:raise ValueError('Signal source plan drift')
    for n,h in p['inputs'].items():
        if a.sha(Path(n).read_bytes())!=h:raise ValueError('Input receipt drift')
    for n,h in p['sources'].items():
        if a.sha((root/'source'/n).read_bytes())!=h or a.sha((a.ROOT/n).read_bytes())!=h:raise ValueError('Source drift')
    return p


def run(root):
    root=Path(root);p=load(root);source=Path(p['source']);started=time.monotonic();observed=prior_observations();summary=[];physical=defaultdict(set)
    for scope in w.load(source)['scopes']:
        w.guard(root,w.load(source),started)
        ticker,m=scope['ticker'],scope['minutes'];tag=f'{ticker}-{m}';receipt=root/(tag+'.json')
        if receipt.exists():
            r=json.loads(receipt.read_text())
            if a.sha((root/r['data']).read_bytes())!=r['data_sha256']:raise ValueError('Decision output drift')
        else:
            chart,count=weights(source,tag);cache={};counts=Counter();records=[];chunks=[];writer=None;path=root/(tag+'.parquet')
            if path.exists():raise ValueError('Uncommitted decision file requires recovery in successor')
            for channel,right in ((0,'call'),(2,'put')):
                for i in np.flatnonzero(count[:,channel]):
                    bar=chart.iloc[i];at=bar.bar_end.value;day=date.fromisoformat(bar.session_date);spot=float(bar.Close)
                    key=(day,right)
                    if key not in cache:cache[key]=choices(observed,ticker,day,right)
                    windows=w.reference_windows(at,m,bar.session_open.value,bar.session_close.value)
                    weight=int(count[i,channel]);counts['signal_memberships']+=weight
                    for target in (0,1,5):
                        symbol=nearest(cache[key],day,target,spot);reason='dated_selection_unresolved' if symbol else 'prior_observation_coverage_unresolved'
                        counts[reason]+=weight;counts['decision_clocks']+=1
                        records.append(dict(ticker=ticker,minutes=m,chart_row=int(i),signal_at_ns=at,right=right,target_dte=target,
                            logical_memberships=weight,raw_spot=spot,acquisition_candidate=symbol or '',reason=reason,
                            feature_start_ns=windows['feature'][0] if windows['feature'] else -1,feature_end_ns=windows['feature'][1] if windows['feature'] else -1,
                            entry_start_ns=windows['entry'][0],entry_end_ns=windows['entry'][1],entry_eligible=False))
                        if len(records)>=5000:
                            table=pa.Table.from_pylist(records)
                            if writer is None:writer=pq.ParquetWriter(path,table.schema,compression='zstd')
                            writer.write_table(table);records=[]
            if records:
                table=pa.Table.from_pylist(records)
                if writer is None:writer=pq.ParquetWriter(path,table.schema,compression='zstd')
                writer.write_table(table)
            if writer is None:raise ValueError('Zero-signal scope needs explicit schema')
            writer.close();r=dict(scope=scope,data=path.name,data_sha256=a.sha(path.read_bytes()),counts=dict(counts),
                weekly_target_memberships_unresolved=(2 if ticker in ('SPY','QQQ') else 0)*counts['signal_memberships'],holding_paths_realized=0)
            a.save(receipt,r)
        summary.append(r)
        for batch in pq.ParquetFile(root/r['data']).iter_batches(batch_size=5000):
            for row in batch.to_pylist():
                s=row['acquisition_candidate']
                if not s:continue
                physical[s,'option_bars'].add((row['entry_start_ns'],row['entry_end_ns']))
                if row['feature_start_ns']>=0:
                    for route in ('option_bars','option_trades'):physical[s,route].add((row['feature_start_ns'],row['feature_end_ns']))
        print(json.dumps(dict(scope=tag,counts=r['counts'])),flush=True)
    coverage=defaultdict(list);receipts=[]
    raw_roots={x['root'] for r in INPUTS for x in json.loads((r/'PLAN.json').read_text())['inputs']}
    for raw in sorted(raw_roots):
        for job in a.load_plan(raw)['jobs']:
            route=job['route']
            if route not in ('option_bars','option_trades'):continue
            symbols=[s for s in job['params']['symbols'].split(',') if (s,route) in physical]
            if not symbols:continue
            _,_,done=a.committed(raw,job)
            if not done:continue
            x=pd.Timestamp(job['params']['start']).value;y=pd.Timestamp(job['params']['end']).value+1
            for s in symbols:coverage[s,route].append((x,y))
            receipts.append(dict(root=raw,job_id=job['id']))
    demands=[];totals=Counter()
    for (s,route),intervals in sorted(physical.items()):
        merged=union_intervals(intervals);pending=[v for interval in merged for v in subtract(interval,coverage[s,route])]
        totals[route+'_intervals']+=len(merged);totals[route+'_pending_intervals']+=len(pending)
        totals[route+'_pending_minutes']+=sum((b-a)//w.MINUTE for a,b in pending)
        demands.append(dict(symbol=s,route=route,intervals=merged,pending_intervals=pending))
    result=dict(plan_sha256=p['sha256'],scope_receipts=summary,physical=demands,totals=dict(totals),transport_receipts=receipts,
        observed_contracts=len(observed),logical_target_memberships=sum(sum(v for k,v in r['counts'].items() if k.endswith('_unresolved')) for r in summary),
        weekly_target_memberships_unresolved=sum(r['weekly_target_memberships_unresolved'] for r in summary),
        holding_paths_realized=0,holding_frontier='await_dated_selection_and_real_execution_receipts',
        full_strategy_demand_complete=False,ready_for_build=False,ready_for_training=False,elapsed_seconds=time.monotonic()-started)
    if not (root/'DEMAND.json').exists():a.save(root/'DEMAND.json',result)
    return {k:v for k,v in result.items() if k not in ('physical','scope_receipts','transport_receipts')}
