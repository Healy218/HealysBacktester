"""Vol-regime track stage 1: RTH-aware per-session RV features, point-in-time
stamps, coverage flags, and the regime-sliced baseline harness."""
import numpy as np
import pandas as pd
import pytest

from nn_meta.vol_features import (LOW_COVERAGE_BARS, evaluate_symbol, rth_bars,
                                  session_rv)


def _bars(days=3, vol=0.001, seed=0, bars_per_day=390):
    """UTC-stamped 1m bars incl. extended hours (like the crawl)."""
    rng = np.random.default_rng(seed)
    idx, px = [], []
    p = 100.0
    for d in pd.date_range("2026-03-02", periods=days, freq="B"):
        # 08:00–20:00 ET = 12h of minutes, RTH is the middle 390
        day_idx = pd.date_range(d + pd.Timedelta(hours=13),  # 08:00 ET in UTC (EST)
                                periods=720, freq="1min")
        idx.extend(day_idx)
        for _ in range(720):
            p *= float(np.exp(rng.normal(0, vol)))
            px.append(p)
    df = pd.DataFrame({"Open": px, "High": px, "Low": px, "Close": px,
                       "Volume": 100.0}, index=pd.DatetimeIndex(idx))
    return df


def test_rth_filter_is_dst_aware_and_keeps_390_bars():
    rth = rth_bars(_bars(days=2))
    per_day = rth.groupby(rth.index.normalize()).size()
    assert (per_day == 390).all()          # March EST: 14:30–21:00 UTC window
    assert rth.index.min().time() == pd.Timestamp("09:30").time()


def test_session_rv_features_are_point_in_time():
    daily = session_rv(_bars(days=4))
    assert len(daily) == 4
    assert (daily["rv_1m"] > 0).all() and (daily["bpv"] > 0).all()
    assert (daily["jump"] >= 0).all()
    assert daily["overnight_r2"].isna().iloc[0]        # no prior close: NaN, not 0
    assert daily["ret_cc"].notna().iloc[1:].all()
    # available_at = 15:59 ET bar close in UTC (EST: 20:59), strictly same day
    aa = pd.to_datetime(daily["available_at"])
    assert (aa.dt.hour == 20).all() and not daily["low_coverage"].any()


def test_low_coverage_is_flagged_never_dropped():
    bars = _bars(days=2)
    rth = rth_bars(bars)
    thin_day = rth.index.normalize().unique()[1]
    keep = ~((bars.index.tz_localize("UTC").tz_convert("America/New_York")
              .tz_localize(None).normalize() == thin_day)
             & (bars.index.hour >= 16))                # drop the afternoon (UTC)
    daily = session_rv(bars[keep])
    assert len(daily) == 2
    assert bool(daily.iloc[1]["low_coverage"]) is True
    assert daily.iloc[1]["n_bars"] < LOW_COVERAGE_BARS


def test_evaluate_symbol_reports_overall_and_regime_qlike():
    rng = np.random.default_rng(1)
    n = 400
    dates = pd.date_range("2024-01-02", periods=n, freq="B")
    rv = np.exp(rng.normal(-9, 0.4, n))                # lognormal RV path
    daily = pd.DataFrame({
        "date": dates, "rv_1m": rv, "ret_cc": rng.normal(0, np.sqrt(rv)),
        "low_coverage": False})
    rows = evaluate_symbol(daily)
    assert rows, "expected at least one evaluated fold"
    for r in rows:
        assert np.isfinite(r["har_qlike"]) and np.isfinite(r["naive_qlike"])
    assert any(k.startswith("har_qlike_") for k in rows[-1])   # regime slices
