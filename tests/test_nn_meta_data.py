# tests/test_nn_meta_data.py
"""nn_meta download helpers: RTH filtering must be DST-correct."""
import pandas as pd

from nn_meta.download_data import filter_rth


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
