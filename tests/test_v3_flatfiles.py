# tests/test_v3_flatfiles.py
"""Flat-files ingestion: the pure minute-aggs→15m transform and the
FlatFilesProvider's per-contract slice, on synthetic data (no S3/network)."""
import numpy as np
import pandas as pd
import pytest

from v3.flatfiles import FlatFilesProvider, frame_from_minute_aggs


def _raw(occ_tickers, per_min=30):
    """Synthetic whole-market minute aggs: a few contracts, per_min bars each."""
    base = pd.Timestamp("2026-06-01 13:30", tz="UTC").value  # ns
    rows = []
    for tk in occ_tickers:
        for i in range(per_min):
            rows.append({"ticker": tk, "volume": 10 + i,
                         "open": 1.0 + i * 0.01, "close": 1.0 + i * 0.01,
                         "high": 1.1 + i * 0.01, "low": 0.9 + i * 0.01,
                         "window_start": base + i * 60_000_000_000,  # +i min
                         "transactions": 1})
    return pd.DataFrame(rows)


class TestTransform:
    def test_filters_to_universe_and_resamples_15m(self):
        raw = _raw(["O:SPY260601C00500000", "O:ZZZZ260601C00010000"])
        out = frame_from_minute_aggs(raw, {"SPY"})
        assert set(out["occ"]) == {"SPY260601C00500000"}   # ZZZZ dropped
        # 30 one-min bars → two 15m buckets (13:30, 13:45)
        assert len(out) == 2
        assert list(out.columns) == ["occ", "timestamp", "Open", "High",
                                     "Low", "Close", "Volume"]
        assert out["Volume"].dtype == np.int64
        # OHLC aggregation within the first bucket
        first = out.iloc[0]
        assert first["Open"] == pytest.approx(1.0)          # first minute open
        assert first["High"] == pytest.approx(1.1 + 14 * 0.01)  # max over 15

    def test_empty_when_no_universe_match(self):
        out = frame_from_minute_aggs(_raw(["O:AAA260601C00010000"]), {"SPY"})
        assert out.empty

    def test_occ_regex_rejects_malformed(self):
        raw = _raw(["NOTANOPTION", "O:SPY260601C00500000"])
        out = frame_from_minute_aggs(raw, {"SPY"})
        assert set(out["occ"]) == {"SPY260601C00500000"}


class TestProviderSlice:
    def test_fetch_slices_contract_from_day_frames(self, tmp_path, monkeypatch):
        # write two day-frames; provider must concat the contract across them
        ffdir = tmp_path / "flatfiles_15m"
        ffdir.mkdir()
        for day in ("2026-06-01", "2026-06-02"):
            fr = frame_from_minute_aggs(
                _raw(["O:SPY260601C00500000", "O:SPY260601P00400000"]), {"SPY"})
            fr["timestamp"] = pd.to_datetime(fr["timestamp"]).map(
                lambda t: t.replace(day=int(day[-2:])))
            fr.to_parquet(ffdir / f"{day}.parquet", index=False)

        # bypass HybridCachedProvider.__init__'s parquet loads
        prov = FlatFilesProvider.__new__(FlatFilesProvider)
        prov._ff_dir = ffdir
        from datetime import date
        bars = prov._fetch_with_retry(
            "SPY260601C00500000", date(2026, 6, 1), date(2026, 6, 2), "15m")
        assert list(bars.columns) == ["Open", "High", "Low", "Close", "Volume"]
        assert bars.index.name == "timestamp"
        assert len(bars) == 4          # 2 buckets/day × 2 days
        # daily rollup path
        daily = prov._fetch_with_retry(
            "SPY260601C00500000", date(2026, 6, 1), date(2026, 6, 2), "daily")
        assert len(daily) == 2         # one bar per day
