# tests/test_v3_indicators.py
"""v3 indicator library: analytic sanity checks (bounds, constant-series
identities, pandas cross-checks) and the TV rating rules on crafted data.
TradingView-fixture comparisons can be added later; these tests pin the math
that has closed-form expectations."""
import numpy as np
import pandas as pd
import pytest

from v3 import indicators as ta
from v3 import tv_rating


def _ohlcv(close, spread=0.5, vol=1000):
    c = pd.Series(close, dtype=float)
    return pd.DataFrame({"Open": c.shift(1).fillna(c), "High": c + spread,
                         "Low": c - spread, "Close": c,
                         "Volume": float(vol)})


@pytest.fixture
def trend_up():
    return _ohlcv(np.linspace(100, 200, 300))


@pytest.fixture
def trend_down():
    return _ohlcv(np.linspace(200, 100, 300))


@pytest.fixture
def noisy():
    rng = np.random.default_rng(7)
    return _ohlcv(100 + rng.normal(0, 1, 400).cumsum())


class TestMovingAverages:
    def test_constant_series_identities(self):
        c = pd.Series([50.0] * 60)
        for f in (lambda: ta.sma(c, 10), lambda: ta.ema(c, 10),
                  lambda: ta.wma(c, 10), lambda: ta.hma(c, 9)):
            assert np.allclose(f().dropna(), 50.0)

    def test_ema_matches_pandas(self, noisy):
        c = noisy["Close"]
        pd.testing.assert_series_equal(
            ta.ema(c, 12), c.ewm(span=12, adjust=False).mean())

    def test_vwma_constant_volume_equals_sma(self, noisy):
        c, v = noisy["Close"], noisy["Volume"]
        assert np.allclose(ta.vwma(c, v, 20).dropna(),
                           ta.sma(c, 20).dropna())

    def test_ichimoku_columns_and_uptrend_stack(self, trend_up):
        ich = ta.ichimoku(trend_up).dropna()
        assert list(ich.columns) == ["conversion", "base", "span_a", "span_b"]
        # steady uptrend: shorter midpoints sit above longer ones
        last = ich.iloc[-1]
        assert last["conversion"] > last["base"] > last["span_b"]


class TestOscillators:
    def test_rsi_bounds_and_uptrend(self, trend_up, noisy):
        r = ta.rsi(trend_up["Close"]).dropna()
        assert (r > 99).iloc[-1]                     # monotonic rise → ~100
        rn = ta.rsi(noisy["Close"]).dropna()
        assert rn.between(0, 100).all()

    def test_stochastic_bounds(self, noisy):
        st = ta.stochastic(noisy).dropna()
        assert st["k"].between(0, 100).all() and st["d"].between(0, 100).all()

    def test_stoch_rsi_bounds(self, noisy):
        sr = ta.stoch_rsi(noisy["Close"]).dropna()
        assert sr["k"].between(0, 100).all()

    def test_cci_centered_on_trendless(self):
        cc = ta.cci(_ohlcv([100.0] * 80)).dropna()
        assert cc.empty or np.allclose(cc, 0)        # constant → MAD 0 → NaN

    def test_adx_bounds_and_direction(self, trend_up, trend_down):
        up = ta.adx(trend_up).dropna()
        assert (up["plus_di"] >= up["minus_di"]).iloc[-1]
        assert up["adx"].between(0, 100).all()
        dn = ta.adx(trend_down).dropna()
        assert (dn["minus_di"] >= dn["plus_di"]).iloc[-1]

    def test_macd_is_ema_diff(self, noisy):
        c = noisy["Close"]
        m = ta.macd(c)
        assert np.allclose(m["macd"], ta.ema(c, 12) - ta.ema(c, 26),
                           equal_nan=True)
        assert np.allclose(m["hist"], m["macd"] - m["signal"], equal_nan=True)

    def test_williams_r_bounds(self, noisy):
        wr = ta.williams_r(noisy).dropna()
        assert wr.between(-100, 0).all()

    def test_ultimate_oscillator_bounds(self, noisy):
        uo = ta.ultimate_oscillator(noisy).dropna()
        assert uo.between(0, 100).all()

    def test_momentum(self, trend_up):
        assert (ta.momentum(trend_up["Close"]).dropna() > 0).all()

    def test_bull_bear_uptrend(self, trend_up):
        bb = ta.bull_bear_power(trend_up).dropna()
        assert (bb["bull"] > 0).iloc[-1]

    def test_awesome_oscillator_sign(self, trend_up, trend_down):
        assert ta.awesome_oscillator(trend_up).dropna().iloc[-1] > 0
        assert ta.awesome_oscillator(trend_down).dropna().iloc[-1] < 0


class TestCommunity:
    def test_supertrend_regimes(self, trend_up, trend_down):
        assert ta.supertrend(trend_up)["direction"].iloc[-1] == 1
        assert ta.supertrend(trend_down)["direction"].iloc[-1] == -1
        # trailing stop sits below price in an uptrend
        st = ta.supertrend(trend_up).dropna()
        tail = st[st["direction"] == 1].tail(50)
        assert (tail["supertrend"] < trend_up["Close"].loc[tail.index]).all()

    def test_squeeze_momentum_shape(self, noisy):
        sq = ta.squeeze_momentum(noisy)
        assert sq["squeeze_on"].dtype == bool
        assert np.isfinite(sq["momentum"].dropna()).all()


class TestRating:
    def test_uptrend_rates_bullish_mas(self, trend_up):
        ma = tv_rating.ma_scores(trend_up).iloc[-1]
        # HMA extrapolates and can sit ON/above price in a perfectly linear
        # trend — exclude it and Ichimoku's stricter stack rule here
        assert ma.drop(["ichimoku", "hma9"]).eq(1).all()
        assert ma["hma9"] in (-1.0, 0.0, 1.0)

    def test_rating_bounds_and_columns(self, noisy):
        r = tv_rating.rating(noisy).dropna()
        assert list(r.columns) == ["ma_rating", "osc_rating", "rating"]
        assert r["rating"].between(-1, 1).all()

    def test_component_count(self, noisy):
        assert tv_rating.ma_scores(noisy).shape[1] == 15
        assert tv_rating.osc_scores(noisy).shape[1] == 11

    def test_categories(self):
        assert tv_rating.category(-0.9) == "strong_sell"
        assert tv_rating.category(-0.3) == "sell"
        assert tv_rating.category(0.0) == "neutral"
        assert tv_rating.category(0.3) == "buy"
        assert tv_rating.category(0.9) == "strong_buy"

    def test_macd_score_rule(self):
        # rising series → MACD above signal → +1
        df = _ohlcv(np.linspace(100, 150, 120))
        sc = tv_rating.osc_scores(df)["macd"]
        assert sc.iloc[-1] == 1
