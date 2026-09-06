"""Small causal numerical primitives following the Pine reference formulas.

References: https://www.tradingview.com/pine-script-reference/v6/ and
https://www.tradingview.com/support/solutions/43000634738-supertrend/.
The implementation preserves Series indices and the explicit initialization
rules, rather than pandas' default exponentially weighted initialization.
These formula checks do not replace exported TradingView parity fixtures.
"""

from collections import deque
from numbers import Integral

import numpy as np
import pandas as pd


def _length(length):
    if isinstance(length, bool) or not isinstance(length, Integral) or length < 1:
        raise ValueError("length must be a positive integer")
    return int(length)


def _series(source):
    result = source.astype(float) if isinstance(source, pd.Series) else pd.Series(source, dtype=float)
    if np.isinf(result.to_numpy()).any():
        raise ValueError("infinite numerical inputs are unsupported")
    return result


def round_half_up(value):
    """Pine math.round: nearest integer, ties toward positive infinity."""
    if isinstance(value, pd.Series):
        return np.floor(value + 0.5)
    result = np.floor(np.asarray(value, dtype=float) + 0.5)
    return float(result) if result.ndim == 0 else result


def sma(source, length):
    """Mean of the last length non-na observations, including na gaps."""
    length = _length(length)
    source = _series(source)
    values = np.full(len(source), np.nan)
    window = deque(maxlen=length)
    for i, value in enumerate(source.to_numpy()):
        if not np.isnan(value):
            window.append(value)
        if len(window) == length:
            values[i] = sum(window) / length
    return pd.Series(values, index=source.index, name=source.name)


def ema(source, length):
    """EMA seeded with the first non-na observation; na leaves state intact."""
    length = _length(length)
    source = _series(source)
    alpha = 2.0 / (length + 1)
    values = np.full(len(source), np.nan)
    state = np.nan
    for i, value in enumerate(source.to_numpy()):
        if not np.isnan(value):
            state = value if np.isnan(state) else alpha * value + (1.0 - alpha) * state
        values[i] = state
    return pd.Series(values, index=source.index, name=source.name)


def rma(source, length):
    """Wilder average seeded by the first length non-na values' SMA."""
    length = _length(length)
    source = _series(source)
    alpha = 1.0 / length
    values = np.full(len(source), np.nan)
    seed = []
    state = np.nan
    for i, value in enumerate(source.to_numpy()):
        if not np.isnan(value):
            if np.isnan(state):
                seed.append(value)
                if len(seed) == length:
                    state = sum(seed) / length
            else:
                state = alpha * value + (1.0 - alpha) * state
        values[i] = state
    return pd.Series(values, index=source.index, name=source.name)


def atr(bars, length):
    """RMA of true range; missing prior close uses current high minus low."""
    previous_close = _series(bars["close"]).shift(1)
    high, low = _series(bars["high"]), _series(bars["low"])
    true_range = pd.concat([high - low, (high - previous_close).abs(),
                            (low - previous_close).abs()], axis=1).max(axis=1, skipna=False)
    true_range = true_range.where(previous_close.notna(), high - low)
    return rma(true_range, length).rename("atr")


def rsi(source, length):
    """Pine's RMA gain/loss formula; unresolved and zero/zero remain na."""
    source = _series(source)
    # Ignore missing observations when selecting the previous source value.
    change = source - source.ffill().shift(1)
    gain = rma(change.clip(lower=0), length)
    loss = rma((-change).clip(lower=0), length)
    with np.errstate(divide="ignore", invalid="ignore"):
        result = 100.0 - 100.0 / (1.0 + gain / loss)
    return result.rename("rsi")


def supertrend(bars, factor, length):
    """Pine Supertrend with +1 bearish/-1 bullish reference direction.

    ``factor`` accepts a scalar or Series aligned exactly to bars. Comparisons
    follow Pine's nine fractional digit float comparison rule. Direction is
    initialized down until the preceding bar has an available ATR.
    """
    volatility = atr(bars, length).to_numpy()
    high = _series(bars["high"]).to_numpy()
    low = _series(bars["low"]).to_numpy()
    close = _series(bars["close"]).to_numpy()
    if isinstance(factor, pd.Series):
        if not factor.index.equals(bars.index):
            raise ValueError("factor index must equal bars index")
        factors = _series(factor).to_numpy()
    elif np.isscalar(factor):
        factors = np.full(len(bars), float(factor))
    else:
        factors = np.asarray(factor, dtype=float)
        if factors.shape != (len(bars),):
            raise ValueError("factor must have one value per bar")
    if np.isinf(factors).any():
        raise ValueError("infinite factor is unsupported")
    upper = np.full(len(bars), np.nan)
    lower = np.full(len(bars), np.nan)
    trend = np.full(len(bars), np.nan)
    direction = np.ones(len(bars), dtype=float)
    rounded = lambda value: np.floor(value * 1e9 + 0.5) / 1e9
    for i in range(len(bars)):
        raw_upper = (high[i] + low[i]) / 2.0 + factors[i] * volatility[i]
        raw_lower = (high[i] + low[i]) / 2.0 - factors[i] * volatility[i]
        prior_upper = upper[i - 1] if i and not np.isnan(upper[i - 1]) else 0.0
        prior_lower = lower[i - 1] if i and not np.isnan(lower[i - 1]) else 0.0
        prior_close = close[i - 1] if i else np.nan
        lower[i] = raw_lower if (rounded(raw_lower) > rounded(prior_lower)
                                  or rounded(prior_close) < rounded(prior_lower)) else prior_lower
        upper[i] = raw_upper if (rounded(raw_upper) < rounded(prior_upper)
                                  or rounded(prior_close) > rounded(prior_upper)) else prior_upper
        if not i or np.isnan(volatility[i - 1]):
            direction[i] = 1.0
        elif rounded(trend[i - 1]) == rounded(prior_upper):
            direction[i] = -1.0 if rounded(close[i]) > rounded(upper[i]) else 1.0
        else:
            direction[i] = 1.0 if rounded(close[i]) < rounded(lower[i]) else -1.0
        trend[i] = lower[i] if direction[i] == -1 else upper[i]
        # Pine built-in outputs no line while ATR is warming up.
        if np.isnan(volatility[i]):
            trend[i] = np.nan
    return pd.DataFrame({"supertrend": trend, "direction": direction}, index=bars.index)
