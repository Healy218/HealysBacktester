"""V8.0-data bar builder: session binning, source spans and needed days."""
import importlib.util
from pathlib import Path

import pandas as pd

_SPEC = importlib.util.spec_from_file_location(
    "build_v8_bars",
    Path(__file__).resolve().parent.parent / "scripts" / "build_v8_bars.py")
bars = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(bars)


def _minutes(times_et, closes):
    ts = pd.DatetimeIndex(times_et).tz_localize("America/New_York").tz_convert("UTC")
    raw = pd.DataFrame({"timestamp": ts, "Open": closes, "High": closes,
                        "Low": closes, "Close": closes, "Volume": 1.0})
    adj = raw.assign(Open=raw.Open / 2, High=raw.High / 2, Low=raw.Low / 2,
                     Close=raw.Close / 2, Volume=2.0)
    return bars._merge_bases(raw, adj)


def test_rth_bins_anchor_at_0930_and_drop_extended_hours():
    m = _minutes(["2024-06-03 09:29", "2024-06-03 09:30", "2024-06-03 10:29",
                  "2024-06-03 10:30", "2024-06-03 15:59", "2024-06-03 16:00"],
                 [1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    h = bars.aggregate(bars._rth(m), ["date", "hour_bin"])
    assert list(h["hour_bin"]) == [0, 1, 6]
    first = h.iloc[0]
    assert (first["open"], first["close"], first["high"], first["volume"]) == (2.0, 3.0, 3.0, 2.0)
    assert first["adj_close"] == 1.5 and first["adj_volume"] == 4.0
    d = bars.aggregate(bars._rth(m), ["date"])
    assert d.iloc[0]["open"] == 2.0 and d.iloc[0]["close"] == 5.0 and d.iloc[0]["n_bars"] == 4


def test_spans_split_on_source_change():
    s = bars.spans_of({"2022-06-07": "FB", "2022-06-08": "FB",
                       "2022-06-09": "META", "2022-06-10": "META"})
    assert s == [{"source": "FB", "first": "2022-06-07", "last": "2022-06-08"},
                 {"source": "META", "first": "2022-06-09", "last": "2022-06-10"}]


def test_needed_days_follow_available_at():
    pool = {"rule": {"etfs_every_month": ["SPY"]},
            "months": {"2022-01": {"available_at": "2022-02-01", "tech": ["XLNX"]},
                       "2022-02": {"available_at": "2022-03-01", "tech": []}}}
    days = ["2022-01-31", "2022-02-01", "2022-02-28", "2022-03-01"]
    need = bars.needed_days(pool, days)
    assert need["XLNX"] == {"2022-02-01", "2022-02-28"}
    assert need["SPY"] == {"2022-02-01", "2022-02-28", "2022-03-01"}


def test_repair_days_flags_thin_and_missing_days_on_liquid_names():
    days = [f"2022-03-{d:02d}" for d in range(1, 12)]
    daily = pd.DataFrame({"date": [d for d in days if d != "2022-03-10"],
                          "n_bars": [390] * 7 + [30, 390, 390]})
    assert bars.repair_days(daily, days) == ["2022-03-08", "2022-03-10"]
    thin = daily.assign(n_bars=[40] * 10)  # an illiquid name is never "repaired"
    assert bars.repair_days(thin, days) == ["2022-03-10"]


def test_rebase_makes_adjusted_continuous_across_seam():
    def span(close, adj):
        d = pd.DataFrame({"close": [close], "adj_close": [adj], "adj_open": [adj],
                          "adj_high": [adj], "adj_low": [adj], "adj_volume": [100.0]})
        return {"daily": d, "hourly": d.copy()}
    old, new = span(27.0, 27.0), span(27.5, 550.0)  # later reverse split only on new symbol
    bars.rebase_adjusted([old, new])
    assert old["daily"]["adj_close"].iloc[0] == 540.0
    assert old["hourly"]["adj_volume"].iloc[0] == 5.0
