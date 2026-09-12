"""Opt-in, bounded seed processes using immutable memory-mapped fold arrays.

No changes to baseline labels, architectures, early stopping, or policy gates.
Each seed writes a hash-verified receipt after its model files are complete.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import gc
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import numpy as np
import pandas as pd
from nn_meta import config


def enabled():
    return os.environ.get('NN_META_PREPARED_TRAINING') == '1'


def release_memory():
    """Return unused Arrow/libc arenas after large temporary transformations."""
    import pyarrow as pa
    import ctypes
    gc.collect()
    pa.default_memory_pool().release_unused()
    libc = ctypes.CDLL(None)
    if hasattr(libc, 'malloc_trim'):
        libc.malloc_trim(0)


def read_dataset(path):
    """Avoid consolidating a second full numeric table while reading Parquet."""
    import pyarrow.parquet as pq
    table = pq.read_table(path)
    frame = table.to_pandas(split_blocks=True, self_destruct=True)
    del table
    release_memory()
    return frame


def training_rows(frame, mask, features, label):
    columns = list(dict.fromkeys([*features, label, 'net_return']))
    return frame.loc[mask & frame[label].notna(), columns]


def policy_rows(frame, mask):
    """Same chronological candidate ordering without repeated feature copies."""
    mask = mask & frame.executed & frame.net_return.notna()
    order = frame.loc[mask,'entry_ts'].sort_values().index
    result = frame.loc[order]
    result.index = pd.RangeIndex(len(result))
    return result


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(4*1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def _json(path, value):
    p = Path(path); t = p.with_suffix('.tmp')
    t.write_text(json.dumps(value, sort_keys=True, indent=2)+'\n'); t.replace(p)


def prepare(train, val, features, label, *, root=None):
    """Same pandas scaler/float32 conversion as the reference; once per fold."""
    from nn_meta.v4_evaluate import _matrix, winsor_bounds
    from nn_meta.ev_sizing import magnitude_target
    root = Path(root or config.RUNS_DIR/'prepared')
    columns = list(dict.fromkeys([*features, label, 'net_return']))
    def narrow(frame):
        if list(frame.columns) == columns and frame[label].notna().all():
            return frame
        return frame.loc[frame[label].notna(), columns]
    tr, va = narrow(train), narrow(val)
    if tr.empty or va.empty:
        raise ValueError('Training requires labeled train and validation rows')
    identity = hashlib.sha256(json.dumps({'features':features,'label':label,
        'preparer':sha(__file__)},sort_keys=True).encode())
    for frame in (tr, va):
        identity.update(pd.util.hash_pandas_object(frame, index=False).values.tobytes())
        identity.update(str(frame.dtypes.tolist()).encode())
    key = identity.hexdigest(); dest = root/key
    dest.mkdir(parents=True, exist_ok=True)
    manifest = dest/'arrays.json'
    if manifest.exists():
        doc = json.loads(manifest.read_text())
        if doc['key'] == key and all(sha(dest/n)==h for n,h in doc['hashes'].items()):
            return dest
        raise ValueError('Prepared training arrays changed; use a fresh cache')
    # Column reductions avoid allocating another full feature block.
    mean = pd.Series({f:tr[f].mean() for f in features})
    std = pd.Series({f:tr[f].std() for f in features}).replace(0, 1.0)
    masks = [f['net_return'].notna().to_numpy() for f in (tr,va)]
    if not all(m.any() for m in masks):
        raise ValueError('Prepared training requires observed returns in both partitions; use the reference path for classification-only fits')
    bounds = winsor_bounds(magnitude_target(tr.loc[masks[0], 'net_return']))
    hashes = {}
    for split, frame, mask in zip(['train','val'], [tr,va], masks):
        # Standardization used to allocate several complete multi-GB matrices.
        # Only a bounded batch is transformed; workers mmap the finished arrays.
        for name, dtype in [('raw','float64'),('x','float32')]:
            path=dest/f'{split}_{name}.npy'
            target=np.lib.format.open_memmap(path,mode='w+',dtype=dtype,shape=(len(frame),len(features)))
            for start in range(0,len(frame),65536):
                batch=frame.iloc[start:start+65536]
                target[start:start+len(batch)]=(batch[features].to_numpy(dtype=dtype)
                    if name=='raw' else _matrix(batch,features,mean,std))
            target.flush();del target
            hashes[path.name]=sha(path)
            release_memory()
        arrays = [('y', lambda: frame[label].to_numpy(dtype='float32')),
                  ('mindex', lambda: np.flatnonzero(mask)),
                  ('mag', lambda: np.clip(magnitude_target(frame.loc[mask,'net_return']), *bounds))]
        for name, make in arrays:
            path=dest/f'{split}_{name}.npy'; np.save(path, make(), allow_pickle=False); hashes[path.name]=sha(path)
    _json(manifest, {'version':1,'key':key,'features':features,'label':label,
                     'mean':mean.to_dict(),'std':std.to_dict(),'bounds':list(bounds),
                     'hashes':hashes,'rows':{'train':len(tr),'val':len(va)}})
    print(f'Prepared fold arrays: {key[:12]} train={len(tr)} val={len(va)}', flush=True)
    return dest


def settings(prepared, family, seed, epochs, estimators):
    from importlib import metadata
    return dict(version=1, prepared=sha(Path(prepared)/'arrays.json'),family=family,seed=int(seed),
                epochs=int(epochs),estimators=int(estimators),arch=config.ARCHITECTURES[0],
                lr=config.LEARNING_RATES[0],batch=config.BATCH_SIZE,l2=config.L2_REG,dropout=config.DROPOUT,
                threads=int(os.environ.get('NN_META_TRAIN_THREADS','2')),
                sources={n:sha(Path(__file__).parent/n) for n in ['training_jobs.py','model.py','v4_evaluate.py','ev_sizing.py']},
                runtime={n:metadata.version(n) for n in ['numpy','pandas','tensorflow','lightgbm']})


def reusable(dest, expected):
    p=Path(dest)/'complete.json'
    if not p.exists(): return False
    doc=json.loads(p.read_text())
    if doc['settings']!=expected: raise ValueError('Seed configuration changed; use fresh output directory')
    if not all((Path(dest)/n).is_file() and sha(Path(dest)/n)==h for n,h in doc['hashes'].items()):
        raise ValueError('Seed artifact checksum mismatch')
    return True


def run_seeds(prepared, family, seeds, *, epochs, estimators, out=None, run_prefix=None):
    seeds=list(seeds)
    if not seeds or len(seeds)!=len(set(seeds)):raise ValueError('Expected unique, nonempty seeds')
    prepared=Path(prepared)
    common=settings(prepared,family,seeds[0],epochs,estimators);common.pop('seed')
    key=hashlib.sha256(json.dumps(common,sort_keys=True).encode()).hexdigest()[:24]
    out=Path(out or config.RUNS_DIR/'seed-jobs'/key);out.mkdir(parents=True,exist_ok=True)
    workers=int(os.environ.get('NN_META_TRAIN_WORKERS','1'))
    if not 1<=workers<=4:raise ValueError('Training workers must be between 1 and 4')
    if not 1<=common['threads']<=4:raise ValueError('Threads per worker must be between 1 and 4')
    def one(seed):
        run_id=f'{run_prefix}-s{seed}' if run_prefix else f'{family}-s{seed}'
        dest=out/run_id;dest.mkdir(exist_ok=True)
        expected=settings(prepared,family,seed,epochs,estimators)
        if reusable(dest,expected):
            print(f'Resume verified seed {run_id}',flush=True);return dest
        import psutil
        if psutil.virtual_memory().available < 4*2**30:
            raise RuntimeError('Less than 4 GiB available; refusing additional training')
        env=dict(os.environ)
        for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMBA_NUM_THREADS','TF_NUM_INTRAOP_THREADS']:
            env[k]=str(expected['threads'])
        env.update(TF_NUM_INTEROP_THREADS='1',CUDA_VISIBLE_DEVICES='-1')
        cmd=[sys.executable,'-m','nn_meta.training_jobs','--prepared',str(prepared),'--out',str(dest),
             '--family',family,'--seed',str(seed),'--epochs',str(epochs),'--estimators',str(estimators)]
        print(f'Start seed {run_id}',flush=True)
        with (dest/'worker.log').open('a') as log:
            subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
        if not reusable(dest,expected):raise RuntimeError('Worker failed to commit its receipt')
        print(f'Completed seed {run_id}',flush=True)
        return dest
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one,seeds))


def worker(prepared, out, family, seed, epochs, estimators):
    prepared,out=Path(prepared),Path(out)
    doc=json.loads((prepared/'arrays.json').read_text())
    if not all(sha(prepared/n)==h for n,h in doc['hashes'].items()):raise ValueError('Prepared array checksum mismatch')
    expected=settings(prepared,family,seed,epochs,estimators)
    if reusable(out,expected):return
    a={n[:-4]:np.load(prepared/n,mmap_mode='r',allow_pickle=False) for n in doc['hashes']}
    def magnitude_x(split, kind):
        x,index=a[f'{split}_{kind}'],a[f'{split}_mindex']
        return x if np.array_equal(index,np.arange(len(x))) else x[index]
    start=time.time();files=[]
    if family=='nn':
        import tensorflow as tf
        from nn_meta.model import build_meta_mlp,build_magnitude_mlp
        tf.keras.utils.set_random_seed(seed)
        model=build_meta_mlp(len(doc['features']),config.ARCHITECTURES[0],config.LEARNING_RATES[0])
        def early():return tf.keras.callbacks.EarlyStopping(monitor='val_loss',patience=max(3,min(12,epochs//4)),restore_best_weights=True)
        hist=model.fit(a['train_x'],a['train_y'],validation_data=(a['val_x'],a['val_y']),
                       epochs=epochs,batch_size=config.BATCH_SIZE,callbacks=[early()],verbose=0)
        loss=float(min(hist.history['val_loss']));model.save(out/'model.keras')
        del model,hist;tf.keras.backend.clear_session();release_memory()
        tf.keras.utils.set_random_seed(seed+10000)
        model=build_magnitude_mlp(len(doc['features']),config.ARCHITECTURES[0],config.LEARNING_RATES[0])
        model.fit(magnitude_x('train','x'),a['train_mag'].astype('float32'),
                  validation_data=(magnitude_x('val','x'),a['val_mag'].astype('float32')),
                  epochs=epochs,batch_size=config.BATCH_SIZE,callbacks=[early()],verbose=0)
        model.save(out/'magnitude.keras')
        _json(out/'scaler.json',{'mean':doc['mean'],'std':doc['std']})
        files=['model.keras','magnitude.keras','scaler.json']
    elif family=='gbt':
        import joblib
        from lightgbm import LGBMClassifier,LGBMRegressor,early_stopping,log_evaluation
        kw=dict(n_estimators=estimators,learning_rate=.02,num_leaves=31,subsample=.8,
                colsample_bytree=.8,min_child_samples=200,reg_lambda=1.,random_state=seed,
                n_jobs=expected['threads'],verbosity=-1)
        def callbacks():return [early_stopping(max(10,estimators//10)),log_evaluation(0)]
        model=LGBMClassifier(**kw)
        model.fit(a['train_raw'],a['train_y'].astype(int),eval_set=[(a['val_raw'],a['val_y'].astype(int))],
                  eval_metric='auc',feature_name=doc['features'],callbacks=callbacks())
        joblib.dump(model,out/'model.joblib');loss=None
        del model;release_memory()
        model=LGBMRegressor(objective='huber',alpha=.5,**kw)
        model.fit(magnitude_x('train','raw'),a['train_mag'],
                  eval_set=[(magnitude_x('val','raw'),a['val_mag'])],eval_metric='l1',
                  feature_name=doc['features'],callbacks=callbacks())
        joblib.dump(model,out/'magnitude.joblib');files=['model.joblib','magnitude.joblib']
    else:raise ValueError('Unknown model family')
    _json(out/'params.json',{'family':family,'seed':seed,'label':doc['label'],'features':doc['features'],
          'arch':config.ARCHITECTURES[0],'lr':config.LEARNING_RATES[0],
          'magnitude_head':{'target':'net_return','loss':'huber','winsor_bounds':doc['bounds']}})
    files.append('params.json')
    _json(out/'complete.json',{'settings':expected,'seconds':time.time()-start,'val_loss':loss,
                             'hashes':{n:sha(out/n) for n in files}})


def disk_predict(family, paths, rows, features, *, magnitude=False):
    """Load one member at a time; mean in fixed seed order, bounded transforms."""
    import joblib
    if not paths: raise ValueError('Cannot score an empty ensemble')
    total=np.zeros(len(rows),dtype='float32' if family=='nn' else 'float64')
    for path in paths:
        path=Path(path)
        if family=='nn':
            import tensorflow as tf
            from nn_meta.v4_evaluate import _matrix
            sc=json.loads((path/'scaler.json').read_text());mu,sd=pd.Series(sc['mean']),pd.Series(sc['std'])
            model=tf.keras.models.load_model(path/('magnitude.keras' if magnitude else 'model.keras'),compile=False)
        else:model=joblib.load(path/('magnitude.joblib' if magnitude else 'model.joblib'))
        for start in range(0,len(rows),65536):
            batch=rows.iloc[start:start+65536]
            if family=='nn':pred=model.predict(_matrix(batch,features,mu,sd),batch_size=4096,verbose=0).flatten()
            elif magnitude:pred=model.predict(batch[features])
            else:pred=model.predict_proba(batch[features])[:,1]
            total[start:start+len(batch)]+=pred
        del model
        if family=='nn':tf.keras.backend.clear_session()
        gc.collect()
    return total/len(paths)


def fit_family(family,train,val,*,features,label,seeds,epochs,gbt_estimators):
    prepared=prepare(train,val,features,label)
    return fit_prepared(family,prepared,features=features,seeds=seeds,epochs=epochs,gbt_estimators=gbt_estimators)


def fit_prepared(family,prepared,*,features,seeds,epochs,gbt_estimators):
    from nn_meta.v4_evaluate import Predictor
    paths=run_seeds(prepared,family,list(seeds) if family=='nn' else [0],epochs=epochs,estimators=gbt_estimators)
    return Predictor(family,lambda rows:disk_predict(family,paths,rows,features),
                     lambda rows:disk_predict(family,paths,rows,features,magnitude=True))


def main():
    p=argparse.ArgumentParser();p.add_argument('--prepared',required=True);p.add_argument('--out',required=True)
    p.add_argument('--family',choices=['nn','gbt'],required=True);p.add_argument('--seed',type=int,required=True)
    p.add_argument('--epochs',type=int,required=True);p.add_argument('--estimators',type=int,required=True)
    a=p.parse_args();worker(a.prepared,a.out,a.family,a.seed,a.epochs,a.estimators)
if __name__=='__main__':main()
