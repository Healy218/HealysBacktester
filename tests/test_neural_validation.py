import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from nn_meta.neural_validation import fit_scaler, matrix, validate_fit
from nn_meta import training_jobs as jobs


def test_all_missing_and_single_observation_columns_are_train_only(tmp_path):
    tr = pd.DataFrame({"absent": [np.nan] * 4, "one": [np.nan, 7, np.nan, np.nan],
                       "constant": [2.] * 4, "y": [0, 1, 0, 1], "net_return": [-.1, .2, -.2, .1]})
    va = tr.copy()
    va["absent"] = [1000., -200., 50., 10.]
    features = ["absent", "one", "constant"]
    mean, std, policy = fit_scaler(tr, features)
    assert policy["inactive"] == ["absent"]
    assert mean["absent"] == 0 and std["one"] == 1
    assert (matrix(va, features, mean, std, policy["inactive"])[:, 0] == 0).all()
    prepared = jobs.prepare(tr, va, features, "y", root=tmp_path)
    doc = json.loads((prepared / "arrays.json").read_text(), parse_constant=lambda v: pytest.fail(v))
    assert doc["preprocessing"] == policy
    for split in ["train", "val"]:
        assert np.isfinite(np.load(prepared / f"{split}_x.npy")).all()
        assert (np.load(prepared / f"{split}_x.npy")[:, 0] == 0).all()
    # GBT retains its own missing-value semantics.
    assert np.isnan(np.load(prepared / "train_raw.npy")[:, 0]).all()
    assert np.load(prepared / "val_raw.npy")[0, 0] == 1000


@pytest.mark.parametrize("value", [np.inf, -np.inf])
def test_infinite_features_are_errors_not_imputation(value):
    with pytest.raises(ValueError, match="infinity"):
        fit_scaler(pd.DataFrame({"x": [1., value]}), ["x"])
    with pytest.raises(ValueError, match="infinity"):
        matrix(pd.DataFrame({"x": [value]}), ["x"], pd.Series({"x": 0}), pd.Series({"x": 1}))


def test_float32_overflow_and_legacy_nan_scaler_fail():
    with pytest.raises(ValueError, match="non-finite"):
        matrix(pd.DataFrame({"x": [1e100]}), ["x"], pd.Series({"x": 0}), pd.Series({"x": 1}))
    with pytest.raises(ValueError, match="scaler means"):
        matrix(pd.DataFrame({"x": [np.nan]}), ["x"], pd.Series({"x": np.nan}), pd.Series({"x": 1}))


@pytest.mark.parametrize("defect", ["loss", "val_loss", "weight", "prediction"])
def test_validation_rejects_every_numerical_failure(defect):
    history = SimpleNamespace(history={"loss": [1.], "val_loss": [.9]})
    weight = SimpleNamespace(name="bad", numpy=lambda: np.array([np.nan if defect == "weight" else 1.]))
    model = SimpleNamespace(weights=[weight], predict=lambda x, **kw: np.full((len(x), 1), np.nan if defect == "prediction" else .5))
    if defect in history.history:
        history.history[defect] = [1., np.nan]
    with pytest.raises(ValueError, match="non-finite"):
        validate_fit(model, history, np.ones((4, 1)), head="classifier")


def test_legacy_success_receipt_cannot_reuse_nan_training(tmp_path):
    (tmp_path / "model.keras").write_bytes(b"preserved defective model")
    settings = {"family": "nn", "seed": 0}
    (tmp_path / "complete.json").write_text(json.dumps({"settings": settings, "val_loss": float("nan"),
        "hashes": {"model.keras": jobs.sha(tmp_path / "model.keras")}}))
    before = (tmp_path / "complete.json").read_bytes()
    with pytest.raises(ValueError, match="finite neural validation"):
        jobs.reusable(tmp_path, settings)
    assert (tmp_path / "complete.json").read_bytes() == before


def test_failed_nn_worker_never_commits_success(tmp_path, monkeypatch):
    import tensorflow as tf
    from nn_meta import model as models
    tr = pd.DataFrame({"x": [1., 2., 3., 4.], "y": [0, 1, 0, 1], "net_return": [-.1, .2, -.2, .1]})
    prepared = jobs.prepare(tr, tr, ["x"], "y", root=tmp_path / "arrays")
    out = tmp_path / "worker"; out.mkdir()
    def build(*args):
        model = models.build_magnitude_mlp(1, [2], .001)
        model.fit = lambda *a, **k: SimpleNamespace(history={"loss": [float("nan")], "val_loss": [float("nan")]})
        return model
    monkeypatch.setattr(models, "build_meta_mlp", build)
    with pytest.raises(ValueError, match="non-finite"):
        jobs.worker(prepared, out, "nn", 0, 1, 5)
    assert not (out / "complete.json").exists()
    assert not (out / "model.keras").exists()
    tf.keras.backend.clear_session()


def test_reference_finalizer_persists_the_same_inactive_feature_policy(tmp_path):
    from nn_meta.v4_finalize import _train_nn_seed
    from nn_meta.v4_loader import _load_member, ensemble_score
    rng = np.random.default_rng(31)
    frame = pd.DataFrame({"x": rng.normal(size=80), "absent": np.nan})
    frame["label"] = (frame.x > 0).astype(float)
    frame["net_return"] = frame.x * .1
    _, member = _train_nn_seed(frame.iloc[:60], frame.iloc[60:], features=["x", "absent"],
        label="label", seed=0, epochs=1, run_id="finite", out_dir=tmp_path)
    loaded = _load_member("nn", tmp_path / "finite")
    assert loaded["inactive"] == ["absent"]
    val = frame.iloc[60:].copy(); val["absent"] = 9999.
    np.testing.assert_allclose(ensemble_score("nn", [loaded], val, ["x", "absent"]),
                               ensemble_score("nn", [member], val, ["x", "absent"]))
