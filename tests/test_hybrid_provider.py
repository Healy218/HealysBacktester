# tests/test_hybrid_provider.py
"""HybridCachedProvider: point-in-time chains from universe metadata, cache-first
contract bars with fetch-on-miss persistence, and 429 retry behavior."""
import pandas as pd
import pytest

from options.data.hybrid_provider import HybridCachedProvider
from options.data.provider import OptionsDataProvider
from utils.error_handling import DataError


# ── fixtures ─────────────────────────────────────────────────────────────────

def _universe_df():
    # "O:" prefix as stored by the real universe parquet; the provider strips it.
    return pd.DataFrame({
        "ticker": ["O:SPY250131C00600000", "O:SPY250321P00580000"],
        "underlying": ["SPY", "SPY"],
        "strike": [600.0, 580.0],
        "expiration": pd.to_datetime(["2025-01-31", "2025-03-21"]),
        "type": ["call", "put"],
        "life_start": pd.to_datetime(["2024-12-02", "2025-01-20"]),
        "life_end": ["2025-01-31", "2025-03-21"],
    })


def _bars(start: str, periods: int, freq: str = "15min") -> pd.DataFrame:
    idx = pd.date_range(start, periods=periods, freq=freq)
    return pd.DataFrame(
        {"Open": 1.0, "High": 1.1, "Low": 0.9, "Close": 1.05, "Volume": 10},
        index=idx,
    )


class FakeLive(OptionsDataProvider):
    """Counts calls; optionally raises 429 for the first N calls."""

    def __init__(self, bars: pd.DataFrame, fail_429_times: int = 0):
        self._bars = bars
        self._fail = fail_429_times
        self.calls = 0

    def get_underlying_bars(self, symbol, start, end, interval):
        raise NotImplementedError

    def get_chain(self, underlying, **kwargs):
        raise NotImplementedError

    def get_contract_bars(self, occ_symbol, start, end, interval):
        self.calls += 1
        if self._fail > 0:
            self._fail -= 1
            raise DataError("Massive HTTP 429 for /v2/aggs: too many requests")
        return self._bars.copy()


def _provider(tmp_path, live, **kwargs):
    return HybridCachedProvider(
        bars_cache_dir=tmp_path,
        underlying_daily_parquet=tmp_path / "und_daily.parquet",
        underlying_15m_parquet=tmp_path / "und_15m.parquet",
        universe_df=_universe_df(),
        live_provider=live,
        **kwargs,
    )


# ── chains ───────────────────────────────────────────────────────────────────

class TestChain:
    def test_point_in_time_includes_live_contract(self, tmp_path):
        p = _provider(tmp_path, FakeLive(_bars("2025-01-02", 4)))
        chain = p.get_chain("SPY", right="C", as_of=pd.Timestamp("2025-01-10").date())
        assert [c.symbol for c in chain] == ["SPY250131C00600000"]
        assert chain[0].strike == 600.0 and chain[0].right == "C"

    def test_as_of_excludes_unlisted_and_expired(self, tmp_path):
        p = _provider(tmp_path, FakeLive(_bars("2025-01-02", 4)))
        # Before the put's life_start (2025-01-20) → only the call exists
        early = p.get_chain("SPY", as_of=pd.Timestamp("2025-01-10").date())
        assert {c.symbol for c in early} == {"SPY250131C00600000"}
        # After the call expires (2025-01-31) → only the put remains
        late = p.get_chain("SPY", as_of=pd.Timestamp("2025-02-10").date())
        assert {c.symbol for c in late} == {"SPY250321P00580000"}

    def test_strike_and_expiration_filters(self, tmp_path):
        p = _provider(tmp_path, FakeLive(_bars("2025-01-02", 4)))
        chain = p.get_chain("SPY", strike_gte=590.0,
                            expiration_lte=pd.Timestamp("2025-02-28").date())
        assert {c.symbol for c in chain} == {"SPY250131C00600000"}


# ── contract bars ────────────────────────────────────────────────────────────

