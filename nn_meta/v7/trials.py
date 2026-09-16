"""Predeclared bounded model pilots; no full-campaign launch or portfolio verdict.

Feature matrices stream in bounded batches. LightGBM still builds an in-memory
binned dataset; pilot resource observations do not waive the full resource gate.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import resource
import sys
import time

import numpy as np

from nn_meta.v7.factorized import MAX_ROWS
from nn_meta.v7.preprocessing import Preprocessor
from nn_meta.v7.provenance import runtime_manifest
from nn_meta.v7.rows import schema
from nn_meta.v7.storage import identity, receipt, sha, transaction, verify
from nn_meta.v7.training_data import FoldRows

ROOT = Path(__file__).resolve().parents[2]
POLICY = 'v7-predeclared-model-trials-v1'
OBJECTIVES = ('win', 'weighted_win', 'return_huber')


def _pilot_sources():
    # Bind loaded project dependencies, plus every V7 source, without walking
    # archived data trees. New project imports during fit invalidate the guard.
    paths = set((ROOT/'nn_meta/v7').glob('*.py'))
    paths.update([ROOT/'scripts/run_v7_model_pilot.py', ROOT/'requirements.txt'])
    prefixes = ('nn_meta', 'nn_options_signal', 'options', 'portfolio', 'signals',
                'indicators', 'utils', 'v3', 'scripts')
    for name, module in list(sys.modules.items()):
        if name.split('.')[0] not in prefixes or not getattr(module, '__file__', None):
            continue
        path = Path(module.__file__).resolve()
        if path.is_relative_to(ROOT) and path.suffix == '.py':
            paths.add(path)
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(paths)}


class _PilotBinding:
    def __init__(self, *, inputs, declaration):
        self.document = dict(sources=_pilot_sources(), runtime=runtime_manifest(),
            inputs={str(p): sha(p) for p in inputs}, declaration=declaration,
            binding_scope='component-pilot-loaded-project-dependencies-and-v7')

    def finish(self):
        if _pilot_sources() != self.document['sources']:
            raise ValueError('Pilot source/import set changed during fit')
        if any(sha(p) != digest for p, digest in self.document['inputs'].items()):
            raise ValueError('Pilot input changed during fit')
        return dict(self.document, source_and_input_guard='passed')


def validate_plan(plan):
    if (plan.get('schema') != POLICY or plan.get('calibration') != 'none'
            or plan.get('selection') != 'retain_all_no_winner_selection'
            or plan.get('feature_columns') != list(schema())):
        raise ValueError('Unsupported trial policy, calibration or feature declaration')
    trials = plan.get('trials', [])
    if not trials or len({t['id'] for t in trials}) != len(trials):
        raise ValueError('Nonempty unique declared trials required')
    for t in trials:
        if (t['family'] not in ('constant', 'gbt', 'nn') or t['objective'] not in OBJECTIVES
                or type(t['seed']) is not int or not 0 <= t['seed'] < 2**31
                or set(t) != {'id', 'family', 'objective', 'seed'}):
            raise ValueError('Unsupported model trial')
    for key, limit in [('gbt_rounds', 10000), ('nn_epochs', 1000), ('batch_size', MAX_ROWS)]:
        if type(plan.get(key)) is not int or not 1 <= plan[key] <= limit:
            raise ValueError('Invalid declared training budget')
    if type(plan.get('threads')) is not int or plan['threads'] != 1 or plan.get('data_order') != 'fixed_source_order':
        raise ValueError('One inner thread and fixed source order required')
    expected = {'gbt': {'num_leaves': 31, 'learning_rate': .05, 'min_data_in_leaf': 20,
                        'max_bin': 63, 'huber_alpha': .9},
                'nn': {'hidden': [64, 32], 'learning_rate': .001, 'huber_delta': 1.}}
    if plan.get('models') != expected:
        raise ValueError('Unsupported declared model hyperparameters')
    return plan


def _dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n')


def _prediction(values, size, objective):
    result = np.asarray(values, dtype=np.float64).reshape(-1)
    if result.shape != (size,) or not np.isfinite(result).all():
        raise ValueError('Nonfinite or misaligned predictions')
    if objective != 'return_huber' and ((result < 0).any() or (result > 1).any()):
        raise ValueError('Classification prediction outside probability range')
    return result


def _targets(rows, processor, objective, root, batch_size):
    y = np.lib.format.open_memmap(root/'train_targets.npy', mode='w+', dtype='float32', shape=(len(rows),))
    w = np.lib.format.open_memmap(root/'train_weights.npy', mode='w+', dtype='float32', shape=(len(rows),))
    offset = 0
    for _, returns in rows.batches(batch_size):
        target, weight = processor.targets(returns, objective=objective)
        y[offset:offset+len(target)], w[offset:offset+len(target)] = target, weight
        offset += len(target)
    y.flush(); w.flush()
    if offset != len(rows) or not np.isfinite(w.sum(dtype=np.float64)) or w.sum(dtype=np.float64) <= 0:
        raise ValueError('Training target count or total weight invalid')
    if objective != 'return_huber' and not (np.any((y == 0) & (w > 0)) and np.any((y == 1) & (w > 0))):
        raise ValueError('Classification requires positive weight for both training classes')
    return y, w


def _fit_gbt(train, y, weights, plan, trial, temp):
    import lightgbm as lgb
    params = dict(objective='huber' if trial['objective'] == 'return_huber' else 'binary',
        alpha=plan['models']['gbt']['huber_alpha'], num_leaves=31, learning_rate=.05,
        min_data_in_leaf=20, max_bin=63, num_threads=1, verbosity=-1,
        deterministic=True, force_col_wise=True, seed=trial['seed'],
        data_random_seed=trial['seed'], feature_fraction_seed=trial['seed'],
        bagging_seed=trial['seed'], drop_seed=trial['seed'])
    # Raw NaNs remain available to tree missing-value branches. NN uses the
    # separately fitted train-only standardizer; neither sees validation at fit.
    dataset = lgb.Dataset(train.lightgbm_sequence(), label=y, weight=weights,
                          feature_name=list(schema()), params=params)
    started = time.monotonic()
    dataset.construct()
    binned = dict(seconds=time.monotonic()-started,
                  process_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
    model = lgb.train(params, dataset, num_boost_round=plan['gbt_rounds'])
    model.save_model(str(temp/'model.txt'))
    loaded = lgb.Booster(model_file=str(temp/'model.txt'))
    return (lambda x: model.predict(x, num_threads=1),
            lambda x: loaded.predict(x, num_threads=1), binned)


def _fit_nn(train, processor, plan, trial, temp):
    import tensorflow as tf
    tf.config.set_visible_devices([], 'GPU')
    for setter, getter in ((tf.config.threading.set_intra_op_parallelism_threads,
                            tf.config.threading.get_intra_op_parallelism_threads),
                           (tf.config.threading.set_inter_op_parallelism_threads,
                            tf.config.threading.get_inter_op_parallelism_threads)):
        try:
            setter(1)
        except RuntimeError:
            if getter() != 1:
                raise RuntimeError('NN trials require a fresh process with one TF thread') from None
    tf.keras.backend.clear_session()
    tf.keras.utils.set_random_seed(trial['seed'])
    tf.config.experimental.enable_op_determinism()
    regression = trial['objective'] == 'return_huber'
    model = tf.keras.Sequential([tf.keras.layers.Input(shape=(len(schema()),)),
        tf.keras.layers.Dense(64, activation='relu'), tf.keras.layers.Dense(32, activation='relu'),
        tf.keras.layers.Dense(1, activation='linear' if regression else 'sigmoid')])
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=.001),
        loss=tf.keras.losses.Huber(delta=1.) if regression else tf.keras.losses.BinaryCrossentropy(),
        jit_compile=False)
    losses = []
    for epoch in range(plan['nn_epochs']):
        model.reset_metrics()
        for x, returns in train.batches(plan['batch_size']):
            y, weights = processor.targets(returns, objective=trial['objective'])
            result = model.train_on_batch(processor.transform(x), y[:, None], sample_weight=weights,
                                          return_dict=True)
            if not all(np.isfinite(v).all() for v in result.values()):
                raise ValueError('Nonfinite NN training loss')
        if not all(np.isfinite(v).all() for v in model.get_weights()):
            raise ValueError('Nonfinite NN weights')
        losses.append(dict(epoch=epoch+1, loss=float(result['loss'])))
    _dump(temp/'training_loss.json', losses)
    model.save(temp/'model.keras')
    loaded = tf.keras.models.load_model(temp/'model.keras', compile=False)
    return (lambda x: model(processor.transform(x), training=False).numpy(),
            lambda x: loaded(processor.transform(x), training=False).numpy(), None)


def run_pilot(fold_path, preprocessing_path, plan_path, trial_id, output, *, reserve_bytes=100*1024**3):
    """Run one <=65,536-row-per-split component pilot, never full training.

    Declaration/binding is persisted before fitting; failures retain their partial
    directory. Same-input completed resumption verifies payloads and source state.
    Predictions are in the exact bound validation selection order.
    """
    import shutil
    fold_path, preprocessing_path, plan_path = map(lambda p: Path(p).resolve(),
                                                   (fold_path, preprocessing_path, plan_path))
    plan = validate_plan(json.loads(plan_path.read_text()))
    matches = [t for t in plan['trials'] if t['id'] == trial_id]
    if len(matches) != 1:
        raise ValueError('Trial was not predeclared')
    trial = matches[0]
    if type(reserve_bytes) is not int or reserve_bytes < 0:
        raise ValueError('Nonnegative disk reserve required')
    train, valid = FoldRows(fold_path, 'train'), FoldRows(fold_path, 'validation')
    if max(len(train), len(valid)) > MAX_ROWS:
        raise ValueError('Component pilot row limit exceeded; full training requires readiness')
    processor = Preprocessor(preprocessing_path)
    if (processor.report['sources'].get(str(fold_path/'complete.json')) != sha(fold_path/'complete.json')
            or processor.report['rows'] != len(train)):
        raise ValueError('Preprocessing belongs to another fold')
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    declaration = dict(schema='v7-model-pilot-v1', trial=trial, plan_sha256=sha(plan_path),
        fold=str(fold_path), preprocessing=str(preprocessing_path), calibration='none',
        training_rows=len(train), validation_rows=len(valid), reserve_bytes=reserve_bytes,
        validation_fit_or_early_stop=False, selection='retain_all_no_winner_selection',
        declared_trial_count=len(plan['trials']), research_ready=False)
    binding = _PilotBinding(inputs=[plan_path, fold_path/'complete.json', preprocessing_path/'complete.json'],
                         declaration=declaration)
    run_id = identity(binding.document)
    if Path(output).exists():
        verify(output, expected_identity=run_id)
        # Force input payload verification, including each selected source shard.
        for rows in (train, valid):
            for _ in rows.batches(plan['batch_size']):
                pass
        binding.finish()
        return json.loads((Path(output)/'report.json').read_text())
    started = time.monotonic()
    with transaction(output) as temp:
        _dump(temp/'declaration.json', dict(**declaration, started_at=datetime.now(timezone.utc).isoformat()))
        _dump(temp/'binding-start.json', binding.document)
        required = 8*len(train)+8*len(valid)+16*1024**2
        if shutil.disk_usage(temp).free < reserve_bytes+required:
            raise ValueError('Insufficient disk for model pilot and declared reserve')
        y, weights = _targets(train, processor, trial['objective'], temp, plan['batch_size'])
        if trial['family'] == 'constant':
            constant = float(np.sum(y.astype(np.float64)*weights)/weights.sum(dtype=np.float64))
            _dump(temp/'model.json', dict(constant=constant, objective=trial['objective'],
                fit='weighted_training_target_mean', calibration='none'))
            predict = lambda x: np.full(len(x), constant)
            restored = lambda x: np.full(len(x), json.loads((temp/'model.json').read_text())['constant'])
            binned = None
        elif trial['family'] == 'gbt':
            predict, restored, binned = _fit_gbt(train, y, weights, plan, trial, temp)
        else:
            predict, restored, binned = _fit_nn(train, processor, plan, trial, temp)
        predictions = np.lib.format.open_memmap(temp/'validation_predictions.npy', mode='w+',
                                               dtype='float64', shape=(len(valid),))
        offset, squared, absolute, logloss, brier = 0, 0., 0., 0., 0.
        for x, returns in valid.batches(plan['batch_size']):
            pred = _prediction(predict(x), len(x), trial['objective'])
            reloaded = _prediction(restored(x), len(x), trial['objective'])
            if not np.allclose(pred, reloaded, atol=1e-7, rtol=1e-7):
                raise ValueError('Reloaded model predictions differ')
            predictions[offset:offset+len(pred)] = pred
            offset += len(pred)
            if trial['objective'] == 'return_huber':
                squared += np.square(pred-returns).sum(dtype=np.float64)
                absolute += np.abs(pred-returns).sum(dtype=np.float64)
            else:
                truth = (returns > 0).astype(float)
                clipped = np.clip(pred, 1e-12, 1-1e-12)
                logloss -= (truth*np.log(clipped)+(1-truth)*np.log1p(-clipped)).sum(dtype=np.float64)
                brier += np.square(pred-truth).sum(dtype=np.float64)
        predictions.flush(); del predictions
        if offset != len(valid):
            raise ValueError('Validation prediction count differs')
        metrics = (dict(raw_return_rmse=float(np.sqrt(squared/offset)), raw_return_mae=float(absolute/offset))
                   if trial['objective'] == 'return_huber' else
                   dict(unweighted_logloss=float(logloss/offset), unweighted_brier=float(brier/offset)))
        if not all(np.isfinite(v) for v in metrics.values()):
            raise ValueError('Nonfinite validation metrics')
        report = dict(**declaration, metrics=metrics, prediction_order='bound_validation_selection_order',
            model_reload_verified=True, duration_seconds=time.monotonic()-started,
            process_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
            binned_dataset=binned, full_resource_gate_passed=False,
            portfolio_performance_evaluated=False, multiple_testing_diagnostics_complete=False)
        # Reopen and reverify transitive payloads, not only their receipt files.
        Preprocessor(preprocessing_path)
        for split in ('train', 'validation'):
            for _ in FoldRows(fold_path, split).batches(plan['batch_size']):
                pass
        if shutil.disk_usage(temp).free < reserve_bytes:
            raise ValueError('Disk reserve violated during model pilot')
        _dump(temp/'binding.json', binding.finish())
        _dump(temp/'report.json', report)
        receipt(temp, dict(identity=run_id, research_ready=False))
    return report
