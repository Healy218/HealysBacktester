import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from nn_meta.session_calendar import SessionCalendar
from nn_meta.v7.factorized import write_shard
from nn_meta.v7.preprocessing import fit_preprocessing
from nn_meta.v7.rows import schema
from nn_meta.v7.storage import verify
from nn_meta.v7.training_data import prepare_fold
from nn_meta.v7.trials import ROOT, run_pilot, validate_plan


def fixture(tmp_path, *, validation_flip=False):
    rng = np.random.default_rng(11)
    n = 256
    # Repeated informative dimensions, one entirely missing training feature.
    x = np.tile(rng.normal(size=(n, 1)), (1, len(schema()))).astype('float32')
    x[:, -1] = np.nan
    x[128:, -1] = 99.  # validation cannot activate a training-missing NN feature
    returns = .2*x[:, 0]+rng.normal(0, .02, n)
    if validation_flip:
        returns[128:] *= -1
    ids = [f'row-{i}' for i in range(n)]
    decision = [pd.Timestamp(('2024-05-10' if i < 128 else '2024-05-20')+'T15:00Z').value for i in range(n)]
    ends = [t+60*10**9 for t in decision]
    meta = pd.DataFrame(dict(row_id=ids, decision_ns=decision, label_end_ns=ends,
                             label_complete=True, net_return=returns))
    write_shard(tmp_path/'rows', pd.DataFrame(x, index=ids, columns=schema()), meta, input_identity='synthetic-test')
    days = pd.bdate_range('2024-05-01', '2024-05-31').strftime('%Y-%m-%d').tolist()
    cal = SessionCalendar(dict(coverage_start=days[0], coverage_end=days[-1],
        sessions=[dict(date=d, open='09:30', close='16:00') for d in days]))
    fold = dict(train_end='2024-05-16', validation_start='2024-05-20', validation_end='2024-05-31')
    prepare_fold([tmp_path/'rows'], fold, cal, tmp_path/'fold', embargo_sessions=2)
    fit_preprocessing(tmp_path/'fold', tmp_path/'preprocessing', reserve_bytes=0)
    plan = json.loads((ROOT/'docs/specs/V7_MODEL_TRIALS_20260916.json').read_text())
    plan.update(gbt_rounds=4, nn_epochs=2, batch_size=32)
    (tmp_path/'plan.json').write_text(json.dumps(plan))
    return tmp_path/'fold', tmp_path/'preprocessing', tmp_path/'plan.json'


def test_predeclared_all_objectives_and_identical_row_baselines(tmp_path):
    fold, prep, plan = fixture(tmp_path)
    document = validate_plan(json.loads(plan.read_text()))
    assert len(document['trials']) == 21
    for objective in ('win', 'weighted_win', 'return_huber'):
        trial_id = 'constant-'+objective
        report = run_pilot(fold, prep, plan, trial_id, tmp_path/trial_id, reserve_bytes=0)
        pred = np.load(tmp_path/trial_id/'validation_predictions.npy')
        targets = np.load(tmp_path/trial_id/'train_targets.npy')
        weights = np.load(tmp_path/trial_id/'train_weights.npy')
        np.testing.assert_allclose(pred, np.average(targets, weights=weights), rtol=1e-6)
        assert len(pred) == report['validation_rows'] == report['training_rows'] == 128
        assert report['model_reload_verified'] and report['calibration'] == 'none'
        assert not report['validation_fit_or_early_stop'] and not report['research_ready']
        assert not report['portfolio_performance_evaluated']
        assert report == run_pilot(fold, prep, plan, trial_id, tmp_path/trial_id, reserve_bytes=0)
    with pytest.raises(ValueError, match='predeclared'):
        run_pilot(fold, prep, plan, 'not-declared', tmp_path/'bad', reserve_bytes=0)


@pytest.mark.parametrize('objective', ['win', 'weighted_win', 'return_huber'])
def test_actual_gbt_finite_deterministic_reload_and_resume_rejects_changed_source(tmp_path, objective):
    fold, prep, plan = fixture(tmp_path)
    trial_id = 'gbt-'+objective+'-11'
    a = run_pilot(fold, prep, plan, trial_id, tmp_path/'a', reserve_bytes=0)
    run_pilot(fold, prep, plan, trial_id, tmp_path/'b', reserve_bytes=0)
    first, second = (np.load(tmp_path/p/'validation_predictions.npy') for p in ('a', 'b'))
    np.testing.assert_array_equal(first, second)
    assert np.ptp(first) > 0 and a['binned_dataset']['process_peak_rss_bytes'] > 0
    assert a['model_reload_verified'] and not a['full_resource_gate_passed']
    (tmp_path/'rows/chart.npy').write_bytes(b'changed')
    with pytest.raises(ValueError, match='integrity'):
        run_pilot(fold, prep, plan, trial_id, tmp_path/'a', reserve_bytes=0)


