# tests/test_nn_meta_data.py
"""nn_meta download helpers: RTH filtering must be DST-correct."""
import pandas as pd
import pytest

from nn_meta.download_data import filter_rth, _load_chunked


def _day(day: str) -> pd.DataFrame:
    """Full 24h of 15m bars for one day, tz-naive UTC."""
    idx = pd.date_range(f"{day} 00:00", periods=96, freq="15min")
    return pd.DataFrame({"Open": 1.0, "High": 1.0, "Low": 1.0, "Close": 1.0,
                         "Volume": 1}, index=idx)


class TestFilterRth:
    def test_winter_rth_window(self):
        # EST (UTC-5): RTH = 14:30–21:00 UTC
        out = filter_rth(_day("2025-01-15"))
        assert len(out) == 26
        assert out.index[0] == pd.Timestamp("2025-01-15 14:30")
        assert out.index[-1] == pd.Timestamp("2025-01-15 20:45")

    def test_summer_rth_window(self):
        # EDT (UTC-4): RTH = 13:30–20:00 UTC
        out = filter_rth(_day("2025-06-16"))
        assert len(out) == 26
        assert out.index[0] == pd.Timestamp("2025-06-16 13:30")
        assert out.index[-1] == pd.Timestamp("2025-06-16 19:45")

    def test_output_is_tz_naive(self):
        out = filter_rth(_day("2025-06-16"))
        assert out.index.tz is None

    def test_empty_frame_passthrough(self):
        empty = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"],
                             index=pd.DatetimeIndex([]))
        assert filter_rth(empty).empty


@pytest.mark.parametrize("inclusive_endpoint", [False, True])
def test_chunked_download_preserves_month_ends_and_final_day(monkeypatch, inclusive_endpoint):
    calls = []
    def vendor(symbol, start, end, interval):
        calls.append((start, end))
        index = pd.date_range(start, end, freq="15min",
                              inclusive="both" if inclusive_endpoint else "left")
        return pd.DataFrame({"Open": 1., "High": 1., "Low": 1., "Close": 1., "Volume": 1}, index=index)
    monkeypatch.setattr("nn_meta.download_data.vbt_data_loader.load_price_data_smart", vendor)
    actual = filter_rth(_load_chunked("SPY", "2024-08-01", "2026-08-24"))
    for day in ["2025-03-31", "2025-07-31", "2026-03-31", "2026-07-31", "2026-08-24"]:
        assert len(actual.loc[day]) == 26
    assert actual.index.is_unique
    assert actual.index.max() == pd.Timestamp("2026-08-24 19:45")
    assert calls[-1][1] == "2026-08-25"
    assert all(previous[1] == following[0] for previous, following in zip(calls, calls[1:]))


@pytest.mark.parametrize("months", [0, -1, True, 1.5])
def test_invalid_chunk_size_refused_before_fetch(months):
    with pytest.raises(ValueError, match="months"):
        _load_chunked("SPY", "2026-08-01", "2026-08-24", months=months)
