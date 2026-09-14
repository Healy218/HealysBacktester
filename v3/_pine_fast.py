"""Optional Numba evaluation of the existing Pine recurrences, no fastmath."""
import numpy as np
from numba import njit


@njit(cache=True)
def average(values, length, wilder):
    result = np.full(len(values), np.nan)
    alpha = 1. / length if wilder else 2. / (length + 1)
    state, total, count = np.nan, 0., 0
    for i, value in enumerate(values):
        if not np.isnan(value):
            if np.isnan(state):
                if wilder:
                    total += value; count += 1
                    if count == length: state = total / length
                else:
                    state = value
            else:
                state = alpha * value + (1. - alpha) * state
        result[i] = state
    return result


@njit(cache=True)
def rounded(value):
    return np.floor(value * 1e9 + .5) / 1e9


@njit(cache=True)
def supertrend_core(high, low, close, factors, volatility):
    n = len(high)
    upper, lower, trend = np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)
    direction = np.ones(n)
    for i in range(n):
        raw_upper = (high[i] + low[i]) / 2. + factors[i] * volatility[i]
        raw_lower = (high[i] + low[i]) / 2. - factors[i] * volatility[i]
        prior_upper = upper[i-1] if i and not np.isnan(upper[i-1]) else 0.
        prior_lower = lower[i-1] if i and not np.isnan(lower[i-1]) else 0.
        prior_close = close[i-1] if i else np.nan
        lower[i] = raw_lower if rounded(raw_lower) > rounded(prior_lower) or rounded(prior_close) < rounded(prior_lower) else prior_lower
        upper[i] = raw_upper if rounded(raw_upper) < rounded(prior_upper) or rounded(prior_close) > rounded(prior_upper) else prior_upper
        if not i or np.isnan(volatility[i-1]): direction[i] = 1.
        elif rounded(trend[i-1]) == rounded(prior_upper): direction[i] = -1. if rounded(close[i]) > rounded(upper[i]) else 1.
        else: direction[i] = 1. if rounded(close[i]) < rounded(lower[i]) else -1.
        trend[i] = lower[i] if direction[i] == -1 else upper[i]
        if np.isnan(volatility[i]): trend[i] = np.nan
    return trend, direction
