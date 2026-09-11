"""Purged expanding-window FA ablations on immutable daily feature snapshots.

Reports forecast errors and cross-sectional rank correlation, not trade P&L.
No production model, thresholds, cohort or training universe is changed.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from fa.feature_snapshots import GROUPS, TECHNICAL
from fa.monthly import sha


def load_panel(root, prices, *, horizon=5):
    frames=[]; manifests={}; price_hashes={}; cache={}
    for folder in sorted(Path(root).glob('20*T*Z')):
        m=json.loads((folder/'manifest.json').read_text())
        for name,digest in m['files'].items():
            if Path(name).name!=name or sha(folder/name)!=digest: raise ValueError('Feature snapshot hash mismatch')
        frame=pd.read_parquet(folder/'features.parquet')
        if frame.ticker.duplicated().any() or not (pd.to_datetime(frame.cutoff,utc=True)==pd.Timestamp(m['cutoff'])).all():
            raise ValueError('Invalid feature snapshot identity')
        frame['recipe']=m['recipe'];frames.append(frame);manifests[folder.name]=sha(folder/'manifest.json')
    if not frames:return pd.DataFrame(),dict(snapshot_sha256=manifests,price_sha256=price_hashes)
    panel=pd.concat(frames,ignore_index=True);panel['cutoff']=pd.to_datetime(panel.cutoff,utc=True)
    panel['capture_day']=panel.cutoff.dt.date
    # One observation per ticker/capture day; no repeated intraday pseudo-samples.
    panel=panel.sort_values('cutoff').drop_duplicates(['ticker','capture_day'],keep='last')
    if panel.recipe.nunique()!=1:raise ValueError('Mixed feature recipes require separate experiments')
    rows=[]
    for row in panel.to_dict('records'):
        symbol=row['ticker'];p=Path(prices)/(symbol+'.parquet')
        if not p.exists():continue
        if symbol not in cache:
            before=sha(p);s=pd.read_parquet(p).Close;s.index=pd.to_datetime(s.index,utc=True)
            if sha(p)!=before:raise ValueError('Outcome prices changed during read')
            if s.index.has_duplicates or not ((s>0)&np.isfinite(s)).all():raise ValueError('Invalid outcome prices')
            cache[symbol]=s.sort_index();price_hashes[symbol]=before
        s=cache[symbol]
        # Conservative execution assumption: enter at NEXT UTC-date session close.
        future=s[s.index > row['cutoff'].normalize()]
        if len(future)<=horizon:continue
        if not all(pd.notna(row.get(c)) for c in TECHNICAL):continue
        row.update(entry_date=future.index[0],label_end=future.index[horizon],target=future.iloc[horizon]/future.iloc[0]-1)
        rows.append(row)
    return pd.DataFrame(rows),dict(snapshot_sha256=manifests,price_sha256=price_hashes)


def predict(train,test,columns,alpha=10.):
    x=train[columns].to_numpy(dtype=float);z=test[columns].to_numpy(dtype=float)
    med=np.array([np.median(c[np.isfinite(c)]) if np.isfinite(c).any() else 0. for c in x.T])
    missing=~np.isfinite(x);test_missing=~np.isfinite(z)
    x=np.where(missing,med,x);z=np.where(test_missing,med,z)
    mean=x.mean(axis=0);std=x.std(axis=0);std=np.where(std>1e-12,std,1.)
    x=np.column_stack([(x-mean)/std,missing.astype(float),np.ones(len(x))])
    z=np.column_stack([(z-mean)/std,test_missing.astype(float),np.ones(len(z))])
    penalty=np.eye(x.shape[1])*alpha;penalty[-1,-1]=0
    beta=np.linalg.solve(x.T@x+penalty,x.T@train.target.to_numpy(dtype=float))
    return z@beta


def evaluate(panel, *, min_train_days=40, min_test_days=10, block_days=5):
    policy=dict(min_train_days=min_train_days,min_test_days=min_test_days,test_block_days=block_days,
                target='next-session-close to fifth subsequent session close return',
                model='ridge alpha=10 fixed; train-only imputation/scaling; missing indicators',
                selection='same eligible rows for every ablation; no hyperparameter selection',
                production_changed=False)
    if panel.empty:return dict(status='awaiting-forward-outcomes',labeled_rows=0,policy=policy)
    panel=panel.copy()
    for c in ['cutoff','entry_date','label_end']:panel[c]=pd.to_datetime(panel[c],utc=True)
    if not (panel.cutoff < panel.entry_date).all() or not (panel.entry_date < panel.label_end).all():
        raise ValueError('Invalid label timing')
    dates=sorted(panel.entry_date.unique());folds=[];predictions=[]
    variants={'technical_baseline':TECHNICAL}
    variants.update({'+ '+k:TECHNICAL+v for k,v in GROUPS.items()})
    variants['+ all_fa']=TECHNICAL+sum(GROUPS.values(),[])
    for offset in range(min_train_days,len(dates),block_days):
        test_dates=dates[offset:offset+block_days];test=panel[panel.entry_date.isin(test_dates)]
        first_cutoff=test.cutoff.min()
        train=panel[(panel.entry_date<test_dates[0])&(panel.label_end<first_cutoff)]
        if train.entry_date.nunique()<min_train_days:continue
        folds.append(dict(train_rows=len(train),test_rows=len(test),train_label_end=train.label_end.max().isoformat(),
                          first_test_cutoff=first_cutoff.isoformat(),test_start=str(test_dates[0]),test_end=str(test_dates[-1])))
        for name,cols in variants.items():
            pred=predict(train,test,cols)
            predictions.extend(dict(variant=name,date=r.entry_date,pred=float(p),target=float(r.target)) for r,p in zip(test.itertuples(),pred))
    out=dict(policy=policy,labeled_rows=len(panel),labeled_days=len(dates),folds=folds)
    if not predictions or len(set(r['date'] for r in predictions))<min_test_days:
        return dict(out,status='insufficient-purged-history',required_test_days=min_test_days)
    scores={}
    for name in variants:
        frame=pd.DataFrame([r for r in predictions if r['variant']==name]);ics=[]
        for _,g in frame.groupby('date'):
            if len(g)>=3 and g.pred.nunique()>1 and g.target.nunique()>1:ics.append(float(g.pred.rank().corr(g.target.rank())))
        scores[name]=dict(rows=len(frame),test_days=frame.date.nunique(),mae=float((frame.pred-frame.target).abs().mean()),
                         direction_accuracy=float(((frame.pred>0)==(frame.target>0)).mean()),mean_daily_rank_ic=float(np.mean(ics)) if ics else None)
    return dict(out,status='evaluated-experimental-only',metrics=scores,
                limitation='Forecast diagnostics only; no costs, execution simulation, significance claim or production promotion.')


def run(cfg):
    from datetime import datetime,timezone
    from fa.monthly import locked
    from scripts.job_receipts import write
    with locked(Path(cfg['prices'])/'.prices.lock'):
        panel,evidence=load_panel(cfg['enrichment_snapshots'],cfg['prices'])
    result=evaluate(panel);result['evidence']=evidence;result['at']=datetime.now(timezone.utc).isoformat()
    folder=Path(cfg['enrichment_reports']);folder.mkdir(parents=True,exist_ok=True)
    target=folder/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    write(target,result)
    return dict(report=str(target),**result)
