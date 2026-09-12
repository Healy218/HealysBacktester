"""Predeclared, research-only objective comparisons; never writes a live bundle.

Train and early-stop on purged temporal partitions. Test metrics are a single
readout, not a search criterion. Simultaneous same-symbol/direction proposals
share one event's training weight across strategy and DTE variants.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from nn_meta import config
from nn_meta.training_jobs import _json, sha


def event_weights(rows):
    keys = ['symbol', 'entry_ts', 'dir_short']
    if rows[keys].isna().any().any():
        raise ValueError('Event identity must be complete')
    sizes = rows.groupby(keys, observed=True, dropna=False)['symbol'].transform('size')
    weights = 1.0 / sizes.to_numpy(dtype=float)
    return weights / weights.mean()


def run(dataset, output, *, estimators=600, threads=2, label='label_excess'):
    import joblib
    from lightgbm import LGBMClassifier, LGBMRegressor, early_stopping, log_evaluation
    from sklearn.metrics import log_loss, brier_score_loss, roc_auc_score, mean_pinball_loss
    from nn_meta.baseline import load_spec
    from nn_meta.feature_contract import require_current_dataset
    from nn_meta.build_meta_dataset import V4_META_FEATURES
    from nn_meta.temporal_validation import assign_purged_splits
    features = V4_META_FEATURES
    columns = list(dict.fromkeys([*features, 'symbol', 'entry_ts', 'exit_ts', label, 'net_return']))
    ds = pd.read_parquet(dataset, columns=columns)
    spec = load_spec()
    require_current_dataset(ds, spec)
    if pd.Timestamp(config.VAL_START) <= pd.Timestamp(spec['train_window'][1]):
        raise ValueError('Validation overlaps the frozen proposal optimization')
    split = assign_purged_splits(ds, train_start=config.TRAIN_START, val_start=config.VAL_START,
        test_start=config.TEST_START, test_end=config.TEST_END, embargo='1D')
    # Honor the original disjoint train/val windows as well as exit-time purge.
    dates = ds.entry_ts.dt.normalize()
    split.loc[((split == 'train') & (dates > config.TRAIN_END)) |
              ((split == 'val') & (dates > config.VAL_END))] = 'purged'
    frames = {s: ds.loc[(split == s) & ds[label].notna() & ds.net_return.notna()]
              for s in ['train', 'val', 'test']}
    if any(f.empty for f in frames.values()):
        raise ValueError('Empty experiment partition')
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    plan = {'version': 1, 'research_only': True, 'dataset_sha256': sha(dataset),
        'source_sha256': sha(__file__), 'features': features, 'estimators': estimators,
        'threads': threads, 'seed': 0, 'label':label, 'quantile': 0.10, 'embargo': '1D',
        'events': ['symbol', 'entry_ts', 'dir_short'],
        'test_used_for_selection': False,
        'split': {s: {'rows':len(f), 'first':str(f.entry_ts.min()), 'last':str(f.entry_ts.max()),
                      'last_exit':str(f.exit_ts.max())} for s,f in frames.items()}}
    if (output/'plan.json').exists() and json.loads((output/'plan.json').read_text()) != plan:
        raise ValueError('Experiment plan changed; use a fresh output directory')
    _json(output/'plan.json', plan)
    tr, va, te = [frames[s] for s in ['train', 'val', 'test']]
    kw = dict(n_estimators=estimators, learning_rate=.02, num_leaves=31, subsample=.8,
              colsample_bytree=.8, min_child_samples=200, reg_lambda=1., random_state=0,
              n_jobs=threads, verbosity=-1)
    results = {}
    for name in ['baseline', 'event_balanced', 'downside_q10']:
        is_quantile = name == 'downside_q10'
        model = LGBMRegressor(objective='quantile', alpha=.1, **kw) if is_quantile else LGBMClassifier(**kw)
        target = 'net_return' if is_quantile else label
        model.fit(tr[features], tr[target], eval_set=[(va[features],va[target])],
            sample_weight=event_weights(tr) if name == 'event_balanced' else None,
            eval_metric='quantile' if is_quantile else 'auc',
            callbacks=[early_stopping(max(10, estimators//10)), log_evaluation(0)])
        joblib.dump(model, output/f'{name}.joblib')
        scores = {}
        for s, f in [('val', va), ('test', te)]:
            if is_quantile:
                pred = model.predict(f[features])
                scores[s] = {'pinball_q10': float(mean_pinball_loss(f[target], pred, alpha=.1)),
                    'fraction_below_prediction': float((f[target].to_numpy() <= pred).mean()),
                    'constant_train_quantile_pinball': float(mean_pinball_loss(f[target],
                        np.full(len(f), tr[target].quantile(.1)), alpha=.1))}
            else:
                pred = model.predict_proba(f[features])[:,1]
                scores[s] = {'log_loss':float(log_loss(f[target], pred, labels=[0,1])),
                    'brier':float(brier_score_loss(f[target], pred)),
                    'auc':float(roc_auc_score(f[target], pred)) if f[target].nunique()==2 else None,
                    'event_balanced_brier':float(brier_score_loss(f[target], pred, sample_weight=event_weights(f)))}
        results[name] = {'best_iteration':model.best_iteration_, 'metrics':scores,
                         'sha256':sha(output/f'{name}.joblib')}
        print(json.dumps({name:results[name]}), flush=True)
        _json(output/'results.partial.json', results)
    _json(output/'results.json', {'complete':True, 'plan_sha256':sha(output/'plan.json'),
        'models':results, 'verdict':'Research metrics only; portfolio validation and separate promotion review required.'})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset', type=Path, default=config.META_DATASET_PARQUET)
    p.add_argument('--output', type=Path, default=config.REPORTS_DIR/'objective-comparisons')
    p.add_argument('--estimators', type=int, default=600)
    p.add_argument('--threads', type=int, default=2)
    a = p.parse_args(); run(a.dataset, a.output, estimators=a.estimators, threads=a.threads)


if __name__ == '__main__':
    main()
