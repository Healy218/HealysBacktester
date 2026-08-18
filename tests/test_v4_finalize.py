"""Unit tests for v4_finalize's persistence helpers.

The full training path (tf + lightgbm) is exercised by a manual smoke run;
these cover the crash-safety and ensemble-scoring logic in isolation.
"""
import json
import sys

import numpy as np
import pandas as pd
import pytest

import nn_meta.v4_finalize as fz
from nn_meta import config
from nn_meta.v4_finalize import _atomic_swap, _ensemble_predict


class _FakeNN:
    def __init__(self, value):
        self.value = value

    def predict(self, x, batch_size=None, verbose=0):
        return np.full((len(x), 1), self.value, dtype="float32")


class _FakeGBT:
    def __init__(self, value):
        self.value = value

    def predict_proba(self, x):
        p = np.full(len(x), self.value)
        return np.column_stack([1 - p, p])


def _rows(n=4):
    import pandas as pd
    return pd.DataFrame({f: np.arange(n, dtype="float32") for f in ("a", "b")})


def test_ensemble_predict_averages_gbt_members():
    rows = _rows()
    members = [{"model": _FakeGBT(0.2)}, {"model": _FakeGBT(0.8)}]
    out = _ensemble_predict("gbt", members, rows, ["a", "b"])
    assert np.allclose(out, 0.5)
    assert out.shape == (len(rows),)


def test_ensemble_predict_averages_nn_members():
    import pandas as pd
    rows = _rows()
    mean, std = pd.Series({"a": 0.0, "b": 0.0}), pd.Series({"a": 1.0, "b": 1.0})
    members = [{"model": _FakeNN(0.1), "mean": mean, "std": std},
               {"model": _FakeNN(0.9), "mean": mean, "std": std}]
    out = _ensemble_predict("nn", members, rows, ["a", "b"])
    assert np.allclose(out, 0.5)
    assert out.shape == (len(rows),)


def test_atomic_swap_replaces_existing_bundle(tmp_path):
    final = tmp_path / "model_final_v4"
    final.mkdir()
    (final / "old.txt").write_text("old")
    staging = tmp_path / "model_final_v4.staging"
    staging.mkdir()
    (staging / "new.txt").write_text("new")

    _atomic_swap(staging, final)

    assert (final / "new.txt").read_text() == "new"
    assert not (final / "old.txt").exists()      # old bundle replaced
    assert not staging.exists()                   # staging moved, not copied
    assert not final.with_name(final.name + ".prev").exists()  # backup cleaned


def test_atomic_swap_creates_when_no_existing_bundle(tmp_path):
    final = tmp_path / "model_final_v4"
    staging = tmp_path / "model_final_v4.staging"
    staging.mkdir()
    (staging / "new.txt").write_text("new")

    _atomic_swap(staging, final)

    assert (final / "new.txt").read_text() == "new"
    assert not staging.exists()


# ── main() orchestration: gate + atomic persist, with training/scoring faked ──

def _install_finalize_stubs(monkeypatch, tmp_path, *, eligible: bool):
    """Point finalize at tiny real dataset/spec files and stub the heavy
    training + policy so main()'s persist/gate orchestration runs fast."""
    dataset = tmp_path / "meta.parquet"
    n = 8
    pd.DataFrame({
        "symbol": ["SPY"] * n, "entry_ts": pd.date_range("2025-01-02", periods=n),
        "exit_ts": pd.date_range("2025-01-03", periods=n),
        "executed": [True] * n, "net_return": np.linspace(-0.1, 0.3, n),
    }).to_parquet(dataset)
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps({"config_hash": "test-hash"}))

    monkeypatch.setattr(config, "META_DATASET_PARQUET", dataset)
    monkeypatch.setattr(config, "BASELINE_SPEC_JSON", spec_path)
    monkeypatch.setattr(fz.config, "META_DATASET_PARQUET", dataset)
    monkeypatch.setattr(fz.config, "BASELINE_SPEC_JSON", spec_path)
    monkeypatch.setattr(fz, "FINAL_DIR", tmp_path / "model_final_v4")
    monkeypatch.setattr(fz, "load_spec", lambda: {"config_hash": "test-hash"})

    def fake_split(ds, val_fraction, embargo):
        s = pd.Series("train", index=ds.index, dtype="object")
        s.iloc[len(ds) // 2:] = "val"
        return s
    monkeypatch.setattr(fz, "_final_split", fake_split)

    class _Stub:
        def predict(self, rows):
            return np.full(len(rows), 0.6)
    monkeypatch.setattr(fz, "fit_gbt", lambda *a, **k: _Stub())

    def fake_train_gbt(train, val, *, features, label, seed, n_estimators,
                       run_id, out_dir):
        run_dir = out_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "model.joblib").write_bytes(b"stub-weights")
        (run_dir / "params.json").write_text("{}")
        return ({"run_id": run_id, "files": ["model.joblib", "params.json"]},
                {"model": None})
    monkeypatch.setattr(fz, "_train_gbt_seed", fake_train_gbt)
    monkeypatch.setattr(fz, "_ensemble_predict",
                        lambda *a, **k: np.full(4, 0.6))

    policy = {"mode": "rank", "threshold": 0.55, "eligible": eligible,
              "baseline_return": 0.05, "family": "gbt",
              "metrics": {"total_return": 0.3 if eligible else -0.26,
                          "n_kept": 25 if eligible else 3, "max_drawdown": 0.2,
                          "per_trade_sharpe": 1.0},
              "candidate_sharpes": [1.0]}

    def fake_choose_policy(rows, pred, spec, mark_stream=None, **k):
        p = dict(policy)
        p["selection_basis"] = "ledger" if mark_stream is not None else "shared_sim"
        return p
    monkeypatch.setattr(fz, "choose_policy", fake_choose_policy)

    monkeypatch.setattr(sys, "argv",
                        ["v4_finalize", "--models", "gbt",
                         "--select-seeds", "0", "--final-seeds", "0,1"])
    return tmp_path / "model_final_v4"