class TestContractBars:
    OCC = "SPY250131C00600000"

    def test_fetch_once_then_cache(self, tmp_path):
        live = FakeLive(_bars("2025-01-02 14:30", 8))
        p = _provider(tmp_path, live)
        df1 = p.get_contract_bars(self.OCC, "2025-01-01", "2025-01-31", "15m")
        df2 = p.get_contract_bars(self.OCC, "2025-01-01", "2025-01-31", "15m")
        assert live.calls == 1                       # second call served from parquet
        assert len(df1) == 8 and df1.equals(df2)
        assert (tmp_path / "bars_15m" / f"{self.OCC}.parquet").exists()

    def test_window_slicing(self, tmp_path):
        # bars across two days; request only the first day
        live = FakeLive(_bars("2025-01-02 14:30", 60))   # spills into 2025-01-03
        p = _provider(tmp_path, live)
        df = p.get_contract_bars(self.OCC, "2025-01-02", "2025-01-02", "15m")
        assert not df.empty
        assert df.index.max() < pd.Timestamp("2025-01-03")

    def test_empty_result_cached_fetch_exactly_once(self, tmp_path):
        live = FakeLive(pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"]))
        p = _provider(tmp_path, live)
        assert p.get_contract_bars(self.OCC, "2025-01-01", "2025-01-31", "15m").empty
        assert p.get_contract_bars(self.OCC, "2025-01-01", "2025-01-31", "15m").empty
        assert live.calls == 1

    def test_429_retries_then_succeeds(self, tmp_path, monkeypatch):
        import options.data.hybrid_provider as hp
        monkeypatch.setattr(hp.time, "sleep", lambda s: None)
        live = FakeLive(_bars("2025-01-02 14:30", 4), fail_429_times=2)
        p = _provider(tmp_path, live)
        df = p.get_contract_bars(self.OCC, "2025-01-01", "2025-01-31", "15m")
        assert len(df) == 4 and live.calls == 3      # 2 failures + 1 success

    def test_no_fetch_when_disabled(self, tmp_path):
        live = FakeLive(_bars("2025-01-02 14:30", 4))
        p = _provider(tmp_path, live, allow_fetch=False)
        df = p.get_contract_bars(self.OCC, "2025-01-01", "2025-01-31", "15m")
        assert df.empty and live.calls == 0

    def test_interval_caches_are_separate(self, tmp_path):
        live = FakeLive(_bars("2025-01-02", 3, freq="D"))
        p = _provider(tmp_path, live)
        p.get_contract_bars(self.OCC, "2025-01-01", "2025-01-31", "15m")
        p.get_contract_bars(self.OCC, "2025-01-01", "2025-01-31", "1D")
        assert live.calls == 2
        assert (tmp_path / "bars_15m" / f"{self.OCC}.parquet").exists()
        assert (tmp_path / "bars_1d" / f"{self.OCC}.parquet").exists()


# ── underlying bars ──────────────────────────────────────────────────────────

class TestUnderlyingBars:
    def test_daily_from_parquet(self, tmp_path):
        daily = pd.DataFrame({
            "underlying": ["SPY"] * 3 + ["QQQ"] * 3,
            "date": list(pd.date_range("2025-01-02", periods=3)) * 2,
            "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.05,
            "volume": 100, "vwap": 1.0, "transactions": 5,
        })
        daily.to_parquet(tmp_path / "und_daily.parquet")
        p = _provider(tmp_path, FakeLive(_bars("2025-01-02", 4)))
        df = p.get_underlying_bars("SPY", "2025-01-02", "2025-01-03", "1D")
        assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
        assert len(df) == 2                          # only SPY rows in window

    def test_15m_from_parquet(self, tmp_path):
        idx = pd.date_range("2025-01-02 14:30", periods=6, freq="15min")
        bars15 = pd.DataFrame({
            "symbol": "SPY", "timestamp": idx,
            "Open": 1.0, "High": 1.1, "Low": 0.9, "Close": 1.05, "Volume": 100,
        })
        bars15.to_parquet(tmp_path / "und_15m.parquet")
        p = _provider(tmp_path, FakeLive(_bars("2025-01-02", 4)))
        df = p.get_underlying_bars("SPY", "2025-01-02", "2025-01-02", "15m")
        assert len(df) == 6 and df.index.name == "timestamp"

    def test_missing_15m_parquet_raises_helpful_error(self, tmp_path):
        p = _provider(tmp_path, FakeLive(_bars("2025-01-02", 4)))
        with pytest.raises(DataError, match="nn_meta.download_data"):
            p.get_underlying_bars("SPY", "2025-01-02", "2025-01-03", "15m")
