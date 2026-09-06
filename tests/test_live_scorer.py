# tests/test_live_scorer.py
"""NNScorer: threshold from the bundle, ensemble averaging, graceful None.
Featurization internals are mocked so these stay fast and offline; a real
end-to-end score is exercised separately as a smoke check."""
import itertools
import json

import pandas as pd
import pytest

from nn_meta import config
from nn_meta.live import scorer as sc
from nn_meta.live.scanner import Signal




def _sig():
    return Signal(symbol="SPY", strategy="rsi", direction=0, right="C",
                  bar_ts=pd.Timestamp("2026-06-10 15:00"), dte=10,
                  spot=600.0, param_label="entry=40")


def _scorer(monkeypatch, tmp_path):
    from nn_meta.feature_contract import CONTRACT_VERSION
    final = tmp_path / "final"
    final.mkdir()
    (final / "ensemble_config.json").write_text(json.dumps({
        "threshold": .55, "run_ids": ["r1", "r2"],
        "feature_contract_version": CONTRACT_VERSION}))
    monkeypatch.setattr(config, "MODEL_FINAL_DIR", final)
    monkeypatch.setattr(sc, "load_spec", lambda: {"symbols": {}})
    # avoid loading the real surface parquet / provider in unit tests
    monkeypatch.setattr(sc, "load_surface_features", lambda: pd.DataFrame())
    monkeypatch.setattr(sc, "get_provider", lambda **kw: object())
    return sc.NNScorer()


class TestRunDirResolution:
    def test_falls_back_to_model_final(self, tmp_path, monkeypatch):
        # deployed hosts have no runs/ — only the committed model_final/
        monkeypatch.setattr(config, "RUNS_DIR", tmp_path / "runs")
        monkeypatch.setattr(config, "MODEL_FINAL_DIR", tmp_path / "final")
        (tmp_path / "final" / "rid").mkdir(parents=True)
        (tmp_path / "final" / "rid" / "scaler.json").write_text("{}")
        from nn_meta.select_meta import resolve_run_dir
        assert resolve_run_dir("rid") == tmp_path / "final" / "rid"

    def test_prefers_runs_dir_when_present(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "RUNS_DIR", tmp_path / "runs")
        monkeypatch.setattr(config, "MODEL_FINAL_DIR", tmp_path / "final")
        (tmp_path / "runs" / "rid").mkdir(parents=True)
        (tmp_path / "runs" / "rid" / "scaler.json").write_text("{}")
        from nn_meta.select_meta import resolve_run_dir
        assert resolve_run_dir("rid") == tmp_path / "runs" / "rid"


class TestNNScorer:
    def test_threshold_from_bundle(self, monkeypatch, tmp_path):
        s = _scorer(monkeypatch, tmp_path)
        expected = json.loads(
            (config.MODEL_FINAL_DIR / "ensemble_config.json").read_text())["threshold"]
        assert s.threshold == float(expected)

    def test_averages_ensemble_predictions(self, monkeypatch, tmp_path):
        s = _scorer(monkeypatch, tmp_path)
        monkeypatch.setattr(s, "_feature_row", lambda sig, bars: pd.DataFrame([{}]))
        # each run_id returns a constant; mean should be their average
        # (cycle so the mock never runs dry regardless of ensemble size)
        vals = itertools.cycle([0.6, 0.8, 0.4, 1.0, 0.2])
        monkeypatch.setattr(sc, "predict_rows", lambda rid, row: [next(vals)])
        out = s(_sig(), pd.DataFrame())
        assert 0.0 <= out <= 1.0

    def test_none_when_no_feature_row(self, monkeypatch, tmp_path):
        s = _scorer(monkeypatch, tmp_path)
        monkeypatch.setattr(s, "_feature_row", lambda sig, bars: None)
        assert s(_sig(), pd.DataFrame()) is None

    def test_none_on_featurize_error(self, monkeypatch, tmp_path):
        s = _scorer(monkeypatch, tmp_path)
        def boom(sig, bars):
            raise ValueError("boom")
        monkeypatch.setattr(s, "_feature_row", boom)
        assert s(_sig(), pd.DataFrame()) is None


def test_legacy_scorer_refuses_unversioned_bundle(tmp_path, monkeypatch):
    final = tmp_path / "old"
    final.mkdir()
    (final / "ensemble_config.json").write_text(json.dumps({"threshold": .5, "run_ids": []}))
    monkeypatch.setattr(config, "MODEL_FINAL_DIR", final)
    with pytest.raises(ValueError, match="feature contract"):
        sc.NNScorer()


def test_legacy_feature_uses_target_not_executed_strike(tmp_path, monkeypatch):
    import numpy as np
    s = _scorer(monkeypatch, tmp_path)
    s.spec = {"symbols": {"SPY": {"best_strategy": "rsi", "strategies": {
        "rsi": {"params": {}, "dte": 5}}}}}
    sig = _sig()
    bars = pd.DataFrame({"Close": 600.0},
                        index=pd.date_range(end=sig.bar_ts, periods=40, freq="15min"))
    monkeypatch.setattr(config, "EXEC_CONFIG", {**config.EXEC_CONFIG, "MONEYNESS": .02})
    monkeypatch.setattr(sc, "propose_trades", lambda *a: [(sig.bar_ts, None, 0)])
    monkeypatch.setattr(sc, "execute_at_dte", lambda *a: ([{"entry_premium": 3., "strike": 900.}], None))
    monkeypatch.setattr(sc, "technical_features", lambda *a: pd.DataFrame(index=bars.index))
    monkeypatch.setattr(sc, "join_surface_asof", lambda df, surface: df)
    monkeypatch.setattr(sc, "add_context_features", lambda df, surface: df)
    row = s._feature_row(sig, bars)
    assert row.iloc[0].moneyness == pytest.approx(np.log1p(.02))
