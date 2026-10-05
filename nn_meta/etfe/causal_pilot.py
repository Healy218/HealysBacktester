"""Source-bound ETFE causal component study; no execution or training admission."""
from collections import Counter,defaultdict
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import sys
import time
import uuid

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from nn_meta.etfe.acquisition import ROOT,digest,save,sha,write_new,resources
from nn_meta.etfe.causal_inputs import (FEATURES,normalized_partitions,stock_minutes,
    session_bars,technical_diagnostics)
from nn_meta.etfe.eligibility import select_contract,feature_window,union_intervals
from nn_meta.etfe.expansion import read_calendar
from nn_meta.etfe.signals import signal_batches
from scripts.prepare_etfe_0dte import verify as verify_setup

CACHE=ROOT/'nn_meta/data_cache_etfe'
STOCK=CACHE/'normalized-20261004-main-r0'
OPTIONS=[STOCK,CACHE/'normalized-20261004-strata-r0',CACHE/'normalized-20261004-january-surfaces-r0']
CALENDAR=CACHE/'alpaca-fresh-20261004-calendar-r1'
SETUP=ROOT/'nn_meta/validation/etfe-setup-20261004-0dte-r0'
START=pd.Timestamp('2024-01-18T14:30Z')
STOP=pd.Timestamp('2024-01-19T21:00Z')
EVENT_SCHEMA=pa.schema([('ticker',pa.string()),('minutes',pa.int16()),('variant_id',pa.string()),
    ('strategy',pa.string()),('direction',pa.string()),('signal_at_ns',pa.int64()),
    ('target_dte',pa.int16()),('raw_spot',pa.float64()),('acquisition_candidate',pa.string()),
    ('eligibility_reason',pa.string()),('feature_start_ns',pa.int64()),('feature_end_ns',pa.int64()),
    ('feature_inside_stock_session',pa.bool_()),('entry_eligible',pa.bool_())])


def source_files():
    # Import mathematical kernels only to capture their transitive local code.
    modules=['signals.'+n for n in ('ma_crossover','rsi_threshold','macd_signals','bbands_breakout',
        'stoch_crossover','volume_breakout','elliott_wave_signals','tv_signals')]
    registry=json.loads((ROOT/'docs/specs/ETFE_FEATURE_MAP_20261003.json').read_text())
    aliases={'gaussian','fibonacci','uptrick','structure','sr','probability','amd'}
    modules += [r['calculator'].rsplit('.',1)[0] for r in registry['tv_scopes'] if r['scope'] in aliases]
    modules.append('nn_meta.v7.setup')
    for module in modules:importlib.import_module(module)
    sources={str(p.relative_to(ROOT)) for m in list(sys.modules.values())
        if (f:=getattr(m,'__file__',None)) and (p:=Path(f).resolve()).is_relative_to(ROOT)
        and p.suffix=='.py' and str(p.relative_to(ROOT)).startswith(('signals/','indicators/','v3/','utils/'))}
    sources.update(['nn_meta/v7/setup.py','nn_meta/etfe/causal_inputs.py','nn_meta/etfe/signals.py',
        'nn_meta/etfe/eligibility.py','nn_meta/etfe/causal_pilot.py','scripts/pilot_etfe_causal.py',
        'docs/specs/ETFE_CAUSAL_PILOT_20261004.md','docs/specs/ETFE_FEATURE_MAP_20261003.json',
        'docs/specs/ETFE_SCOPE_0DTE_20261004.json'])
    return sorted(sources)


def prepare(root):
    setup=verify_setup(SETUP);inputs=[]
    for p in OPTIONS:
        for name in ('PLAN.json','NORMALIZED.json','INDEPENDENT_AUDIT.json'):
            inputs.append(dict(path=str(p/name),sha256=sha((p/name).read_bytes())))
    inputs.extend(dict(path=str(p),sha256=sha(p.read_bytes())) for p in
                  (CALENDAR/'CALENDAR.json',SETUP/'catalog.json'))
    plan=dict(schema='etfe-causal-component-plan-v1',setup_sha256=setup['plan_sha256'],inputs=inputs,
        packages={p:importlib.metadata.version(p) for p in ('numpy','pandas','pyarrow','vectorbt')},
        sources={p:sha((ROOT/p).read_bytes()) for p in source_files()},
        observation_start=str(START),observation_end=str(STOP),calculation_origin='2024-01-02',
        price_basis='raw_unadjusted_diagnostics_not_admitted_features',
        scopes=[dict(ticker=t,minutes=m) for t in ('SPY','QQQ','VOO') for m in (1,5,15)],
        implemented_shared_features=FEATURES,full_feature_schema_complete=False,
        limits=dict(max_root_bytes=4*2**30,max_run_seconds=1800,signal_columns=32,writer_rows=5000),
        ready_for_build=False,ready_for_training=False)
    plan['sha256']=digest(plan);root=Path(root);root.mkdir(parents=True,exist_ok=False)
    save(root/'PLAN.json',plan)
    for n in plan['sources']:
        p=root/'source'/n;p.parent.mkdir(parents=True,exist_ok=True);write_new(p,(ROOT/n).read_bytes())
    return plan