def test_main_persists_eligible_bundle_with_ensemble_operating_point(monkeypatch, tmp_path):
    final = _install_finalize_stubs(monkeypatch, tmp_path, eligible=True)
    fz.main()

    assert final.exists() and not final.with_name(final.name + ".staging").exists()
    cfg = json.loads((final / "ensemble_config.json").read_text())
    assert cfg["eligible"] is True
    # the persisted operating point is the RE-VALIDATED ensemble policy
    assert cfg["mode"] == "rank" and cfg["threshold"] == 0.55
    assert cfg["operating_point_source"] == "full-ensemble revalidation"
    assert cfg["run_ids"] == ["v4-gbt-xs-s0", "v4-gbt-xs-s1"]
    manifest = json.loads((final / "manifest.json").read_text())
    # manifest covers the trained files + ensemble_config, not just inputs
    assert "ensemble_config.json" in manifest["output_artifacts"]
    assert any("model.joblib" in k for k in manifest["output_artifacts"])
    assert (final / "v4-gbt-xs-s0" / "model.joblib").exists()


def test_main_marks_flag_routes_both_selection_passes_through_the_ledger(monkeypatch, tmp_path):
    """--marks must reach BOTH choose_policy call sites (cheap-seed family pick
    and full-ensemble operating point), and the bundle must record it."""
    final = _install_finalize_stubs(monkeypatch, tmp_path, eligible=True)
    marks = tmp_path / "meta.marks.parquet"
    marks.write_bytes(b"stub")  # existence only; loading is stubbed below
    sentinel = pd.DataFrame({"mark": [1.0]})
    monkeypatch.setattr(fz, "option_b_blockers",
                        lambda cols, mark_stream_exists: [])
    monkeypatch.setattr(fz, "load_mark_stream", lambda p: sentinel)

    inner = fz.choose_policy
    seen: list = []
    def capture(rows, pred, spec, mark_stream=None, **k):
        seen.append(mark_stream)
        return inner(rows, pred, spec, mark_stream=mark_stream, **k)
    monkeypatch.setattr(fz, "choose_policy", capture)
    monkeypatch.setattr(sys, "argv",
                        ["v4_finalize", "--models", "gbt",
                         "--select-seeds", "0", "--final-seeds", "0,1",
                         "--marks", str(marks)])

    fz.main()

    assert len(seen) == 2 and all(s is sentinel for s in seen)
    cfg = json.loads((final / "ensemble_config.json").read_text())
    assert cfg["selection_basis"] == "ledger"


def test_main_marks_flag_fails_closed_on_blockers(monkeypatch, tmp_path):
    """A dataset that can't support the ledger must stop finalize BEFORE any
    training, mirroring v4_evaluate's fail-closed contract."""
    _install_finalize_stubs(monkeypatch, tmp_path, eligible=True)
    marks = tmp_path / "meta.marks.parquet"
    marks.write_bytes(b"stub")
    monkeypatch.setattr(fz, "option_b_blockers",
                        lambda cols, mark_stream_exists: ["missing provenance columns"])
    monkeypatch.setattr(sys, "argv",
                        ["v4_finalize", "--models", "gbt",
                         "--select-seeds", "0", "--final-seeds", "0,1",
                         "--marks", str(marks)])

    with pytest.raises(SystemExit) as exc:
        fz.main()
    assert "missing provenance columns" in str(exc.value)


def test_main_refuses_ineligible_and_leaves_existing_bundle_untouched(monkeypatch, tmp_path):
    final = _install_finalize_stubs(monkeypatch, tmp_path, eligible=False)
    final.mkdir()
    (final / "SENTINEL").write_text("previously-validated model")

    with pytest.raises(SystemExit) as exc:
        fz.main()
    assert exc.value.code == 1
    # the good bundle survives; no staging/prev debris
    assert (final / "SENTINEL").read_text() == "previously-validated model"
    assert not final.with_name(final.name + ".staging").exists()
    assert not final.with_name(final.name + ".prev").exists()
