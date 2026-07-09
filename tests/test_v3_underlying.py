# tests/test_v3_underlying.py
"""Stage 2 underlying layer: resample correctness on synthetic 1m data and
universe sanity (no dupes, v2 subset preserved)."""
import numpy as np
import pandas as pd
import pytest

from v3 import config, underlying
from v3.universe import BOOTSTRAP_UNIVERSE, V2_UNIVERSE


@pytest.fixture
def one_m(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "UNDERLYING_DIR", tmp_path)
    idx = pd.date_range("2025-06-02 13:30", periods=390, freq="1min", tz="UTC")
    rng = np.random.default_rng(1)
    c = pd.Series(100 + rng.normal(0, 0.1, 390).cumsum(), index=idx)
    df = pd.DataFrame({"Open": c.shift(1).fillna(c), "High": c + 0.05,
                       "Low": c - 0.05, "Close": c, "Volume": 100.0})
    (tmp_path / "TEST").mkdir()
    df.to_parquet(tmp_path / "TEST" / "2025.parquet")
    return df


class TestResample:
    def test_15m_ohlcv_semantics(self, one_m):
        r = underlying.resample("TEST", "15min")
        assert len(r) == 26                       # 390 / 15
        first = one_m.iloc[:15]
        assert r.iloc[0]["Open"] == first["Open"].iloc[0]
        assert r.iloc[0]["Close"] == first["Close"].iloc[-1]
        assert r.iloc[0]["High"] == first["High"].max()
        assert r.iloc[0]["Low"] == first["Low"].min()
        assert r.iloc[0]["Volume"] == first["Volume"].sum()

    def test_1d_collapses_session(self, one_m):
        assert len(underlying.resample("TEST", "1d")) == 1

    def test_unknown_interval_rejected(self, one_m):
        with pytest.raises(ValueError):
            underlying.resample("TEST", "3min")

    def test_missing_symbol_raises(self, one_m):
        with pytest.raises(FileNotFoundError):
            underlying.load_1m("NOPE")


class TestUniverse:
    def test_no_duplicates_and_sorted(self):
        assert BOOTSTRAP_UNIVERSE == sorted(set(BOOTSTRAP_UNIVERSE))

    def test_v2_universe_is_subset(self):
        assert set(V2_UNIVERSE) <= set(BOOTSTRAP_UNIVERSE)

    def test_target_size(self):
        assert len(BOOTSTRAP_UNIVERSE) >= 200