def verify(root):
    root=Path(root);plan=json.loads((root/'PLAN.json').read_text())
    if digest({k:v for k,v in plan.items() if k!='sha256'})!=plan['sha256']:raise ValueError('Pilot plan drift')
    if any(importlib.metadata.version(p)!=v for p,v in plan['packages'].items()):raise ValueError('Pilot package drift')
    for n,h in plan['sources'].items():
        if sha((ROOT/n).read_bytes())!=h or sha((root/'source'/n).read_bytes())!=h:raise ValueError('Pilot source drift')
    for r in plan['inputs']:
        if sha(Path(r['path']).read_bytes())!=r['sha256']:raise ValueError('Pilot input drift')
    return plan


def guard(root,plan,started):
    if time.monotonic()-started>plan['limits']['max_run_seconds']:raise RuntimeError('pilot_time_budget')
    r=resources(root)
    if r['disk_free']<max(100*2**30,.2*r['disk_total'])+2**30:raise RuntimeError('pilot_disk_reserve')
    if r['ram_available']<max(2*2**30,.2*r['ram_total'])+2**30:raise RuntimeError('pilot_ram_reserve')
    if sum(p.stat().st_size for p in Path(root).rglob('*') if p.is_file())+256*2**20>plan['limits']['max_root_bytes']:
        raise RuntimeError('pilot_root_budget')


def observations():
    result={}
    columns=['symbol','underlying','timestamp_ns','expiration_date','right','strike','quality_flags','occurrence_id']
    for root in OPTIONS:
        for _,p in normalized_partitions(root,'option_bars'):
            for batch in pq.ParquetFile(p).iter_batches(batch_size=5000,columns=columns):
                for r in batch.to_pylist():
                    if r['quality_flags'] or r['timestamp_ns']>=STOP.value:continue
                    s=r['symbol'];at=pd.Timestamp(r['timestamp_ns'],tz='UTC')
                    if s not in result or at<result[s]['first_observed_at']:
                        result[s]=dict(symbol=s,ticker=r['underlying'],right=r['right'],strike=r['strike'],
                            expiration_date=str(r['expiration_date']),first_observed_at=at,
                            first_source_occurrence_id=r['occurrence_id'])
    return result


def parquet_new(root,name,frame):
    path=Path(root)/name
    if path.exists():raise ValueError('Refusing overwrite')
    frame.to_parquet(path,index=True)
    with path.open('rb') as f:os.fsync(f.fileno())
    return dict(path=name,sha256=sha(path.read_bytes()),rows=len(frame))


def checked_scope(root,path):
    if not path.exists():return None
    r=json.loads(path.read_text())
    for f in r['files']:
        if sha((root/f['path']).read_bytes())!=f['sha256']:raise ValueError('Completed scope checksum drift')
    return r


