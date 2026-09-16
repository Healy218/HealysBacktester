import numpy as np
import pytest
from nn_meta.v7.preprocessing import Preprocessor, fit_preprocessing, merge_moments
from nn_meta.v7.training_data import prepare_fold
from tests.test_v7_training_data import fixture


def test_streaming_moments_match_dense_with_missing_constant_and_large_offset():
    rng = np.random.default_rng(2022)
    values = rng.normal(size=(2500, 4))
    values[:, 0] += 1e6
    values[:, 1] = np.nan
    values[:, 2] = 5.
    values[::4, 3] = np.nan
    count, mean, m2 = np.zeros(4, dtype=np.int64), np.zeros(4), np.zeros(4)
    for part in np.array_split(values, 11):
        count, mean, m2 = merge_moments(count, mean, m2, part)
    assert count.tolist() == [2500, 0, 2500, 1875]
    np.testing.assert_allclose(mean[[0,2,3]], np.nanmean(values[:, [0,2,3]], axis=0), rtol=1e-12)
    np.testing.assert_allclose(m2[[0,2,3]]/(count[[0,2,3]]-1), np.nanvar(values[:, [0,2,3]], axis=0, ddof=1), atol=1e-10)
    with pytest.raises(ValueError, match='finite-or-missing'):
        merge_moments(count, mean, m2, np.array([[np.inf]*4]))


def test_preprocessing_fits_only_train_and_exact_quantiles_without_validation(tmp_path):
    paths, fold, calendar = fixture(tmp_path)
    prepare_fold(paths, fold, calendar, tmp_path/'fold', embargo_sessions=2)
    report = fit_preprocessing(tmp_path/'fold', tmp_path/'preprocessing', batch_size=1, reserve_bytes=0)
    assert report['rows'] == 2 and report['validation_used'] is False
    np.testing.assert_allclose(report['winsor_bounds'], np.quantile([-.5, .5], [.01, .99]))
    assert report['mean'][0] == 5. and report['std'][0] == np.sqrt(50.)
    assert report['counts'][-1] == 0 and report['inactive'][-1]
    processor = Preprocessor(tmp_path/'preprocessing')
    assert fit_preprocessing(tmp_path/'fold', tmp_path/'preprocessing', batch_size=1, reserve_bytes=0) == report
    with pytest.raises(ValueError, match='resume settings differ'):
        fit_preprocessing(tmp_path/'fold', tmp_path/'preprocessing', batch_size=2, reserve_bytes=0)
    x = np.full((1, len(report['mean'])), 20.)
    assert processor.transform(x)[0, -1] == 0.  # validation cannot activate a missing feature
    x[0, 0] = np.nan
    assert processor.transform(x)[0, 0] == 0.
    y, weights = processor.targets(np.array([-2., 0., 1.]), objective='weighted_win')
    np.testing.assert_array_equal(y, [0., 0., 1.])
    np.testing.assert_array_equal(weights, [2., 0., 2.])
    y, _ = processor.targets(np.array([-2., 0., 1.]), objective='return_huber')
    np.testing.assert_allclose(y, [-.49, 0., .49])
    (tmp_path/'preprocessing/partitioned_train_returns.npy').write_bytes(b'changed')
    with pytest.raises(ValueError, match='integrity'):
        Preprocessor(tmp_path/'preprocessing')


def test_target_disk_reserve_is_checked_before_dense_allocation(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import shutil
    paths, fold, calendar = fixture(tmp_path)
    prepare_fold(paths, fold, calendar, tmp_path/'fold', embargo_sessions=2)
    monkeypatch.setattr(shutil, 'disk_usage', lambda path: SimpleNamespace(free=0))
    with pytest.raises(ValueError, match='Insufficient disk'):
        fit_preprocessing(tmp_path/'fold', tmp_path/'blocked', reserve_bytes=0)
    assert not (tmp_path/'blocked/complete.json').exists()
