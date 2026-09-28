"""Fixed-family retraining on an immutable base plus matured candidate rows."""
from __future__ import annotations
import json
import shutil
from pathlib import Path
import time

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from .storage import sha,identity,write,seal,verify


def assemble_delta(run_dir,features):
    rows=[]
    for inventory in sorted((Path(run_dir)/'symbols').glob('*/inventory.json')):
        verify(inventory.parent)
        cached={}
        for candidate in json.loads(inventory.read_text())['candidates']:
            if candidate['status']!='matured':continue
            origin=Path(candidate['feature_root']);label_root=Path(candidate['label_root'])
            verify(label_root);label=json.loads((label_root/'label.json').read_text())
            if origin not in cached:
                verify(origin)
                from .data import candidate_key
                cached[origin]={candidate_key(r):r for r in pd.read_parquet(origin/'features.parquet').to_dict('records')}
            row=cached[origin][candidate['candidate_id']]
            rows.append({k:row[k] for k in ['symbol','strategy','dte','entry_ts',*features]}|
                        {k:label[k] for k in ['exit_ts','fill_exit_ts','net_return','label_excess']}|
                        {'candidate_id':candidate['candidate_id']})
    frame=pd.DataFrame(rows)
    if len(frame):
        if frame.candidate_id.duplicated().any():raise ValueError('duplicate extension identities')
        frame['entry_ts']=pd.to_datetime(frame.entry_ts)
        frame['exit_ts']=pd.to_datetime(frame.exit_ts)
        frame['fill_exit_ts']=pd.to_datetime(frame.fill_exit_ts)
        frame=frame.sort_values(['entry_ts','symbol','strategy','dte'])
    frame.to_parquet(Path(run_dir)/'delta.parquet',index=False)
    return frame


def split_metadata(meta,val_start,embargo_days):
    entry=pd.to_datetime(meta.entry_ts);end=pd.to_datetime(meta.exit_ts)
    if 'fill_exit_ts' in meta:end=pd.concat([end,pd.to_datetime(meta.fill_exit_ts)],axis=1).max(axis=1)
    valid=meta.label_excess.notna() & meta.net_return.notna() & end.notna()
    if not np.isfinite(meta.loc[valid,['label_excess','net_return']].to_numpy(float)).all():
        raise ValueError('non-finite training targets')
    if not meta.loc[valid,'label_excess'].isin([0,1]).all() or (end[valid]<entry[valid]).any():
        raise ValueError('invalid labels or maturity clocks')
    train=valid & (entry<val_start) & (end<val_start-pd.Timedelta(days=embargo_days))
    val=valid & (entry>=val_start)
    return train.to_numpy(),val.to_numpy()


def prepare_arrays(base,delta,root,features,validation_days,embargo_days,append_start):
    root=Path(root);base=Path(base);delta=Path(delta)
    declaration=dict(base_sha256=sha(base),delta_sha256=sha(delta),features=features,
                     validation_days=validation_days,embargo_days=embargo_days,append_start=append_start,
                     source_sha256=sha(__file__))
    if (root/'complete.json').exists():return verify(root,declaration)
    columns=['entry_ts','exit_ts','fill_exit_ts','label_excess','net_return']
    sources=[base,delta]
    metadata=[pd.read_parquet(path,columns=columns) for path in sources]
    if len(metadata[1]) and (pd.to_datetime(metadata[1].entry_ts)<pd.Timestamp(append_start)).any():
        raise ValueError('extension overlaps immutable training base')
    if (pd.to_datetime(metadata[0].entry_ts)>=pd.Timestamp(append_start)).any():raise ValueError('base overlaps extension')
    days=sorted(set(pd.concat([m.entry_ts for m in metadata]).dt.normalize()))
    if len(days)<=validation_days:raise ValueError('insufficient chronological training history')
    val_start=pd.Timestamp(days[-validation_days]);masks=[split_metadata(m,val_start,embargo_days) for m in metadata]
    sizes={name:sum(int(pair[i].sum()) for pair in masks) for i,name in enumerate(['train','validation'])}
    if not all(sizes.values()):raise ValueError('empty purged train or validation partition')
    root.mkdir(parents=True,exist_ok=True);arrays={};files=[]
    required=sum(sizes.values())*(len(features)+2)*8
    if shutil.disk_usage(root).free<required+12_000_000_000:
        raise ValueError('insufficient disk for arrays plus research reserve')
    for split,size in sizes.items():
        for suffix,shape in [('x',(size,len(features))),('y',(size,)),('return',(size,))]:
            name=f'{split}_{suffix}.npy';files.append(name)
            arrays[split,suffix]=np.lib.format.open_memmap(root/name,mode='w+',dtype='float64',shape=shape)
    offsets=dict(train=0,validation=0)
    for path,meta,pair in zip(sources,metadata,masks):
        offset=0
        for batch in pq.ParquetFile(path).iter_batches(batch_size=16384,columns=features):
            frame=batch.to_pandas();n=len(frame)
            if np.isinf(frame.to_numpy(float)).any():raise ValueError('infinite training features')
            for i,split in enumerate(['train','validation']):
                selected=pair[i][offset:offset+n];size=int(selected.sum());start=offsets[split]
                arrays[split,'x'][start:start+size]=frame.loc[selected,features].to_numpy(float)
                arrays[split,'y'][start:start+size]=meta.iloc[offset:offset+n].loc[selected,'label_excess']
                arrays[split,'return'][start:start+size]=meta.iloc[offset:offset+n].loc[selected,'net_return']
                offsets[split]+=size
            offset+=n
    for array in arrays.values():array.flush()
    if offsets!=sizes:raise ValueError('prepared row counts disagree')
    if sha(base)!=declaration['base_sha256'] or sha(delta)!=declaration['delta_sha256']:
        raise ValueError('dataset changed during array preparation')
    bounds=np.quantile(arrays['train','return'],[.01,.99]).tolist()
    # Match the frozen magnitude target: train-only 1%/99% clipping.
    write(root/'arrays.json',dict(sizes=sizes,features=features,val_start=val_start.isoformat(),bounds=bounds))
    return seal(root,declaration,[*files,'arrays.json'])


