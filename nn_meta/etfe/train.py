"""ETFE experiment v2 training runner: folds, preprocessing, GBT/NN/constant fits, resumable receipts.

Implements docs/specs/ETFE_EXPERIMENT_V2_20261007.json exactly; nothing is tuned. Features are cast
to float32 for fitting (recorded in each receipt). Each fit writes model, predictions and a receipt
last; a fit with a valid receipt is skipped on restart (recovery = rerun).
"""
import bisect
import datetime as dt
import json
import os
from pathlib import Path
import resource
import time

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from nn_meta.etfe import acquisition as a
from nn_meta.etfe.joined_features import schema

ROOT=Path(__file__).resolve().parents[2]
EXPERIMENT=ROOT/'docs/specs/ETFE_EXPERIMENT_V2_20261007.json'


def load_experiment():
    e=json.loads(EXPERIMENT.read_text())
    if a.digest({k:v for k,v in e.items() if k!='sha256'})!=e['sha256'] or e['status']!='frozen':raise ValueError('Experiment drift')
    m=json.loads((ROOT/e['dataset_manifest']).read_text())
    if m['sha256']!=e['dataset_manifest_sha256']:raise ValueError('Dataset manifest drift')
    return e,m


def folds(e):
    out={f['id']:dict(train_end=f['train_end'],start=f['validation_start'],end=f['validation_end']) for f in e['folds']}
    f=e['final_refit'];out[f['id']]=dict(train_end=f['train_end'],start=f['test_start'],end=f['test_end'])
    return out


def load_rows(e,m,columns):
    root=(ROOT/e['dataset_manifest']).parent;parts=[]
    for tag,info in m['partitions'].items():
        path=root/info['path']
        if a.sha(path.read_bytes())!=info['sha256']:raise ValueError(f'{tag}: partition drift')
        parts.append(pq.read_table(path,columns=columns).to_pandas())
    return pd.concat(parts,ignore_index=True)


def split(e,m,fold_id,data):
    f=folds(e)[fold_id];sessions=m['sessions']
    i=bisect.bisect_left(sessions,f['start']);cut=sessions[max(i-e['embargo_sessions'],0)]
    cut_ns=pd.Timestamp(cut+' 09:30',tz='America/New_York').value
    train=data.labeled&(data.session_date<=f['train_end'])&(data.purge_horizon_ns<cut_ns)
    evaluate=(data.session_date>=f['start'])&(data.session_date<=f['end'])
    return train.to_numpy(),evaluate.to_numpy(),dict(fold=fold_id,purge_cut_session=cut,**f)


def preprocess(X,train,names):
    """Train-only medians; zero for all-NaN training columns. Masks are separate inputs."""
    # In place on the fold matrix Z = [values | masks]; `names` is the value width. No full copies.
    Z,width=X,names
    med=np.empty(width,np.float32)
    for i in range(width):
        col=Z[:,i];v=col[train];v=v[~np.isnan(v)]
        med[i]=np.median(v) if len(v) else 0.0
        col[np.isnan(col)]=med[i]
    return med


def target(e,objective,data,rows):
    if objective=='return_huber':return data.target_return.to_numpy()[rows],None
    y=data.target_win.to_numpy()[rows];w=data.target_weight.to_numpy()[rows] if objective=='weighted_win' else None
    return y,w


def fit_gbt(e,trial,X,y,w,objective):
    import lightgbm as lgb
    g=e['gbt'];params=dict(num_leaves=g['num_leaves'],learning_rate=g['learning_rate'],min_data_in_leaf=g['min_data_in_leaf'],
        max_bin=g['max_bin'],num_threads=g['threads'],bagging_fraction=1.0,feature_fraction=1.0,seed=trial['seed'],
        deterministic=True,force_row_wise=True,verbose=-1)
    params.update(objective='huber',alpha=g['huber_alpha']) if objective=='return_huber' else params.update(objective='binary')
    model=lgb.train(params,lgb.Dataset(X,y,weight=w,params=dict(max_bin=g['max_bin'])),num_boost_round=g['rounds'])
    return model


def fit_nn(e,trial,X,y,w,objective):
    import tensorflow as tf
    tf.keras.utils.set_random_seed(trial['seed']);tf.config.experimental.enable_op_determinism()
    n=e['nn'];layers=[tf.keras.Input(shape=(X.shape[1],))]+[tf.keras.layers.Dense(h,activation=n['activation']) for h in n['hidden']]
    layers.append(tf.keras.layers.Dense(1,activation=None if objective=='return_huber' else 'sigmoid'))
    model=tf.keras.Sequential(layers)
    loss=tf.keras.losses.Huber(delta=n['huber_delta']) if objective=='return_huber' else tf.keras.losses.BinaryCrossentropy()
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=n['learning_rate']),loss=loss)
    model.fit(X,y,sample_weight=w,batch_size=n['batch_size'],epochs=n['epochs'],shuffle=n['shuffle'],verbose=0)
    return model


def predict_chunks(fn,Z,rows,chunk=250_000):
    idx=np.flatnonzero(rows);out=np.empty(len(idx))
    for i in range(0,len(idx),chunk):out[i:i+chunk]=fn(Z[idx[i:i+chunk]])
    return out


MEDIANS={}


