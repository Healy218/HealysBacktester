"""Immutable, bounded streaming join of verified ETFE diagnostic components."""
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import time
import uuid

import numpy as np
import pandas as pd

from nn_meta.etfe.acquisition import ROOT,digest,sha,save,write_new
from nn_meta.etfe.causal_pilot import verify as verify_causal
from nn_meta.etfe.option_feature_pilot import verify as verify_option,guard
from nn_meta.etfe.tv_feature_pilot import verify as verify_tv
from nn_meta.etfe.remaining_feature_pilot import verify as verify_remaining
from nn_meta.etfe.joined_features import schema,join_batch,validate_bundle

PARENTS={
 'causal':ROOT/'nn_meta/validation/etfe-causal-20261004-r0',
 'option':ROOT/'nn_meta/validation/etfe-option-features-20261004-r1',
 'tv':ROOT/'nn_meta/validation/etfe-tv-features-20261005-r0',
 'remaining':ROOT/'nn_meta/validation/etfe-remaining-features-20261005-r0'}
SOURCES=['nn_meta/etfe/joined_features.py','nn_meta/etfe/joined_pilot.py','scripts/pilot_etfe_joined.py',
 'scripts/audit_etfe_joined.py','docs/specs/ETFE_JOINED_SCHEMA_20261005.md',
 'docs/specs/ETFE_FEATURE_MAP_20261003.json','docs/specs/ETFE_FEATURE_BINDINGS_20261005.json']


def parent_plans():
    return {n:f(PARENTS[n]) for n,f in [('causal',verify_causal),('option',verify_option),('tv',verify_tv),('remaining',verify_remaining)]}


def prepare(root):
    parents=parent_plans();paths=set();scopes={}
    for name,base in PARENTS.items():
        complete=json.load(open(base/'COMPLETE.json'));audit=json.load(open(base/'INDEPENDENT_AUDIT.json'))
        if not complete['complete'] or complete['plan_sha256']!=parents[name]['sha256'] or audit['plan_sha256']!=parents[name]['sha256']:
            raise ValueError('Unverified predecessor')
        for file in ('PLAN.json','COMPLETE.json','INDEPENDENT_AUDIT.json','RESUME_AUDIT.json'):paths.add(base/file)
        for filename,h in complete['scope_receipts'].items():
            path=base/filename
            if sha(path.read_bytes())!=h:raise ValueError('Parent scope drift')
            r=json.load(open(path));paths.add(path)
            for f in r['files']:
                p=base/f['path']
                if sha(p.read_bytes())!=f['sha256']:raise ValueError('Parent payload drift')
                paths.add(p)
            key=(r['scope']['ticker'],r['scope']['minutes']);scopes.setdefault(key,{})[name]=r
    base=PARENTS['remaining'];shared=json.load(open(base/'SHARED.json'))
    for f in shared['files']:paths.add(base/f['path'])
    paths.update([base/'SHARED.json',base/'DAILY_INPUT_AUDIT.json'])
    chunks=[];scope_rows=[]
    for (ticker,minutes),receipts in sorted(scopes.items()):
        if set(receipts)!=set(PARENTS):raise ValueError('Missing parent scope')
        rows=receipts['causal']['logical_rows']
        if any(r['logical_rows']!=rows for r in receipts.values()):raise ValueError('Parent logical census drift')
        scope=dict(ticker=ticker,minutes=minutes,rows=rows,parents=receipts)
        scope_rows.append(scope)
        for start in range(0,rows,5000):chunks.append(dict(ticker=ticker,minutes=minutes,start=start,stop=min(start+5000,rows)))
    layout=schema();plan=dict(schema='etfe-joined-diagnostic-plan-v1',feature_schema=layout,feature_schema_sha256=digest(layout),
        sources={n:sha((ROOT/n).read_bytes()) for n in SOURCES},
        inputs={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in sorted(paths)},
        parents={n:dict(path=str(PARENTS[n].relative_to(ROOT)),plan_sha256=p['sha256']) for n,p in parents.items()},
        scopes=scope_rows,chunks=chunks,shared=shared,packages={n:importlib.metadata.version(n) for n in ('numpy','pandas','pyarrow')},
        limits=dict(max_root_bytes=2*2**30,max_run_seconds=1800,batch_rows=5000),
        joined_schema_implemented=True,model_feature_admitted=False,ready_for_training=False)
    plan['sha256']=digest(plan);root=Path(root);root.mkdir(parents=True,exist_ok=False);save(root/'PLAN.json',plan)
    for n in SOURCES:
        p=root/'source'/n;p.parent.mkdir(parents=True,exist_ok=True);write_new(p,(ROOT/n).read_bytes())
    return plan


def verify(root):
    root=Path(root);p=json.load(open(root/'PLAN.json'))
    if digest({k:v for k,v in p.items() if k!='sha256'})!=p['sha256']:raise ValueError('Plan drift')
    if p['feature_schema']!=schema() or digest(schema())!=p['feature_schema_sha256']:raise ValueError('Feature schema drift')
    for n,h in p['sources'].items():
        if sha((ROOT/n).read_bytes())!=h or sha((root/'source'/n).read_bytes())!=h:raise ValueError('Join source drift')
    for n,h in p['inputs'].items():
        if sha((ROOT/n).read_bytes())!=h:raise ValueError('Join input drift: '+n)
    for n,v in p['packages'].items():
        if importlib.metadata.version(n)!=v:raise ValueError('Package drift')
    for n,parent in parent_plans().items():
        if parent['sha256']!=p['parents'][n]['plan_sha256']:raise ValueError('Predecessor plan drift')
    return p


