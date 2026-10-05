"""Frozen, factored ETFE remaining-feature study with real/synthetic boundaries."""
import gzip
import importlib.metadata
import json
from pathlib import Path
import resource
import time
import uuid

import numpy as np
import pandas as pd

from nn_meta.etfe.acquisition import ROOT,digest,sha,save,write_new
from nn_meta.etfe.causal_pilot import SETUP,START,STOP,source_files as causal_sources,parquet_new,checked_scope
from nn_meta.etfe.signals import signal_batches
from nn_meta.etfe.tv_feature_pilot import PILOT,inputs,verify as verify_tv
from nn_meta.etfe.option_feature_pilot import guard
from nn_meta.etfe.normalization import load_normalization
from nn_meta.etfe.event_features import catalog_features,signal_history,names,SECTORS
from nn_meta.etfe.context_features import daily_stock,stock_context,surface_summary,option_context,STOCK_FIELDS,OPTION_FIELDS

TV=ROOT/'nn_meta/validation/etfe-tv-features-20261005-r0'
SOURCES=['nn_meta/etfe/event_features.py','nn_meta/etfe/context_features.py','nn_meta/etfe/remaining_feature_pilot.py',
 'nn_meta/etfe/tv_feature_pilot.py','nn_meta/etfe/option_feature_pilot.py','nn_meta/etfe/purchase_policy_v2.py',
 'scripts/pilot_etfe_remaining_features.py','scripts/audit_etfe_remaining_features.py',
 'docs/specs/ETFE_REMAINING_FEATURES_20261005.md','docs/specs/ETFE_FEATURE_BINDINGS_20261005.json']
CONTEXT_ROOTS=[ROOT/'nn_meta/data_cache_etfe'/n for n in ('normalized-20261004-january-discovery-r0','normalized-20261004-january-surfaces-r0')]


def prepare(root):
    prior=verify_tv(TV);amend=json.loads((ROOT/SOURCES[-1]).read_text())
    if sha((ROOT/amend['parent']).read_bytes())!=amend['parent_sha256']:raise ValueError('Amendment parent drift')
    paths=[TV/n for n in ('PLAN.json','COMPLETE.json','INDEPENDENT_AUDIT.json')]+[SETUP/'catalog.json']
    for normal in CONTEXT_ROOTS:
        load_normalization(normal);paths += [normal/n for n in ('PLAN.json','NORMALIZED.json','INDEPENDENT_AUDIT.json')]
    source_set=set(causal_sources())|set(SOURCES)
    plan=dict(schema='etfe-remaining-feature-components-v1',sources={n:sha((ROOT/n).read_bytes()) for n in sorted(source_set)},
        inputs={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in paths},parent_plan_sha256=prior['sha256'],scopes=prior['scopes'],
        fields=names()+STOCK_FIELDS+OPTION_FIELDS,technical_overrides=['ma_gap','px_vs_fast'],
        packages={n:importlib.metadata.version(n) for n in ('numpy','pandas','pyarrow','vectorbt')},
        limits=dict(max_root_bytes=2**30,max_run_seconds=1800),real_dated_identity_available=False,
        real_option_surface_admitted=False,model_feature_admitted=False,full_feature_schema_complete=False,ready_for_training=False)
    if len(plan['fields'])!=100 or len(set(plan['fields']))!=100:raise ValueError('Remaining field census')
    plan['sha256']=digest(plan);root=Path(root);root.mkdir(parents=True,exist_ok=False);save(root/'PLAN.json',plan)
    for n in plan['sources']:
        p=root/'source'/n;p.parent.mkdir(parents=True,exist_ok=True);write_new(p,(ROOT/n).read_bytes())
    return plan


def verify(root):
    root=Path(root);p=json.loads((root/'PLAN.json').read_text())
    if digest({k:v for k,v in p.items() if k!='sha256'})!=p['sha256']:raise ValueError('Plan drift')
    for n,h in p['sources'].items():
        if sha((ROOT/n).read_bytes())!=h or sha((root/'source'/n).read_bytes())!=h:raise ValueError('Source drift: '+n)
    for n,h in p['inputs'].items():
        if sha((ROOT/n).read_bytes())!=h:raise ValueError('Input drift')
    for n,v in p['packages'].items():
        if importlib.metadata.version(n)!=v:raise ValueError('Package drift')
    if verify_tv(TV)['sha256']!=p['parent_plan_sha256']:raise ValueError('Predecessor drift')
    for normal in CONTEXT_ROOTS:load_normalization(normal)
    return p


