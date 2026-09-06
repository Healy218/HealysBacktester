"""Input contracts shared by the isolated TradingView trend adaptations.

The caller supplies completed bars only. Index values are observation labels;
no shift converts a forming bar into a completed bar inside these functions.
"""
from __future__ import annotations

import numbers

import numpy as np
import pandas as pd


def validate_bars(bars: pd.DataFrame) -> None:
    required = ["Open", "High", "Low", "Close"]
    missing = set(required).difference(bars.columns)
    if missing:
        raise ValueError(f"missing OHLC columns: {sorted(missing)}")
    if any(not pd.api.types.is_numeric_dtype(bars[column])
           or pd.api.types.is_bool_dtype(bars[column]) for column in required):
        raise ValueError("OHLC columns must have numeric dtypes")
    if not bars.index.is_unique or not bars.index.is_monotonic_increasing:
        raise ValueError("bar index must be unique and increasing")
    values = bars[required].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("trend ports require finite OHLC; missing bars must not be fabricated")
    if ((bars.High < bars.Low) | (bars.High < bars[["Open", "Close"]].max(axis=1))
            | (bars.Low > bars[["Open", "Close"]].min(axis=1))).any():
        raise ValueError("invalid OHLC range")


def integer(name: str, value: int, minimum: int = 1,
            maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, numbers.Integral):
        raise ValueError(f"{name} must be an integer")
    value = int(value)
    if value < minimum or (maximum is not None and value > maximum):
        raise ValueError(f"{name} outside [{minimum}, {maximum or 'infinity'}]")
    return value


def positive(name: str, value: float, minimum: float = 0.0,
             maximum: float | None = None) -> float:
    value = float(value)
    if not np.isfinite(value) or value <= 0 or value < minimum or (
            maximum is not None and value > maximum):
        raise ValueError(f"invalid {name}: {value}")
    return value


def cross_over(value: pd.Series, level: pd.Series) -> pd.Series:
    value, level = comparison_value(value), comparison_value(level)
    return (value > level) & (value.shift(1) <= level.shift(1))


def cross_under(value: pd.Series, level: pd.Series) -> pd.Series:
    value, level = comparison_value(value), comparison_value(level)
    return (value < level) & (value.shift(1) >= level.shift(1))


def comparison_value(value):
    """Pine comparisons round float operands to nine fractional digits.

    Preserve full precision in arithmetic; apply only at comparison sites.
    https://www.tradingview.com/pine-script-docs/language/type-system/#float
    """
    return np.floor(value * 1_000_000_000.0 + 0.5) / 1_000_000_000.0


def pine_ohlc(bars: pd.DataFrame) -> pd.DataFrame:
    """Map the repository's OHLC contract to shared Pine primitive names."""
    return bars[["Open", "High", "Low", "Close"]].rename(columns=str.lower)
