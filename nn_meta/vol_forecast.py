"""Track 1 classical volatility baselines: HAR-RV and GARCH(1,1).

The forecasting track's product is volatility features for the meta-model, and
the standing rule is that no neural sequence model ships before it beats the
boring classical baseline out-of-sample.  This module is that baseline: a
HAR-RV regression and a GARCH(1,1) MLE, scored one-step-ahead with QLIKE and
pinball loss under the stage-1 expanding folds.

Realized variance here is the daily squared log return — a noisy but unbiased
proxy.  The full run should use intraday realized variance from the 1-minute
underlying history in ``v3/data`` (not on this machine); the contract and
losses are identical, only the RV input is finer.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from nn_meta.temporal_validation import expanding_folds


def daily_log_returns(close) -> np.ndarray:
    """Log returns from a close series (first element dropped)."""
    c = np.asarray(close, dtype=float)
    return np.diff(np.log(c))


def realized_variance(returns) -> np.ndarray:
    """Daily realized-variance proxy: squared return per day."""
    return np.asarray(returns, dtype=float) ** 2


# ── loss functions ───────────────────────────────────────────────────────────

def qlike(realized, forecast) -> float:
    """QLIKE variance loss: mean(r/f - log(r/f) - 1); 0 iff forecast == realized."""
    r = np.asarray(realized, dtype=float)
    f = np.asarray(forecast, dtype=float)
    m = (r > 0) & (f > 0) & np.isfinite(r) & np.isfinite(f)
    if not m.any():
        return float("nan")
    ratio = r[m] / f[m]
    return float(np.mean(ratio - np.log(ratio) - 1.0))


def pinball_loss(y_true, y_pred, quantile: float) -> float:
    """Quantile (pinball) loss at the given quantile level."""
    e = np.asarray(y_true, dtype=float) - np.asarray(y_pred, dtype=float)
    return float(np.mean(np.maximum(quantile * e, (quantile - 1.0) * e)))


# ── HAR-RV ───────────────────────────────────────────────────────────────────

def _har_matrix(rv: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Design matrix [1, RV_d, RV_w, RV_m] predicting RV[t] for t >= 22."""
    rows, targets = [], []
    for t in range(22, len(rv)):
        rows.append([1.0, rv[t - 1], rv[t - 5:t].mean(), rv[t - 22:t].mean()])
        targets.append(rv[t])
    return np.asarray(rows), np.asarray(targets)


@dataclass(frozen=True)
class HARRV:
    """Heterogeneous Auto-Regressive realized-variance model."""

    coef: np.ndarray

    @classmethod
    def fit(cls, rv) -> "HARRV":
        rv = np.asarray(rv, dtype=float)
        x, y = _har_matrix(rv)
        if len(x) == 0:
            raise ValueError("HAR-RV needs at least 23 realized-variance points")
        coef, *_ = np.linalg.lstsq(x, y, rcond=None)
        return cls(coef)

    def forecast_at(self, rv: np.ndarray, t: int) -> float:
        """One-step-ahead forecast for RV[t] using history strictly before t."""
        feats = np.array([1.0, rv[t - 1], rv[t - 5:t].mean(), rv[t - 22:t].mean()])
        return float(self.coef @ feats)