def pack(values,reasons):
    if not values.index.equals(reasons.index) or not values.columns.equals(reasons.columns):raise ValueError('Feature alignment')
    if np.isinf(values.to_numpy(dtype=float)).any():raise ValueError('Infinite features')
    return pd.concat([values.astype('float64').add_prefix('diagnostic__'),values.isna().astype('uint8').add_prefix('missing__diagnostic__'),
        reasons.add_prefix('reason__')],axis=1).assign(model_feature_admitted=False)


def catalog():return json.loads((SETUP/'catalog.json').read_text())['records']


def build_shared(root,plan):
    values,reasons=catalog_features(catalog());static=pack(values,reasons);daily={};surfaces={};surface_audit=[]
    for t in ('SPY','QQQ','VOO'):
        scope=next(s for s in plan['scopes'] if s['ticker']==t and s['minutes']==1)
        daily[t]=daily_stock(pd.read_parquet(PILOT/scope['underlying']['path']))
        d=daily[t];rows=[]
        for i,day in enumerate(d.index):
            # No historical surface proof was supplied. Future collection must
            # produce it rather than promoting today's discovery to dated terms.
            spot=d.close.iloc[i]
            if i+1<len(d) and math_finite_positive(spot):
                row,audit=surface_summary([],spot,d.session_close.iloc[i],d.session_open.iloc[i+1])
            else:
                row=dict(near=np.nan,far=np.nan,ratio=np.nan,raw_ratio=np.nan)
                audit=dict(reason='stock_close_or_next_open_unavailable')
            rows.append(row);surface_audit.append(dict(ticker=t,session_date=day,**audit))
        surfaces[t]=pd.DataFrame(rows,index=d.index)
    contexts=[];summary=[];checks=[]
    for t,d in daily.items():
        stock,why=stock_context(d,daily['SPY']);opt=option_context(surfaces[t],surfaces['SPY'],stock)
        reason=pd.DataFrame('dated_surface_coverage_unresolved',index=d.index,columns=OPTION_FIELDS)
        context=pack(pd.concat([stock,opt],axis=1),pd.concat([why,reason],axis=1)).reset_index()
        context['ticker']=t;context['available_at']=d.session_open.to_numpy();contexts.append(context)
        summary.append(d.reset_index().assign(ticker=t))
        cut=350
        a,b=stock_context(d.iloc[:cut],daily['SPY'].iloc[:cut]);pd.testing.assert_frame_equal(a,stock.iloc[:cut],rtol=1e-12,atol=1e-12)
        changed=d.copy();changed.loc[changed.index[cut-1]:,'close']*=2
        future,_=stock_context(changed,daily['SPY']);pd.testing.assert_frame_equal(future.iloc[:cut],stock.iloc[:cut],rtol=1e-12,atol=1e-12)
        checks.append(dict(ticker=t,prefix_sessions=cut,prefix_future_passed=True))
    files=[parquet_new(root,'STATIC.parquet',static),parquet_new(root,'DAILY.parquet',pd.concat(contexts,ignore_index=True)),
           parquet_new(root,'STOCK_DAILY_INPUTS.parquet',pd.concat(summary,ignore_index=True))]
    save(root/'SURFACE_GAPS.json',dict(real_surface_evidence_available=False,observations=surface_audit))
    files.append(dict(path='SURFACE_GAPS.json',sha256=sha((root/'SURFACE_GAPS.json').read_bytes())))
    r=dict(plan_sha256=plan['sha256'],files=files,static_variants=len(static),daily_rows=sum(len(d) for d in daily.values()),daily_prefix_checks=checks)
    save(root/'SHARED.json',r);return r


def math_finite_positive(v):return bool(np.isfinite(v) and v>0)