def train_member(arrays, parent_member, output, threads):
    import joblib
    import lightgbm as lgb
    arrays=Path(arrays);output=Path(output);parent_member=Path(parent_member)
    verify(arrays);doc=json.loads((arrays/'arrays.json').read_text())
    declaration=dict(arrays=sha(arrays/'complete.json'),parent={h:sha(parent_member/f'{h}.joblib') for h in ['model','magnitude']},
                     source=sha(__file__),lightgbm=lgb.__version__,threads=threads)
    if (output/'complete.json').exists():return verify(output,declaration)
    output.mkdir(parents=True,exist_ok=True);started=time.monotonic()
    x={s:np.load(arrays/f'{s}_x.npy',mmap_mode='r') for s in ['train','validation']}
    for head,target,metric in [('model','y','auc'),('magnitude','return','l1')]:
        y={s:np.load(arrays/f'{s}_{target}.npy',mmap_mode='r') for s in x}
        if head=='magnitude':y={s:np.clip(v,*doc['bounds']) for s,v in y.items()}
        params=joblib.load(parent_member/f'{head}.joblib').get_params()
        params.update(n_jobs=threads,verbosity=-1)
        model=(lgb.LGBMClassifier if head=='model' else lgb.LGBMRegressor)(**params)
        model.fit(x['train'],y['train'],eval_set=[(x['validation'],y['validation'])],
                  feature_name=doc['features'],eval_metric=metric,
                  callbacks=[lgb.early_stopping(max(10,int(params['n_estimators'])//10)),lgb.log_evaluation(0)])
        joblib.dump(model,output/f'{head}.joblib')
    return seal(output,declaration,['model.joblib','magnitude.joblib'],seconds=time.monotonic()-started)


def predict(model_root,members,x,deadline=float('inf')):
    import joblib
    result={head:np.zeros(len(x)) for head in ['model','magnitude']}
    for member in members:
        for head in result:
            model=joblib.load(Path(model_root)/member/f'{head}.joblib')
            for start in range(0,len(x),16384):
                if time.monotonic()>deadline:raise TimeoutError('evaluation deadline reached')
                batch=x[start:start+16384]
                pred=(model.predict_proba(batch,num_threads=1)[:,1] if head=='model' else model.predict(batch,num_threads=1))
                if not np.isfinite(pred).all():raise ValueError('non-finite ensemble prediction')
                result[head][start:start+len(batch)]+=pred/len(members)
    return result


def evaluate(arrays,candidate,parent,members,deadline=float('inf')):
    arrays=Path(arrays);x=np.load(arrays/'validation_x.npy',mmap_mode='r')
    y=np.load(arrays/'validation_y.npy',mmap_mode='r');returns=np.load(arrays/'validation_return.npy',mmap_mode='r')
    scores={}
    for name,root in [('candidate',candidate),('parent',parent)]:
        pred=predict(root,members,x,deadline)
        scores[name]=dict(brier=float(np.mean((pred['model']-y)**2)),
                         return_mse=float(np.mean((pred['magnitude']-returns)**2)),
                         return_mae=float(np.mean(np.abs(pred['magnitude']-returns))))
    baseline=float(np.mean(returns**2));scores['zero_return_baseline_mse']=baseline
    prior=float(np.load(arrays/'train_y.npy',mmap_mode='r').mean())
    class_baseline=float(np.mean((y-prior)**2));scores['training_prevalence_baseline_brier']=class_baseline
    passed=(scores['candidate']['return_mse']<=min(scores['parent']['return_mse'],baseline)
            and scores['candidate']['brier']<=min(scores['parent']['brier'],class_baseline))
    return dict(status='passed' if passed else 'rejected',metrics=scores,validation_rows=len(y),
                scope='purged temporal validation; reused for daily selection, not an untouched performance test',
                deployment_approved=False)
