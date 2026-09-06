"""Streamed bar store (2026-09-05): append/read, 1m → 15m aggregation in the
REST loader's shape, completeness trim."""
import pandas as pd
import pytest

from nn_meta.live.feeds.barstore import BarStore, aggregate_15m


def _m1(day="2026-09-04", start="13:30", n=45, base=100.0):
    idx = pd.date_range(f"{day} {start}", periods=n, freq="1min")
    return [{"timestamp": t, "open": base + i, "high": base + i + 0.5, "low": base + i - 0.5,
             "close": base + i + 0.25, "volume": 10.0} for i, t in enumerate(idx)]


def test_append_is_idempotent_and_sorted(tmp_path):
    s = BarStore(tmp_path)
    assert s.append_1m("spy", _m1()) == 45
    assert s.append_1m("SPY", _m1()) == 45                 # same rows again → no growth
    late = _m1(start="14:15", n=5, base=200.0)
    s.append_1m("SPY", late[::-1])                         # out of order
    m1 = s.read_1m("SPY")
    assert len(m1) == 50 and m1.index.is_monotonic_increasing and m1.index.tz is None
    assert list(m1.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert s.coverage("SPY")["rows"] == 50 and s.coverage("NOPE")["rows"] == 0


def test_aggregate_15m_matches_alpaca_convention(tmp_path):
    s = BarStore(tmp_path); s.append_1m("SPY", _m1(n=45))
    b = s.read_15m("SPY")
    assert list(b.index) == [pd.Timestamp("2026-09-04 13:30"), pd.Timestamp("2026-09-04 13:45"),
                             pd.Timestamp("2026-09-04 14:00")]
    first = b.iloc[0]
    assert first.Open == 100.0 and first.High == 114.5 and first.Low == 99.5 \
        and first.Close == 114.25 and first.Volume == 150.0
    assert b.index.tz is None and b.dtypes.eq(float).all()


def test_read_15m_returns_only_complete_buckets_before_now(tmp_path):
    s = BarStore(tmp_path); s.append_1m("SPY", _m1(n=40))    # 13:30..14:09
    b = s.read_15m("SPY", now=pd.Timestamp("2026-09-04 14:10"))
    assert list(b.index) == [pd.Timestamp("2026-09-04 13:30"), pd.Timestamp("2026-09-04 13:45")]
    b2 = s.read_15m("SPY", now=pd.Timestamp("2026-09-04 13:59"))
    assert list(b2.index) == [pd.Timestamp("2026-09-04 13:30")]


def test_aggregate_drops_pre_market_bars():
    m1 = pd.DataFrame({"Open": 1.0, "High": 1.0, "Low": 1.0, "Close": 1.0, "Volume": 1.0},
                      index=pd.date_range("2026-09-04 12:00", periods=120, freq="1min"))
    b = aggregate_15m(m1)
    assert b.index[0] == pd.Timestamp("2026-09-04 13:30") and len(b) == 2


def test_stream_maps_vendor_symbols_both_ways(monkeypatch):
    from nn_meta import config
    from nn_meta.live.feeds import stock_stream as ss
    monkeypatch.setattr(config, "FETCH_ALIASES", {"BRKB": "BRK.B"}, raising=False)
    assert ss.vendor_symbol("BRKB") == "BRK.B" and ss.vendor_symbol("spy") == "SPY"
    assert ss.pool_symbol("BRK.B") == "BRKB" and ss.pool_symbol("SPY") == "SPY"


def test_live_loader_fetches_the_vendor_symbol(monkeypatch):
    import pandas as pd
    from datetime import datetime, timezone
    from nn_meta import config
    from nn_meta.live import run_live
    monkeypatch.setattr(config, "FETCH_ALIASES", {"BRKB": "BRK.B"}, raising=False)
    seen = []
    def fake_smart(symbol, start, end, interval, cache_dir="data/cache", force_download=False, use_cache=True):
        seen.append(symbol)
        idx = pd.date_range(pd.Timestamp(end).strftime("%Y-%m-%d") + " 13:30", periods=2, freq="15min")
        return pd.DataFrame({"Open": 1.0, "High": 1.0, "Low": 1.0, "Close": 1.0, "Volume": 1.0}, index=idx)
    monkeypatch.setattr(run_live.vbt_data_loader, "load_price_data_smart", fake_smart)
    monkeypatch.setattr(run_live, "_feed_is_fresh", lambda now: False)
    run_live._bar_loader("BRKB", now=datetime(2026, 9, 4, 15, 0, tzinfo=timezone.utc))
    assert seen == ["BRK.B", "BRK.B"]