def run_scope(root,scope,plan,started):
    raw,bars=inputs(scope);records=[r for r in catalog() if r['signal_minutes']==scope['minutes']];positions=[]
    signals=signal_history(bars,records,signal_batches(bars,records,raw),observation_start=START,position_sink=positions)
    guard(root,plan,started)
    cutoff=len(bars)-max(7,60//scope['minutes']);prefix_positions=[];prefix=bars.iloc[:cutoff]
    check=signal_history(prefix,records,signal_batches(prefix,records,raw,width=17),observation_start=START,position_sink=prefix_positions)
    for full,part in zip(positions,prefix_positions,strict=True):
        if full['variant_id']!=part['variant_id'] or full['direction']!=part['direction'] or [i for i in full['positions'] if i<cutoff]!=part['positions']:
            raise ValueError('Full-history signal prefix/batch drift')
    expected=signals[signals.bar_position<cutoff].reset_index(drop=True)
    pd.testing.assert_frame_equal(expected,check,rtol=1e-12,atol=1e-12)
    vals=signals[['dir_short','bars_since_signal','ma_gap','px_vs_fast']]
    why=pd.DataFrame('observed_diagnostic',index=vals.index,columns=vals.columns)
    for n in vals:why.loc[vals[n].isna(),n]='first_signal' if n=='bars_since_signal' else 'insufficient_chart_history'
    metadata=signals.drop(columns=vals.columns);output=pd.concat([metadata,pack(vals,why)],axis=1)
    events=pd.read_parquet(PILOT/scope['events']['path']);lookup={(r.variant_id,r.direction,r.signal_at_ns):i for i,r in enumerate(signals.itertuples())}
    ids=[lookup[(e.variant_id,e.direction,e.signal_at_ns)] for e in events.itertuples()]
    if set(ids)!=set(range(len(signals))):raise ValueError('Logical signal census drift')
    links=pd.DataFrame(dict(event_ordinal=np.arange(len(events),dtype='int64'),signal_ordinal=ids,variant_id=events.variant_id,
        context_session_date=pd.to_datetime(events.signal_at_ns,utc=True).dt.tz_convert('America/New_York').dt.strftime('%Y-%m-%d')))
    missing=['dte_frac','moneyness']+['sec_'+n for n in SECTORS]
    mv=pd.DataFrame(np.nan,index=links.index,columns=missing)
    mr=pd.DataFrame({n:('dated_selected_contract_unresolved' if n in ('dte_frac','moneyness') else 'dated_sector_unresolved') for n in missing},index=links.index)
    links=pd.concat([links,pack(mv,mr)],axis=1)
    tag=f"{scope['ticker']}-{scope['minutes']}";attempt=uuid.uuid4().hex
    files=[parquet_new(root,f'{tag}-{attempt}-signals.parquet',output),parquet_new(root,f'{tag}-{attempt}-links.parquet',links)]
    path=root/f'{tag}-{attempt}-positions.json.gz';write_new(path,gzip.compress(json.dumps(positions,separators=(',',':')).encode(),mtime=0))
    files.append(dict(path=path.name,sha256=sha(path.read_bytes())))
    r=dict(scope=dict(ticker=scope['ticker'],minutes=scope['minutes']),plan_sha256=plan['sha256'],files=files,
        logical_rows=len(events),signals=len(signals),variants=len(records),prefix_batch_passed=True,
        prefix_bar_count=cutoff,signals_with_prior=int(signals.previous_position.ge(0).sum()),
        signals_with_pre_pilot_prior=int((signals.previous_signal_at_ns.ge(0)&signals.previous_signal_at_ns.lt(START.value)).sum()),
        model_feature_admitted=False)
    save(root/f'{tag}.json',r);return r


def run(root,max_scopes=None):
    import fcntl
    root=Path(root);plan=verify(root);started=time.monotonic();results=[];processed=0
    with (root/'writer.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);guard(root,plan,started)
        shared=checked_scope(root,root/'SHARED.json') or build_shared(root,plan)
        if shared['plan_sha256']!=plan['sha256']:raise ValueError('Shared plan drift')
        for scope in plan['scopes']:
            guard(root,plan,started);path=root/f"{scope['ticker']}-{scope['minutes']}.json";r=checked_scope(root,path)
            if r is None:
                if max_scopes is not None and processed>=max_scopes:break
                r=run_scope(root,scope,plan,started);processed+=1
            if r['plan_sha256']!=plan['sha256']:raise ValueError('Scope plan drift')
            results.append(r);print(json.dumps({k:r[k] for k in ('scope','logical_rows','signals','signals_with_pre_pilot_prior')}),flush=True)
        report=dict(plan_sha256=plan['sha256'],complete=len(results)==9,processed_scopes=processed,
            shared_sha256=sha((root/'SHARED.json').read_bytes()),scope_receipts={f"{r['scope']['ticker']}-{r['scope']['minutes']}.json":sha((root/f"{r['scope']['ticker']}-{r['scope']['minutes']}.json").read_bytes()) for r in results},
            logical_rows=sum(r['logical_rows'] for r in results),signals=sum(r['signals'] for r in results),
            signals_with_pre_pilot_prior=sum(r['signals_with_pre_pilot_prior'] for r in results),
            elapsed_seconds=time.monotonic()-started,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
            model_feature_admitted=False,full_feature_schema_complete=False,ready_for_training=False)
        save(root/f'run-{uuid.uuid4().hex}.json',report)
        if report['complete'] and not (root/'COMPLETE.json').exists():save(root/'COMPLETE.json',report)
        return report
