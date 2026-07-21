"""HAR-RV / GARCH(1,1) volatility baselines and their OOS losses."""
import numpy as np
import pandas as pd
import pytest

from nn_meta.vol_forecast import (GARCH11, HARRV, daily_log_returns,
                                  evaluate_vol_baselines, pinball_loss, qlike,
                                  realized_variance)


def _sim_garch(n, omega, alpha, beta, seed):
    rng = np.random.default_rng(seed)
    r = np.zeros(n)
    var = omega / (1 - alpha - beta)
    for t in range(1, n):
        var = omega + alpha * r[t - 1] ** 2 + beta * var
        r[t] = rng.normal(0.0, np.sqrt(var))
    return r


def _sim_har(n, seed):
    rng = np.random.default_rng(seed)
    rv = np.empty(n)
    rv[:22] = rng.uniform(0.5, 1.5, 22)
    for t in range(22, n):
        pred = 0.1 + 0.5 * rv[t - 1] + 0.3 * rv[t - 5:t].mean() + 0.1 * rv[t - 22:t].mean()
        rv[t] = max(1e-3, pred + rng.normal(0.0, 0.05))
    return rv


def test_qlike_is_zero_at_perfect_forecast():
    x = np.array([1e-4, 2e-4, 3e-4])
    assert qlike(x, x) == pytest.approx(0.0)
    assert qlike(x, x * 2) > 0


def test_pinball_median_is_half_mae():
    y = np.array([1.0, 2.0, 3.0])
    p = np.array([1.5, 1.5, 1.5])
    assert pinball_loss(y, p, 0.5) == pytest.approx(0.5 * np.mean(np.abs(y - p)))


def test_daily_log_returns_and_rv():
    close = np.array([100.0, 101.0, 100.0])
    r = daily_log_returns(close)
    assert len(r) == 2
    assert np.all(realized_variance(r) >= 0)


def test_har_beats_naive_out_of_sample():
    rv = _sim_har(2000, 0)
    model = HARRV.fit(rv[:1600])
    forecasts = np.clip([model.forecast_at(rv, t) for t in range(1600, 2000)], 1e-9, None)
    realized = rv[1600:2000]
    assert qlike(realized, forecasts) < qlike(realized, np.full_like(realized, rv[:1600].mean()))


def test_garch_recovers_persistence_and_beats_naive():
    r = _sim_garch(3000, omega=1e-6, alpha=0.10, beta=0.85, seed=1)
    model = GARCH11.fit(r[:2400])
    assert 0.0 < model.alpha < 0.5
    assert 0.8 < model.alpha + model.beta < 1.0            # persistent, stationary
    rv = realized_variance(r)
    forecasts = np.array([model.forecast_at(r, t) for t in range(2400, 3000)])
    assert np.all(forecasts > 0)
    naive = np.full(600, rv[:2400].mean())
    assert qlike(rv[2400:], forecasts) < qlike(rv[2400:], naive)


def test_evaluate_vol_baselines_reports_each_fold():
    r = _sim_garch(800, omega=1e-6, alpha=0.10, beta=0.85, seed=2)
    dates = pd.bdate_range("2020-01-01", periods=800)
    rows = evaluate_vol_baselines(dates, r, n_folds=2)
    assert len(rows) == 2
    for row in rows:
        assert {"har_qlike", "garch_qlike", "naive_qlike", "har_pinball",
                "garch_pinball", "n_test"} <= set(row)
        assert np.isfinite(row["garch_qlike"])


def test_garch_fit_requires_minimum_history():
    with pytest.raises(ValueError, match="at least 30"):
        GARCH11.fit(np.zeros(10))
