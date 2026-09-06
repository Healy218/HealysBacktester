"""Causal input and primitive helpers for the source-backed setup adaptations."""
from __future__ import annotations

import numpy as np
import pandas as pd

from v3._tv_trend_support import comparison_value as cmp, integer, validate_bars


def timed_bars(bars, bar_minutes=15, as_of=None):
    validate_bars(bars)
    if not isinstance(bars.index, pd.DatetimeIndex) or bars.index.tz is None:
        raise ValueError("requires timezone-aware bar-open timestamps")
    duration = pd.Timedelta(minutes=integer("bar_minutes", bar_minutes))
    if len(bars) > 1 and (bars.index[1:] - bars.index[:-1] < duration).any():
        raise ValueError("bars overlap the declared duration")
    available = bars.index + duration
    if as_of is not None:
        as_of = pd.Timestamp(as_of)
        if as_of.tz is None or (available > as_of).any():
            raise ValueError("as_of must be timezone-aware and exclude forming bars")
    return available


def confirmed_pivots(values, length, *, high):
    """Rightmost tied extremum; exported Pine tie fixtures still required."""
    values = np.asarray(values, dtype=float)
    tested = cmp(values)
    result = np.full(len(values), np.nan)
    for i in range(2 * length, len(values)):
        p = i - length
        left, right = tested[p - length:p], tested[p + 1:i + 1]
        good = ((tested[p] >= left).all() and (tested[p] > right).all()) if high else (
            (tested[p] <= left).all() and (tested[p] < right).all())
        if good:
            result[i] = values[p]
    return result


def aligned_observations(values, index, available, columns):
    """Explicit completed external observations, never a hidden future merge."""
    if not isinstance(values, pd.DataFrame) or not values.index.equals(index):
        raise ValueError("external observations must align exactly to bar index")
    if not set(columns + ["available_at"]).issubset(values):
        raise ValueError("external observations need value columns and available_at")
    at = pd.to_datetime(values.available_at)
    if not isinstance(at.dtype, pd.DatetimeTZDtype):
        raise ValueError("external available_at must be timezone-aware")
    present = values[columns].notna().any(axis=1)
    if (present & (at.isna() | (at > pd.Series(available, index=index)))).any():
        raise ValueError("external observation was unavailable at this bar close")
    for column in columns:
        if not pd.api.types.is_numeric_dtype(values[column]) or pd.api.types.is_bool_dtype(values[column]):
            raise ValueError("external observations must be numeric")
        if np.isinf(values[column].to_numpy(dtype=float)).any():
            raise ValueError("external observations cannot be infinite")
    return values[columns].astype(float)


def percentile_rank_previous(values, length):
    """Percent of the previous length values <= current, excluding current.

    Official Pine debugging examples identify a new lowest value with rank0:
    https://www.tradingview.com/pine-script-docs/v5/writing/debugging/
    """
    values = np.asarray(values, dtype=float)
    out = np.full(len(values), np.nan)
    tested = cmp(values)
    for i in range(length, len(values)):
        previous = tested[i - length:i]
        if np.isfinite(previous).all() and np.isfinite(tested[i]):
            out[i] = 100 * np.count_nonzero(previous <= tested[i]) / length
    return out