def load_scope(plan,scope):
    r=scope['parents']
    def frame(parent,i):return pd.read_parquet(PARENTS[parent]/r[parent]['files'][i]['path'])
    shared=plan['shared']['files'];static=pd.read_parquet(PARENTS['remaining']/shared[0]['path'])
    daily=pd.read_parquet(PARENTS['remaining']/shared[1]['path']);daily=daily[daily.ticker.eq(scope['ticker'])].set_index('session_date')
    technical=frame('causal',0);technical.index=pd.DatetimeIndex(technical.bar_end).as_unit('ns').asi8
    return dict(events=frame('causal',1),technical=technical,static=static,daily=daily,
        signals=frame('remaining',0),remaining_links=frame('remaining',1),tv=frame('tv',0).reset_index(drop=True),
        tv_links=frame('tv',2),windows=frame('option',0).set_index('window_id'),option_links=frame('option',1))


def chunk_name(chunk):return f"{chunk['ticker']}-{chunk['minutes']}-{chunk['start']:09d}.json"


def checked_chunk(root,chunk,plan):
    p=Path(root)/'chunks'/chunk_name(chunk)
    if not p.exists():return None
    r=json.load(open(p))
    if r['chunk']!=chunk or r['plan_sha256']!=plan['sha256'] or r['feature_schema_sha256']!=plan['feature_schema_sha256']:
        raise ValueError('Committed chunk binding drift')
    if r['rows']!=chunk['stop']-chunk['start'] or set(r['files'])!={'matrix','reasons','availability','rows'}:raise ValueError('Committed chunk census drift')
    for f in r['files'].values():
        if sha((Path(root)/f['path']).read_bytes())!=f['sha256']:raise ValueError('Committed payload drift')
    return r


def save_bundle(root,chunk,plan,bundle):
    relative=Path('payloads')/uuid.uuid4().hex;directory=Path(root)/relative;directory.mkdir(parents=True)
    files={}
    for kind,frame in bundle.items():
        path=directory/(kind+'.parquet');frame.to_parquet(path,index=False,compression='zstd')
        with path.open('rb') as stream:os.fsync(stream.fileno())
        files[kind]=dict(path=str(relative/path.name),sha256=sha(path.read_bytes()),rows=len(frame))
    missing=bundle['matrix'].iloc[:,221:].sum().to_numpy()
    result=dict(chunk=chunk,plan_sha256=plan['sha256'],feature_schema_sha256=plan['feature_schema_sha256'],files=files,
        rows=len(bundle['rows']),missing_by_field=dict(zip(plan['feature_schema']['fields'],map(int,missing))),
        logical_identity_unique=True,model_feature_admitted=False)
    folder=Path(root)/'chunks';folder.mkdir(exist_ok=True);save(folder/chunk_name(chunk),result);return result


def run(root,max_chunks=None):
    import fcntl
    root=Path(root);plan=verify(root);started=time.monotonic();processed=0;results=[];loaded=None;data=None
    with (root/'writer.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for chunk in plan['chunks']:
            guard(root,plan,started);r=checked_chunk(root,chunk,plan)
            if r is None:
                if max_chunks is not None and processed>=max_chunks:break
                key=(chunk['ticker'],chunk['minutes'])
                if key!=loaded:
                    scope=next(s for s in plan['scopes'] if (s['ticker'],s['minutes'])==key)
                    data=load_scope(plan,scope);loaded=key
                event_sha=scope['parents']['causal']['files'][1]['sha256']
                bundle=join_batch(data,chunk['start'],chunk['stop'],event_sha256=event_sha,layout=plan['feature_schema'])
                # Different actual batch boundaries must yield identical copies.
                cut=chunk['start']+max(1,(chunk['stop']-chunk['start'])//2)
                if cut<chunk['stop']:
                    first=join_batch(data,chunk['start'],cut,event_sha256=event_sha,layout=plan['feature_schema'])
                    second=join_batch(data,cut,chunk['stop'],event_sha256=event_sha,layout=plan['feature_schema'])
                    for kind in bundle:pd.testing.assert_frame_equal(bundle[kind],pd.concat([first[kind],second[kind]],ignore_index=True),check_exact=True)
                    del first,second
                r=save_bundle(root,chunk,plan,bundle);del bundle;processed+=1
            results.append(r)
            if chunk['stop']==next(s['rows'] for s in plan['scopes'] if s['ticker']==chunk['ticker'] and s['minutes']==chunk['minutes']):
                print(json.dumps(dict(scope=[chunk['ticker'],chunk['minutes']],rows=chunk['stop'])),flush=True)
        missing={n:sum(r['missing_by_field'][n] for r in results) for n in plan['feature_schema']['fields']}
        report=dict(plan_sha256=plan['sha256'],feature_schema_sha256=plan['feature_schema_sha256'],complete=len(results)==len(plan['chunks']),
            chunk_receipts={chunk_name(r['chunk']):sha((root/'chunks'/chunk_name(r['chunk'])).read_bytes()) for r in results},
            processed_chunks=processed,rows=sum(r['rows'] for r in results),missing_by_field=missing,
            elapsed_seconds=time.monotonic()-started,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
            all_chunks_batch_invariant=True,model_feature_admitted=False,ready_for_training=False)
        save(root/f'run-{uuid.uuid4().hex}.json',report)
        if report['complete'] and not (root/'COMPLETE.json').exists():save(root/'COMPLETE.json',report)
        return {k:v for k,v in report.items() if k not in ('missing_by_field','chunk_receipts')}
