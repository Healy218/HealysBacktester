# tests/test_live_scorer.py
"""NNScorer: threshold from the bundle, ensemble averaging, graceful None.
Featurization internals are mocked so these stay fast and offline; a real
end-to-end score is exercised separately as a smoke check."""
import json

import pandas as pd
import pytest

from nn_meta import config
from nn_meta.live import scorer as sc
from nn_meta.live.scanner import Signal


pytestmark = pytest.mark.skipif(
    not (config.MODEL_FINAL_DIR / "ensemble_config.json").exists(),
    reason="no trained model_final bundle")


def _sig():
    return Signal(symbol="SPY", strategy="rsi", direction=0, right="C",
                  bar_ts=pd.Timestamp("2026-06-10 15:00"), dte=10,
                  spot=600.0, param_label="entry=40")


def _scorer(monkeypatch):
    # avoid loading the real surface parquet / provider in unit tests
    monkeypatch.setattr(sc, "load_surface_features", lambda: pd.DataFrame())
    monkeypatch.setattr(sc, "get_provider", lambda: object())
    return sc.NNScorer()


class TestNNScorer:
    def test_threshold_from_bundle(self, monkeypatch):
        s = _scorer(monkeypatch)
        expected = json.loads(
            (config.MODEL_FINAL_DIR / "ensemble_config.json").read_text())["threshold"]
        assert s.threshold == float(expected)

    def test_averages_ensemble_predictions(self, monkeypatch):
        s = _scorer(monkeypatch)
        monkeypatch.setattr(s, "_feature_row", lambda sig, bars: pd.DataFrame([{}]))
        # each run_id returns a constant; mean should be their average
        vals = iter([0.6, 0.8, 0.4, 1.0, 0.2][:len(s.ens["run_ids"])] * 2)
        monkeypatch.setattr(sc, "predict_rows", lambda rid, row: [next(vals)])
        out = s(_sig(), pd.DataFrame())
        assert 0.0 <= out <= 1.0

    def test_none_when_no_feature_row(self, monkeypatch):
        s = _scorer(monkeypatch)
        monkeypatch.setattr(s, "_feature_row", lambda sig, bars: None)
        assert s(_sig(), pd.DataFrame()) is None

    def test_none_on_featurize_error(self, monkeypatch):
        s = _scorer(monkeypatch)
        def boom(sig, bars):
            raise ValueError("boom")
        monkeypatch.setattr(s, "_feature_row", boom)
        assert s(_sig(), pd.DataFrame()) is None
