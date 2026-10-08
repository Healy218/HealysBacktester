"""V8 stock spread sampler: day selection, quote filtering, AR estimator."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

_SPEC = importlib.util.spec_from_file_location(
    "sample_v8_stock_spreads",
    Path(__file__).resolve().parent.parent / "scripts" / "sample_v8_stock_spreads.py")
sp = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(sp)


def test_sample_days_deterministic_three_per_month():
    days = [d.date().isoformat() for d in pd.bdate_range("2022-01-01", "2022-03-31")]
    a, b = sp.sample_days(days), sp.sample_days(days)
    assert a == b and len(a) == 9
    assert all(sum(x.startswith(m) for x in a) == 3 for m in ("2022-01", "2022-02", "2022-03"))


def test_summarize_drops_crossed_and_stub_quotes():
    t = pd.Timestamp("2022-03-09T15:00:10Z")
    qs = [{"bp": 100.0, "ap": 100.02, "bs": 1, "as": 1, "t": "2022-03-09T15:00:01Z"},
          {"bp": 100.0, "ap": 99.9, "bs": 1, "as": 1, "t": "2022-03-09T15:00:05Z"},   # crossed
          {"bp": 1.0, "ap": 200.0, "bs": 1, "as": 1, "t": "2022-03-09T15:00:06Z"}]    # stub
    r = sp.summarize("X", qs, t, 10)
    assert r["n_quotes"] == 1 and r["age_s"] == 9.0
    assert abs(r["spread_bps"] - 2.0) < 1e-3
    assert sp.summarize("X", qs[1:], t, 10) is None


def test_abdi_ranaldo_recovers_spread_from_bounce():
    # mid fixed at 100, closes alternate bid/ask with a 20 bp spread,
    # high/low straddle the mid symmetrically → eta = log(mid)
    n = 40
    rng = np.random.default_rng(0)
    side = rng.choice([-1, 1], n)
    close = 100 * np.exp(side * 0.001)
    daily = pd.DataFrame({"ticker": "X", "date": [f"2022-01-{i % 28 + 1:02d}" for i in range(n)],
                          "high": 100 * np.exp(0.01), "low": 100 * np.exp(-0.01), "close": close})
    daily["date"] = [d.date().isoformat() for d in pd.bdate_range("2022-01-03", periods=n)]
    ar = sp.abdi_ranaldo(daily)
    assert ((ar["ar_bps"] > 10) & (ar["ar_bps"] < 30)).all()