def run_scope(root,scope,calendar,contracts,plan,started):
    ticker,minutes=scope['ticker'],scope['minutes'];tag=f'{ticker}-{minutes}'
    raw=stock_minutes(STOCK,ticker)
    chart=session_bars(raw,calendar,minutes)
    features=technical_diagnostics(chart)
    output=chart.copy()
    for name in FEATURES:
        output['raw__'+name]=features[name]
        output['missing__raw__'+name]=features[name].isna().astype('uint8')
    attempt=uuid.uuid4().hex;files=[parquet_new(root,f'{tag}-{attempt}-underlying.parquet',output)]
    pilot=chart[chart.bar_end.le(STOP)].copy()
    if not pilot.valid.all():raise ValueError('Pilot history has incomplete bars; no silent reset/drop')
    records=[r for r in json.loads((SETUP/'catalog.json').read_text())['records'] if r['signal_minutes']==minutes]
    chosen=[c for c in contracts.values() if c['ticker']==ticker]
    selection_cache={};reasons=Counter();census=[];prefix={};row_count=0;buffer=[];physical=defaultdict(set)
    event_path=root/f'{tag}-{attempt}-events.parquet'
    cutoff=max(1,len(pilot)-max(7,60//minutes));observed=pilot.bar_end.ge(START).to_numpy()
    def flush(writer):
        nonlocal buffer
        if buffer:writer.write_table(pa.Table.from_pylist(buffer,schema=EVENT_SCHEMA));buffer=[]
    with pq.ParquetWriter(event_path,EVENT_SCHEMA,compression='zstd') as writer:
        for batch,channels in signal_batches(pilot,records,raw,width=plan['limits']['signal_columns']):
            guard(root,plan,started)
            for rec in batch:
                vid=rec['variant_id'];data=np.column_stack([f[vid].to_numpy() for f in channels])
                prefix[vid]=sha(np.packbits(data[:cutoff],axis=None).tobytes())
                counts=data[observed].sum(axis=0).tolist()
                census.append(dict(variant_id=vid,strategy=rec['strategy'],events=counts,prefix_sha256=prefix[vid]))
                for channel,direction,right in ((0,'long','call'),(2,'short','put')):
                    for position in np.flatnonzero(data[:,channel]&observed):
                        bar=pilot.iloc[position];at=bar.bar_end;spot=float(bar.Close)
                        a,b=feature_window(at,minutes);inside=a>=bar.session_open and b<=bar.session_close
                        for target in (0,1,5):
                            key=(at.value,right,target,spot)
                            if key not in selection_cache:
                                selection_cache[key]=select_contract(chosen,at,right=right,target=target,spot=spot)
                            result=selection_cache[key];candidate=result['acquisition_candidate']
                            symbol=candidate['symbol'] if candidate else None
                            reason=result['reason'];reasons[reason]+=1;row_count+=1
                            buffer.append(dict(ticker=ticker,minutes=minutes,variant_id=vid,strategy=rec['strategy'],
                                direction=direction,signal_at_ns=at.value,target_dte=target,raw_spot=spot,
                                acquisition_candidate=symbol,eligibility_reason=reason,feature_start_ns=a.value,
                                feature_end_ns=b.value,feature_inside_stock_session=bool(inside),entry_eligible=False))
                            if symbol:
                                if inside:
                                    physical[(symbol,'option_trades')].add((a.value,b.value))
                                    physical[(symbol,'option_bars')].add((a.value,b.value))
                                physical[(symbol,'option_bars')].add((at.value-60_000_000_000,at.value))
                            if len(buffer)>=5000:flush(writer)
        flush(writer)
    with event_path.open('rb') as f:os.fsync(f.fileno())
    files.append(dict(path=event_path.name,sha256=sha(event_path.read_bytes()),rows=row_count))
    for batch,channels in signal_batches(pilot.iloc[:cutoff],records,raw,width=17):
        guard(root,plan,started)
        for rec in batch:
            data=np.column_stack([f[rec['variant_id']].to_numpy() for f in channels])
            if sha(np.packbits(data,axis=None).tobytes())!=prefix.pop(rec['variant_id']):
                raise ValueError('Real all-variant prefix/batch invariance failed: '+rec['strategy'])
    if prefix:raise ValueError('Prefix variant census incomplete')
    intervals=[dict(symbol=s,route=r,intervals=union_intervals(v)) for (s,r),v in sorted(physical.items())]
    demand_path=root/f'{tag}-{attempt}-demand.json'
    save(demand_path,dict(physical=intervals,logical_rows=row_count,price_basis='raw_unadjusted_diagnostic',
        conditional_targets_withheld=[2,4],holding_demand_complete=False,entry_eligible=False))
    files.append(dict(path=demand_path.name,sha256=sha(demand_path.read_bytes())))
    report=dict(scope=scope,plan_sha256=plan['sha256'],files=files,calendar_bins=len(chart),
        invalid_bins=int((~chart.valid).sum()),feature_missing={n:int(features[n].isna().sum()) for n in FEATURES},
        pilot_prefix_bins=len(pilot),pilot_observed_bins=int(observed.sum()),variants=len(census),
        families=sorted({r['strategy'] for r in census}),variant_census=census,
        logical_rows=row_count,reasons=dict(reasons),physical_keys=len(intervals),
        physical_intervals=sum(len(x['intervals']) for x in intervals),all_variant_prefix_and_batch_check=True,
        eligible_entries=0,ready_for_build=False,ready_for_training=False)
    save(root/f'{tag}.json',report)
    return report


def run(root,*,max_scopes=None):
    import fcntl
    root=Path(root);plan=verify(root);started=time.monotonic();results=[];processed=0
    with (root/'writer.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        calendar=read_calendar(CALENDAR);contracts=None
        for scope in plan['scopes']:
            path=root/f"{scope['ticker']}-{scope['minutes']}.json"
            r=checked_scope(root,path)
            if r is None:
                if max_scopes is not None and processed>=max_scopes:break
                guard(root,plan,started)
                if contracts is None:contracts=observations()
                r=run_scope(root,scope,calendar,contracts,plan,started);processed+=1
            if r['plan_sha256']!=plan['sha256']:raise ValueError('Scope plan mismatch')
            results.append(r)
            print(json.dumps(dict(scope=scope,variants=r['variants'],logical_rows=r['logical_rows'],invalid_bins=r['invalid_bins'])),flush=True)
        report=dict(schema='etfe-causal-component-receipt-v1',plan_sha256=plan['sha256'],
            complete=len(results)==len(plan['scopes']),processed_scopes=processed,scopes=len(results),
            scope_receipts={f"{r['scope']['ticker']}-{r['scope']['minutes']}.json":sha((root/f"{r['scope']['ticker']}-{r['scope']['minutes']}.json").read_bytes()) for r in results},
            calendar_bins=sum(r['calendar_bins'] for r in results),invalid_bins=sum(r['invalid_bins'] for r in results),
            ticker_variant_combinations=sum(r['variants'] for r in results),logical_rows=sum(r['logical_rows'] for r in results),
            elapsed_seconds=time.monotonic()-started,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
            eligible_entries=0,full_feature_schema_complete=False,ready_for_build=False,ready_for_training=False)
        save(root/('run-'+uuid.uuid4().hex+'.json'),report)
        if report['complete'] and not (root/'COMPLETE.json').exists():save(root/'COMPLETE.json',report)
        return report
