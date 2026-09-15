import numpy as np
import pandas as pd
import pytest
from nn_meta.v7.factorized import partitions, write_shard, FactorizedRows, training_sequence
from nn_meta.v7.rows import schema


def fixture():
    rng = np.random.default_rng(4)
    frame = pd.DataFrame(index=[f'r{i}' for i in range(200)], columns=schema(), dtype=float)
    for key, names in partitions().items():
        vectors = rng.normal(size=(7, len(names)))
        if key == 'parameters':
            vectors[:, -1] = np.nan
        frame.loc[:, names] = vectors[np.arange(len(frame)) % 7]
    metadata = pd.DataFrame({'row_id': frame.index, 'label_complete': [True] * 150 + [False] * 50})
    return frame, metadata


def test_factorized_round_trip_preserves_nan_order_and_censored_row_metadata(tmp_path):
    rows, metadata = fixture()
    path = tmp_path / 'shard'
    write_shard(path, rows, metadata, input_identity='fixture')
    store = FactorizedRows(path)
    np.testing.assert_array_equal(store.take(np.arange(len(rows))), rows.to_numpy(dtype=np.float32))
    np.testing.assert_array_equal(store.take(np.array([4, 1, 4])), rows.iloc[[4, 1, 4]].to_numpy(dtype=np.float32))
    pd.testing.assert_frame_equal(pd.read_parquet(path / 'metadata.parquet'), metadata)
    assert store.receipt['factorized_payload_bytes'] < store.receipt['float32_dense_payload_bytes'] / 3


def test_sequence_lightgbm_matches_dense_fold_without_loading_heldout_rows(tmp_path):
    import lightgbm as lgb
    rows, metadata = fixture()
    path = tmp_path / 'shard'
    write_shard(path, rows, metadata, input_identity='fixture')
    indices = np.arange(150)
    sequence = training_sequence(path, indices=indices)
    dense = rows.iloc[indices].to_numpy(dtype=np.float32)
    labels = (dense[:, 0] > 0).astype(int)
    params = {'objective': 'binary', 'verbosity': -1, 'num_threads': 1, 'min_data_in_leaf': 2,
              'min_data_in_bin': 1, 'feature_pre_filter': False, 'bin_construct_sample_cnt': 1000}
    a = lgb.train(params, lgb.Dataset(sequence, label=labels), num_boost_round=3)
    b = lgb.train(params, lgb.Dataset(dense, label=labels), num_boost_round=3)
    np.testing.assert_allclose(a.predict(dense), b.predict(dense), rtol=0, atol=1e-12)
    assert len(sequence) == 150


def test_modified_factor_bytes_are_rejected(tmp_path):
    rows, metadata = fixture()
    path = tmp_path / 'shard'
    write_shard(path, rows, metadata, input_identity='fixture')
    (path / 'chart.npy').write_bytes(b'changed')
    with pytest.raises(ValueError, match='integrity'):
        FactorizedRows(path)
