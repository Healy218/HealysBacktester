"""Regression coverage for purged, embargoed temporal label splits."""
import pandas as pd

from nn_meta.temporal_validation import assign_purged_splits, expanding_folds


def _rows():
    return pd.DataFrame({
        "entry_ts": pd.to_datetime([
            "2025-01-02", "2025-01-08", "2025-01-11", "2025-01-19",
            "2025-01-22", "2025-01-31",
        ]),
        "exit_ts": pd.to_datetime([
            "2025-01-03",  # safe train
            "2025-01-11",  # train entry, label crosses into validation
            "2025-01-13",  # safe validation
            "2025-01-23",  # validation entry, label crosses into test
            "2025-01-25",  # safe test
            "2025-02-03",  # test label extends past the test end
        ]),
    })


def test_exit_time_purging_rejects_cross_boundary_labels():
    split = assign_purged_splits(
        _rows(), train_start="2025-01-01", val_start="2025-01-10",
        test_start="2025-01-20", test_end="2025-01-31",
    )
    assert split.tolist() == ["train", "purged", "val", "purged", "test", "purged"]


def test_embargo_removes_labels_near_the_next_split():
    rows = pd.DataFrame({
        "entry_ts": pd.to_datetime(["2025-01-02", "2025-01-03"]),
        "exit_ts": pd.to_datetime(["2025-01-08", "2025-01-09"]),
    })
    split = assign_purged_splits(
        rows, train_start="2025-01-01", val_start="2025-01-10",
        test_start="2025-01-20", test_end="2025-01-31", embargo="1D",
    )
    assert split.tolist() == ["train", "purged"]


def test_expanding_folds_have_fold_local_validation_before_oos():
    days = pd.Series(pd.date_range("2025-01-01", periods=20, freq="B"))
    folds = expanding_folds(days, n_folds=3)
    assert len(folds) == 3
    assert all(f.train_start < f.val_start < f.test_start <= f.test_end for f in folds)
    assert [f.test_start for f in folds] == sorted(f.test_start for f in folds)
