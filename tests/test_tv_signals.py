# tests/test_tv_signals.py
"""TV-derived proposal strategies: generator contract (4-tuple, MultiIndex
param columns, boolean frames) and the sweep → params → single_signals
replay round-trip that the freeze pipeline depends on."""
import numpy as np
import pandas as pd
import pytest

from nn_meta import config, proposals


def _bars(n=400, seed=3):
    rng = np.random.default_rng(seed)
    c = pd.Series(100 + rng.normal(0, 1, n).cumsum(),
                  index=pd.date_range("2025-01-02 14:30", periods=n,
                                      freq="15min"))
    return pd.DataFrame({"Open": c.shift(1).fillna(c), "High": c + 0.4,
                         "Low": c - 0.4, "Close": c, "Volume": 1000.0})


NEW_STRATEGIES = ["supertrend", "tv_rating", "squeeze"]


@pytest.mark.parametrize("strategy", NEW_STRATEGIES)
class TestGeneratorContract:
    def test_sweep_shapes_and_types(self, strategy):
        bars = _bars()
        ent, ext, s_ent, s_ext = proposals.sweep_signals(strategy, bars)
        assert ent.shape == ext.shape and len(ent) == len(bars)
        assert ent.dtypes.eq(bool).all() and not ent.isna().any().any()
        assert ent.shape[1] > 1                    # a real grid
        assert all(ent.columns.names)              # named param levels
        if config.ENABLE_SHORTING:
            assert s_ent.shape == ent.shape

    def test_single_replays_sweep_column(self, strategy):
        bars = _bars()
        ent, *_ = proposals.sweep_signals(strategy, bars)
        col = ent.columns[len(ent.columns) // 2]
        params = {n: (int(v) if float(v) == int(v) else float(v))
                  for n, v in zip(ent.columns.names, col)}
        single_ent, *_ = proposals.single_signals(strategy, bars, params)
        pd.testing.assert_series_equal(
            single_ent.iloc[:, 0], ent[col], check_names=False)


class TestPoolConfig:
    def test_default_pool_is_deployed_v2(self):
        # the live v2.2 ensemble's feature schema depends on this exact list
        assert config.POOL == "v2"
        assert config.PROPOSAL_STRATEGIES == ["ma", "macd", "rsi", "volume"]
        assert config.ARTIFACTS.name == "artifacts"
        assert config.MODEL_FINAL_DIR.name == "model_final"

    def test_v3_pool_is_superset(self):
        assert set(config.PROPOSAL_STRATEGIES) < set(config.PROPOSAL_STRATEGIES_V3)
        assert set(NEW_STRATEGIES) <= set(config.PROPOSAL_STRATEGIES_V3)
        for s in NEW_STRATEGIES:
            assert s in config.SWEEP_GRIDS

    def test_v3_env_switch_suffixes_dirs(self, monkeypatch):
        import importlib
        monkeypatch.setenv("NN_META_POOL", "v3")
        try:
            importlib.reload(config)
            assert config.PROPOSAL_STRATEGIES == config.PROPOSAL_STRATEGIES_V3
            assert config.ARTIFACTS.name == "artifacts_v3"
            assert config.RUNS_DIR.name == "runs_v3"
            assert config.MODEL_FINAL_DIR.name == "model_final_v3"
            assert config.DATA_CACHE.name == "data_cache"   # shared
        finally:
            monkeypatch.delenv("NN_META_POOL")
            importlib.reload(config)
        assert config.PROPOSAL_STRATEGIES == ["ma", "macd", "rsi", "volume"]