def run_fit(out,fit_id,e,m,data,Z,width):
    """One declared fit -> model, predictions on the fold's evaluation rows, receipt (written last).

    Z is the fold matrix [values | masks] (float32); values are median-filled in place once per fold.
    """
    out=Path(out);receipt=out/'receipts'/(fit_id.replace('/','__')+'.json')
    if receipt.exists():return json.loads(receipt.read_text()),True
    fold_id,trial_id=fit_id.split('/');trial=next(t for t in e['trials'] if t['id']==trial_id);objective=trial['objective']
    started=time.monotonic();train,evaluate,info=split(e,m,fold_id,data)
    if fold_id not in MEDIANS:MEDIANS[fold_id]=preprocess(Z,train,width)
    med=MEDIANS[fold_id];y,w=target(e,objective,data,train)
    if trial['family']=='constant':
        value=float(np.average(y,weights=w)) if w is not None else float(np.mean(y));pred=np.full(int(evaluate.sum()),value)
        model_path=out/'models'/(fit_id.replace('/','__')+'.json');model_path.parent.mkdir(parents=True,exist_ok=True)
        model_path.write_text(json.dumps(dict(constant=value))+'\n')
    elif trial['family']=='gbt':
        model=fit_gbt(e,trial,Z[train],y,w,objective);pred=predict_chunks(model.predict,Z,evaluate)
        model_path=out/'models'/(fit_id.replace('/','__')+'.txt');model_path.parent.mkdir(parents=True,exist_ok=True);model.save_model(str(model_path))
    else:
        Xt=Z[train];mu=Xt[:,:width].mean(axis=0);sd=Xt[:,:width].std(axis=0);sd=np.where(sd>0,sd,1.0).astype(np.float32)
        Xt[:,:width]-=mu;Xt[:,:width]/=sd
        model=fit_nn(e,trial,Xt,y,w,objective);del Xt
        def nn_predict(B):
            B=B.copy();B[:,:width]-=mu;B[:,:width]/=sd
            return model.predict(B,batch_size=65536,verbose=0).ravel()
        pred=predict_chunks(nn_predict,Z,evaluate)
        model_path=out/'models'/(fit_id.replace('/','__')+'.keras');model_path.parent.mkdir(parents=True,exist_ok=True);model.save(str(model_path))
        # TensorFlow otherwise retains converted training tensors and graphs (~3 GB per final-fold fit).
        import gc
        import tensorflow as tf
        del model;tf.keras.backend.clear_session();gc.collect()
    preds=data.loc[evaluate,['ticker','minutes','chart_row','signal_at_ns','right','target_dte','contract','session_date','labeled']].copy()
    preds['score']=pred.astype(np.float64)
    pred_path=out/'predictions'/(fit_id.replace('/','__')+'.parquet');pred_path.parent.mkdir(parents=True,exist_ok=True)
    preds.to_parquet(pred_path,index=False)
    r=dict(fit_id=fit_id,trial=trial,split=info,train_rows=int(train.sum()),evaluate_rows=int(evaluate.sum()),
        model=str(model_path.relative_to(out)),model_sha256=a.sha(model_path.read_bytes()) if model_path.is_file() else None,
        predictions=str(pred_path.relative_to(out)),predictions_sha256=a.sha(pred_path.read_bytes()),
        medians_sha256=a.digest([float(x) for x in med]),feature_dtype='float32',experiment_sha256=e['sha256'],
        elapsed_seconds=time.monotonic()-started,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
        finished_at=dt.datetime.now(dt.timezone.utc).isoformat())
    receipt.parent.mkdir(parents=True,exist_ok=True);a.save(receipt,r)
    return r,False


META=['ticker','minutes','chart_row','signal_at_ns','right','target_dte','contract','session_date','purge_horizon_ns',
      'labeled','target_return','target_win','target_weight']


def load_fold(e,m,fold_id):
    """Only one fold's rows: labeled rows through train_end plus every row in the evaluation window.

    Filtering happens in Arrow before pandas; values arrive as float32 and masks as uint8, column by
    column, so peak memory stays near the fold matrix size (the whole dataset is never materialized;
    loading all 6.59M x 442 columns at once exhausted RAM on 2026-10-07).
    """
    import pyarrow as pa
    import pyarrow.compute as pc
    names=schema()['fields'];f=folds(e)[fold_id];root=(ROOT/e['dataset_manifest']).parent;w=len(names)

    def keep(t):
        d=t['session_date']
        return pc.or_(pc.and_(t['labeled'],pc.less_equal(d,f['train_end'])),
                      pc.and_(pc.greater_equal(d,f['start']),pc.less_equal(d,f['end'])))
    files=[]
    for tag,info in m['partitions'].items():
        path=root/info['path']
        if a.sha(path.read_bytes())!=info['sha256']:raise ValueError(f'{tag}: partition drift')
        files.append(pq.ParquetFile(path))
    # Pass 1: count kept rows (meta columns only). Pass 2: stream each row group into a preallocated Z.
    total=0
    for pf in files:
        for g in range(pf.num_row_groups):total+=pc.sum(keep(pf.read_row_group(g,columns=['session_date','labeled']))).as_py() or 0
    Z=np.empty((total,2*w),np.float32);metas=[];pos=0
    for pf in files:
        for g in range(pf.num_row_groups):
            t=pf.read_row_group(g,columns=META+names+['missing__'+n for n in names]);t=t.filter(keep(t));n=t.num_rows
            if not n:continue
            for i,name in enumerate(names):
                Z[pos:pos+n,i]=t[name].cast(pa.float32()).to_numpy(zero_copy_only=False)
                Z[pos:pos+n,w+i]=t['missing__'+name].to_numpy(zero_copy_only=False)
            metas.append(t.select(META));pos+=n;del t
    if pos!=total:raise ValueError('Fold row count drift')
    data=pa.concat_tables(metas).to_pandas();del metas
    return data,Z,w