# ── GARCH(1,1) ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class GARCH11:
    """Gaussian GARCH(1,1); fit on scaled returns for numerical conditioning."""

    omega: float
    alpha: float
    beta: float
    scale: float = 100.0

    @staticmethod
    def _recursion(r: np.ndarray, omega: float, alpha: float, beta: float) -> np.ndarray:
        var = np.empty(len(r))
        var[0] = r.var() if len(r) > 1 else omega / max(1e-6, 1 - alpha - beta)
        for t in range(1, len(r)):
            var[t] = omega + alpha * r[t - 1] ** 2 + beta * var[t - 1]
        return np.maximum(var, 1e-12)

    @classmethod
    def fit(cls, returns, *, scale: float = 100.0) -> "GARCH11":
        r = np.asarray(returns, dtype=float) * scale
        r = r[np.isfinite(r)]
        if len(r) < 30:
            raise ValueError("GARCH(1,1) needs at least 30 returns")
        v0 = r.var()

        def nll(p):
            var = cls._recursion(r, p[0], p[1], p[2])
            return 0.5 * np.sum(np.log(2 * np.pi) + np.log(var) + r ** 2 / var)

        with warnings.catch_warnings():
            # SLSQP probes just outside the box and clips; benign here.
            warnings.simplefilter("ignore", RuntimeWarning)
            res = minimize(nll, x0=[v0 * 0.1, 0.05, 0.90], method="SLSQP",
                           bounds=[(1e-8, None), (1e-8, 0.999), (1e-8, 0.999)],
                           constraints={"type": "ineq",
                                        "fun": lambda p: 0.999 - p[1] - p[2]})
        omega, alpha, beta = res.x
        return cls(float(omega), float(alpha), float(beta), scale)

    def conditional_variance(self, returns) -> np.ndarray:
        r = np.asarray(returns, dtype=float) * self.scale
        return self._recursion(r, self.omega, self.alpha, self.beta) / self.scale ** 2

    def forecast_at(self, returns: np.ndarray, t: int) -> float:
        """One-step-ahead variance for index t from history strictly before t."""
        cv = self.conditional_variance(returns[:t]) * self.scale ** 2
        r_prev = (returns[t - 1] * self.scale) ** 2
        return float((self.omega + self.alpha * r_prev + self.beta * cv[-1])
                     / self.scale ** 2)


# ── fold evaluation ──────────────────────────────────────────────────────────

def evaluate_vol_baselines(dates, returns, *, n_folds: int = 3,
                           pinball_quantile: float = 0.05) -> list[dict]:
    """Compare HAR-RV, GARCH(1,1), and a constant-variance naive forecast OOS.

    Models are fit on each fold's training window; forecasts are one-step-ahead
    over the test window using expanding history, so no test observation informs
    a forecast of itself.  QLIKE scores the variance forecast; pinball scores a
    lower-tail return quantile implied by the variance.
    """
    dates = pd.DatetimeIndex(pd.to_datetime(dates))
    returns = np.asarray(returns, dtype=float)
    rv = realized_variance(returns)
    from scipy.stats import norm
    z = float(norm.ppf(pinball_quantile))

    results = []
    for w in expanding_folds(pd.Series(dates), n_folds=n_folds):
        train = dates < w.test_start
        test_idx = np.where((dates >= w.test_start) & (dates <= w.test_end))[0]
        if train.sum() < 40 or len(test_idx) == 0:
            continue
        har = HARRV.fit(rv[train])
        garch = GARCH11.fit(returns[train])
        naive = float(rv[train].mean())

        har_f = np.array([har.forecast_at(rv, t) for t in test_idx])
        garch_f = np.array([garch.forecast_at(returns, t) for t in test_idx])
        realized = rv[test_idx]
        har_f = np.clip(har_f, 1e-12, None)

        results.append({
            "test_start": str(w.test_start.date()), "test_end": str(w.test_end.date()),
            "n_test": int(len(test_idx)),
            "har_qlike": qlike(realized, har_f),
            "garch_qlike": qlike(realized, garch_f),
            "naive_qlike": qlike(realized, np.full_like(realized, naive)),
            "har_pinball": pinball_loss(returns[test_idx], z * np.sqrt(har_f), pinball_quantile),
            "garch_pinball": pinball_loss(returns[test_idx], z * np.sqrt(garch_f), pinball_quantile),
        })
    return results


def _smoke(symbol: str = "SPY") -> None:
    """Smoke run against the legacy local daily cache."""
    from nn_meta import config
    und = pd.read_parquet(config.UNDERLYING_DAILY_PARQUET,
                          columns=["underlying", "date", "close"])
    bars = und[und["underlying"] == symbol].sort_values("date")
    if len(bars) < 60:
        raise SystemExit(f"not enough local daily bars for {symbol}: {len(bars)}")
    returns = daily_log_returns(bars["close"].to_numpy())
    dates = pd.to_datetime(bars["date"].to_numpy())[1:]
    for row in evaluate_vol_baselines(dates, returns):
        print(f"{row['test_start']}..{row['test_end']} n={row['n_test']:4d} "
              f"QLIKE har={row['har_qlike']:.4f} garch={row['garch_qlike']:.4f} "
              f"naive={row['naive_qlike']:.4f}", flush=True)


if __name__ == "__main__":
    import sys
    _smoke(sys.argv[1] if len(sys.argv) > 1 else "SPY")
