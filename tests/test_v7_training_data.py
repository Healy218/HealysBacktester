import numpy as np
import pandas as pd
import pytest

from nn_meta.session_calendar import SessionCalendar
from nn_meta.v7.factorized import MAX_ROWS, write_shard
from nn_meta.v7.rows import schema
from nn_meta.v7.training_data import FoldRows, prepare_fold


def fixture(tmp_path, *, duplicate=False, mutate=None):
    days = pd.bdate_range('2024-05-01', '2024-06-05').strftime('%Y-%m-%d').tolist()
    cal = SessionCalendar(dict(coverage_start=days[0], coverage_end=days[-1],
        sessions=[dict(date=d, open='09:30', close='16:00') for d in days]))
    fold = dict(train_end='2024-05-16', validation_start='2024-05-20', validation_end='2024-05-31')
    starts = ['2024-05-10', '2024-05-15', '2024-05-20', '2024-05-30', '2024-05-09']
    ends = ['2024-05-13', '2024-05-16', '2024-05-21', '2024-06-03', None]
    paths = []
    for part in range(2):
        ids = [f'{0 if duplicate else part}-{i}' for i in range(5)]
        values = np.tile(np.arange(5)[:, None]+part*10., (1, len(schema())))
        values[:, -1] = np.nan
        frame = pd.DataFrame(values, index=ids, columns=schema())
        meta = pd.DataFrame(dict(row_id=ids,
            decision_ns=pd.Series([pd.Timestamp(d+'T15:00Z').value for d in starts], dtype='int64'),
            label_end_ns=pd.Series([pd.Timestamp(d+'T20:00Z').value if d else None for d in ends], dtype='Int64'),
            label_complete=[True]*4+[False], net_return=[-.5+part, .1, .3+part, -.1, np.nan]))
        if mutate:
            mutate(meta)
        path = tmp_path/f'source-{part}'
        write_shard(path, frame, meta, input_identity=f'fixture-{part}')
        paths.append(path)
    return paths, fold, cal


def test_folds_purge_full_settlement_horizon_and_reconcile_every_row(tmp_path):
    paths, fold, cal = fixture(tmp_path)
    report = prepare_fold(paths, fold, cal, tmp_path/'fold', embargo_sessions=2)
    assert report['counts'] == dict(source=10, train=2, validation=2, incomplete=2, outside_or_purged=4)
    train, valid = FoldRows(tmp_path/'fold', 'train'), FoldRows(tmp_path/'fold', 'validation')
    x, y = train.take(np.array([1, 0, 1]))
    np.testing.assert_array_equal(x[:, 0], [10., 0., 10.])
    np.testing.assert_array_equal(y, [.5, -.5, .5])
    assert np.isnan(x[:, -1]).all()
    np.testing.assert_array_equal(valid.take(np.array([0, 1]))[0][:, 0], [2., 12.])
    assert not report['research_ready'] and not report['binned_dataset_memory_verified']
    excluded = pd.read_parquet(tmp_path/'fold/0-excluded.parquet')
    assert excluded.row_id.tolist() == ['0-1', '0-3', '0-4']
    assert excluded.exclusion_reason.tolist() == ['outside_fold_or_purged_horizon']*2+['incomplete_label']
    with pytest.raises(ValueError, match='Bounded'):
        train.take(np.zeros(MAX_ROWS+1, dtype=int))
    with pytest.raises(ValueError, match='Bounded'):
        train.take(np.array([-1]))
    assert prepare_fold(paths, fold, cal, tmp_path/'fold', embargo_sessions=2) == report
    with pytest.raises(ValueError, match='identity mismatch'):
        prepare_fold(list(reversed(paths)), fold, cal, tmp_path/'fold', embargo_sessions=2)


def test_global_duplicate_rows_and_inexact_nanosecond_clocks_are_rejected(tmp_path):
    paths, fold, cal = fixture(tmp_path, duplicate=True)
    with pytest.raises(ValueError, match='Duplicate row identity'):
        prepare_fold(paths, fold, cal, tmp_path/'bad', embargo_sessions=2)
    other = tmp_path/'other'; other.mkdir()
    paths, fold, cal = fixture(other, mutate=lambda m: m.__setitem__('label_end_ns', m.label_end_ns.astype(float)))
    with pytest.raises(ValueError, match='integer label clocks'):
        prepare_fold(paths, fold, cal, other/'bad', embargo_sessions=2)


def test_multishard_lightgbm_reader_matches_dense_and_detects_payload_mutation(tmp_path):
    import lightgbm as lgb
    paths, fold, cal = fixture(tmp_path)
    prepare_fold(paths, fold, cal, tmp_path/'fold', embargo_sessions=2)
    train = FoldRows(tmp_path/'fold', 'train')
    x, y = train.take(np.arange(len(train)))
    params = dict(objective='regression', verbosity=-1, num_threads=1, min_data_in_leaf=1,
                  min_data_in_bin=1, feature_pre_filter=False)
    a = lgb.train(params, lgb.Dataset(train.lightgbm_sequence(), label=y), num_boost_round=2)
    b = lgb.train(params, lgb.Dataset(x, label=y), num_boost_round=2)
    np.testing.assert_allclose(a.predict(x), b.predict(x), atol=1e-12, rtol=0)
    (paths[0]/'chart.npy').write_bytes(b'changed')
    fresh = FoldRows(tmp_path/'fold', 'train')
    with pytest.raises(ValueError, match='integrity'):
        fresh.take(np.array([0]))
