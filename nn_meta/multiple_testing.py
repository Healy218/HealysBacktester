"""Multiple-testing corrections for the v4 policy grid.

Selecting a mode/threshold/model on validation and reporting its Sharpe invites
backtest overfitting.  Two standard tools guard against it:

* Deflated Sharpe Ratio (Bailey & López de Prado): the probability the true
  Sharpe exceeds zero after deflating for the number of configurations tried,
  the sample length, and non-normal returns.
* Probability of Backtest Overfitting via CSCV: the fraction of in-sample /
  out-of-sample splits in which the in-sample-best strategy underperforms the
  median out of sample.

Everything here is pure (stdlib + numpy), so the local suite needs no scipy.
"""
from __future__ import annotations

import itertools
import math
from statistics import NormalDist

import numpy as np
import pandas as pd

_N = NormalDist()
_EULER_MASCHERONI = 0.5772156649015329


def sharpe_moments(returns) -> tuple[float, int, float, float]:
    """Return (per-observation Sharpe, n, skew, Pearson kurtosis) of a series."""
    x = np.asarray(returns, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 2:
        return 0.0, n, 0.0, 3.0
    mu = x.mean()
    sd = x.std(ddof=1)
    if sd == 0:
        return 0.0, n, 0.0, 3.0
    sr = mu / sd
    z = (x - mu) / x.std(ddof=0)
    return float(sr), n, float(np.mean(z ** 3)), float(np.mean(z ** 4))


def probabilistic_sharpe_ratio(sr: float, n: int, *, skew: float = 0.0,
                               kurtosis: float = 3.0,
                               sr_benchmark: float = 0.0) -> float:
    """P(true Sharpe > sr_benchmark) given the estimator's non-normal variance."""
    if n < 2:
        raise ValueError("need at least two observations")
    denom = math.sqrt(max(1e-12, 1.0 - skew * sr + (kurtosis - 1.0) / 4.0 * sr ** 2))
    return _N.cdf((sr - sr_benchmark) * math.sqrt(n - 1) / denom)


def expected_max_sharpe(n_trials: int, variance_trial_sr: float) -> float:
    """Expected maximum Sharpe of ``n_trials`` independent, skill-less trials."""
    if n_trials < 1:
        raise ValueError("n_trials must be >= 1")
    if variance_trial_sr < 0:
        raise ValueError("variance_trial_sr must be non-negative")
    if n_trials == 1:
        return 0.0
    z1 = _N.inv_cdf(1.0 - 1.0 / n_trials)
    z2 = _N.inv_cdf(1.0 - 1.0 / (n_trials * math.e))
    return math.sqrt(variance_trial_sr) * ((1.0 - _EULER_MASCHERONI) * z1
                                           + _EULER_MASCHERONI * z2)


def deflated_sharpe_ratio(sr: float, n: int, *, skew: float, kurtosis: float,
                          n_trials: int, variance_trial_sr: float) -> float:
    """Deflated Sharpe: PSR against the expected max Sharpe of the trial set."""
    sr_star = expected_max_sharpe(n_trials, variance_trial_sr)
    return probabilistic_sharpe_ratio(sr, n, skew=skew, kurtosis=kurtosis,
                                      sr_benchmark=sr_star)


def deflated_sharpe_from_trials(returns, trial_sharpes) -> dict | None:
    """Deflated Sharpe for a return series given the Sharpes of all trials."""
    sr, n, skew, kurt = sharpe_moments(returns)
    trials = np.asarray([t for t in trial_sharpes if t is not None and np.isfinite(t)],
                        dtype=float)
    if n < 2 or len(trials) < 2:
        return None
    variance = float(np.var(trials, ddof=1))
    dsr = deflated_sharpe_ratio(sr, n, skew=skew, kurtosis=kurt,
                                n_trials=len(trials), variance_trial_sr=variance)
    return {"sharpe": sr, "n": n, "n_trials": len(trials),
            "expected_max_sharpe": expected_max_sharpe(len(trials), variance),
            "deflated_sharpe": float(dsr)}


def _performance(matrix: np.ndarray, metric: str) -> np.ndarray:
    if metric == "mean":
        return matrix.mean(axis=0)
    if metric == "sharpe":
        mu = matrix.mean(axis=0)
        sd = matrix.std(axis=0, ddof=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(sd > 0, mu / sd, 0.0)
    raise ValueError("metric must be 'mean' or 'sharpe'")


def combinatorial_pbo(returns_matrix, *, n_splits: int = 16,
                      metric: str = "sharpe") -> dict:
    """Probability of Backtest Overfitting via CSCV.

    ``returns_matrix`` is (observations x strategies).  Rows are cut into
    ``n_splits`` blocks; for every way of choosing half as in-sample, the
    in-sample-best strategy's out-of-sample rank becomes a logit.  PBO is the
    share of logits at or below zero (in-sample winner below the OOS median).
    """
    M = np.asarray(returns_matrix, dtype=float)
    if M.ndim != 2 or M.shape[1] < 2:
        raise ValueError("returns_matrix must be 2D with >= 2 strategies")
    if n_splits < 2 or n_splits % 2 != 0:
        raise ValueError("n_splits must be an even integer >= 2")
    T, K = M.shape
    if T < n_splits:
        raise ValueError("more splits than observations")
    blocks = np.array_split(np.arange(T), n_splits)
    logits = []
    for combo in itertools.combinations(range(n_splits), n_splits // 2):
        chosen = set(combo)
        is_idx = np.concatenate([blocks[b] for b in combo])
        oos_idx = np.concatenate([blocks[b] for b in range(n_splits) if b not in chosen])
        best = int(np.argmax(_performance(M[is_idx], metric)))
        oos_ranks = pd.Series(_performance(M[oos_idx], metric)).rank(method="average")
        omega = float(oos_ranks.iloc[best]) / (K + 1)
        omega = min(max(omega, 1e-9), 1.0 - 1e-9)
        logits.append(math.log(omega / (1.0 - omega)))
    arr = np.asarray(logits, dtype=float)
    return {"pbo": float(np.mean(arr <= 0.0)), "n_combinations": len(arr),
            "median_logit": float(np.median(arr))}