def test_pilot_failure_records_declaration_and_blocks_stale_plan_and_wrong_preprocessing(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import shutil
    fold, prep, plan = fixture(tmp_path)
    monkeypatch.setattr(shutil, 'disk_usage', lambda p: SimpleNamespace(free=0))
    with pytest.raises(ValueError, match='Insufficient disk'):
        run_pilot(fold, prep, plan, 'constant-win', tmp_path/'failed', reserve_bytes=0)
    partial, = tmp_path.glob('failed.partial-*')
    assert (partial/'declaration.json').exists() and not (partial/'complete.json').exists()
    monkeypatch.undo()
    run_pilot(fold, prep, plan, 'constant-win', tmp_path/'good', reserve_bytes=0)
    doc = json.loads(plan.read_text()); doc['gbt_rounds'] += 1
    plan.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match='identity mismatch'):
        run_pilot(fold, prep, plan, 'constant-win', tmp_path/'good', reserve_bytes=0)
    other = tmp_path/'other'; other.mkdir()
    _, other_prep, _ = fixture(other)
    with pytest.raises(ValueError, match='another fold'):
        run_pilot(fold, other_prep, plan, 'constant-win', tmp_path/'bad', reserve_bytes=0)


def test_actual_nn_all_objectives_finite_deterministic_and_reload(tmp_path):
    fold, prep, plan = fixture(tmp_path)
    # Fresh process bounds TensorFlow's pools before initialization, as the CLI does.
    code = '''
import os
os.environ['CUDA_VISIBLE_DEVICES']='-1'
os.environ['TF_CPP_MIN_LOG_LEVEL']='3'
from nn_meta.v7.runtime import configure_threads
configure_threads(1)
from nn_meta.v7.trials import run_pilot
from pathlib import Path
import sys
root=Path(sys.argv[1])
for objective in ('win','weighted_win','return_huber'):
    for repeat in ('a','b'):
        run_pilot(root/'fold',root/'preprocessing',root/'plan.json','nn-'+objective+'-11',
                  root/(objective+'-'+repeat),reserve_bytes=0)
'''
    result = subprocess.run([sys.executable, '-c', code, str(tmp_path)], cwd=ROOT,
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-6000:]
    for objective in ('win', 'weighted_win', 'return_huber'):
        path = tmp_path/(objective+'-a')
        verify(path)
        a, b = (np.load(tmp_path/(objective+'-'+repeat)/'validation_predictions.npy') for repeat in ('a','b'))
        np.testing.assert_array_equal(a, b)
        assert np.isfinite(a).all() and np.ptp(a) > 0
        report = json.loads((path/'report.json').read_text())
        assert report['model_reload_verified'] and not report['validation_fit_or_early_stop']
        losses = json.loads((path/'training_loss.json').read_text())
        assert len(losses) == 2 and all(np.isfinite(x['loss']) for x in losses)


def test_plan_and_full_panel_limits_cannot_silently_change(tmp_path, monkeypatch):
    import nn_meta.v7.trials as module
    fold, prep, plan = fixture(tmp_path)
    document = json.loads(plan.read_text())
    for key, value in [('calibration', 'fit_on_validation'), ('nn_epochs', True),
                       ('selection', 'pick_best_validation')]:
        bad = dict(document, **{key: value})
        with pytest.raises(ValueError):
            validate_plan(bad)
    monkeypatch.setattr(module, 'MAX_ROWS', 100)
    document['batch_size'] = 32
    plan.write_text(json.dumps(document))
    with pytest.raises(ValueError, match='pilot row limit'):
        run_pilot(fold, prep, plan, 'constant-win', tmp_path/'blocked', reserve_bytes=0)


def test_validation_labels_do_not_change_fits_or_preprocessing(tmp_path):
    paths = []
    for name, flip in [('a', False), ('b', True)]:
        root = tmp_path/name; root.mkdir()
        fold, prep, plan = fixture(root, validation_flip=flip)
        run_pilot(fold, prep, plan, 'gbt-weighted_win-11', root/'model', reserve_bytes=0)
        paths.append(root)
    a, b = paths
    np.testing.assert_array_equal(np.load(a/'model/validation_predictions.npy'),
                                  np.load(b/'model/validation_predictions.npy'))
    first, second = [json.loads((p/'preprocessing/report.json').read_text()) for p in paths]
    for key in ['mean', 'std', 'winsor_bounds', 'clipped_absolute_return_mean']:
        assert first[key] == second[key]
    assert json.loads((a/'model/report.json').read_text())['metrics'] != json.loads((b/'model/report.json').read_text())['metrics']


def test_payload_mutation_during_fit_prevents_complete_receipt(tmp_path, monkeypatch):
    import nn_meta.v7.trials as module
    fold, prep, plan = fixture(tmp_path)
    original = module._fit_gbt
    def mutate(*args):
        result = original(*args)
        (prep/'partitioned_train_returns.npy').write_bytes(b'changed while fitting')
        return result
    monkeypatch.setattr(module, '_fit_gbt', mutate)
    with pytest.raises(ValueError, match='integrity'):
        run_pilot(fold, prep, plan, 'gbt-win-11', tmp_path/'rejected', reserve_bytes=0)
    assert not (tmp_path/'rejected').exists()
    partial, = tmp_path.glob('rejected.partial-*')
    assert (partial/'declaration.json').exists() and not (partial/'complete.json').exists()
