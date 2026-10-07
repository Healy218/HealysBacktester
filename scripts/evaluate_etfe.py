"""Validation-fold portfolio-replay evaluation and declared selection for an ETFE training root."""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nn_meta.etfe import eval_portfolio as ev
from nn_meta.etfe import train as t

KEYS=['ticker','minutes','chart_row','signal_at_ns','right','target_dte','contract']


def labels(e):
    root=(ROOT/e['dataset_manifest']).parent
    return pd.concat([pq.read_table(p,columns=KEYS+['status','target_return','terminal_ns','debit_cents','pnl_cents','quantity']).to_pandas() for p in sorted(root.glob('*-*.parquet'))],ignore_index=True)


def evaluate(train_root,experiment,folds=('2024h2','2025h1','2025h2')):
    e,_=t.load_experiment(experiment);lab=labels(e);rows=[]
    for fold in folds:
        base=None
        for trial in e['trials']:
            p=pd.read_parquet(Path(train_root)/'predictions'/f"{fold}__{trial['id']}.parquet",columns=KEYS+['score'])
            d=p.merge(lab,on=KEYS,how='left')
            if base is None:
                cash=dict(fold=fold,trial='cash',threshold=None,trades=0,blocked=0,total_return=0.0,max_drawdown=0.0,win_rate=None)
                allel=dict(fold=fold,trial='all_eligible',threshold=None,**ev.replay(d.assign(score=0.0),'score',None))
                rows+= [cash,allel];base=allel['total_return']
            if trial['family']=='constant':continue
            for th in e['thresholds'][trial['objective']]:
                r=ev.replay(d,'score',th);rows.append(dict(fold=fold,trial=trial['id'],threshold=th,**r))
    return pd.DataFrame(rows)


def select(df,min_trades=100,max_dd=.20):
    """Declared rule: positive and >= min trades every fold, max DD <= 20%, excess > 0 vs cash and best baseline."""
    base=df[df.trial=='all_eligible'].set_index('fold').total_return
    m=df[~df.trial.isin(['cash','all_eligible'])].copy();m['excess_vs_baseline']=m.total_return-m.fold.map(base).clip(lower=0)
    g=m.groupby(['trial','threshold']).agg(folds=('fold','nunique'),min_trades=('trades','min'),min_return=('total_return','min'),
        max_dd=('max_drawdown','max'),mean_excess=('excess_vs_baseline','mean'),blocked=('blocked','sum'),mean_return=('total_return','mean'))
    g['passes']=(g.folds==3)&(g.min_trades>=min_trades)&(g.min_return>0)&(g.max_dd<=max_dd)&(g.mean_excess>0)&(g.blocked==0)
    return g.sort_values(['passes','mean_excess'],ascending=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True);parser.add_argument('--experiment',type=Path,required=True)
    args=parser.parse_args();df=evaluate(args.root.resolve(),args.experiment.resolve());g=select(df)
    out=args.root.resolve()/'EVALUATION_VALIDATION.json'
    out.write_text(json.dumps(dict(method='portfolio_replay_approximation',folds=df.to_dict('records'),
        selection=g.reset_index().to_dict('records')),indent=1,default=str)+'\n')
    pd.set_option('display.width',200)
    print(df[df.trial.isin(['cash','all_eligible'])].round(4).to_string(index=False))
    print(g.head(12).round(4).to_string())
    print('passing:',int(g.passes.sum()))
