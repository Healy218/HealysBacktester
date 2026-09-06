"""Observation contracts for completed-bar TradingView volume features."""
from __future__ import annotations

import numpy as np
import pandas as pd

from v3._tv_trend_support import integer, validate_bars


def profile_observations(bars, bar_minutes, as_of=None, *, logarithmic=False):
    validate_bars(bars)
    bar_minutes = integer("bar_minutes", bar_minutes)
    if not isinstance(bars.index, pd.DatetimeIndex) or bars.index.tz is None:
        raise ValueError("profile features require timezone-aware bar-open timestamps")
    if "Volume" not in bars or not pd.api.types.is_numeric_dtype(bars.Volume) or pd.api.types.is_bool_dtype(bars.Volume):
        raise ValueError("Volume must be a numeric column")
    volume = bars.Volume.to_numpy(dtype=float)
    if not np.isfinite(volume).all() or (volume < 0).any():
        raise ValueError("Volume must be finite and nonnegative")
    if logarithmic and (bars.Close <= 0).any():
        raise ValueError("log regression requires positive Close prices")
    duration = pd.Timedelta(minutes=bar_minutes)
    if len(bars) > 1 and (bars.index[1:] - bars.index[:-1] < duration).any():
        raise ValueError("bar-open timestamps overlap declared bar duration")
    available = bars.index + duration
    if as_of is not None:
        as_of = pd.Timestamp(as_of)
        if as_of.tz is None:
            raise ValueError("as_of must be timezone-aware")
        if (available > as_of).any():
            raise ValueError("forming/future bars exceed as_of availability")
    return available


def frame_from_rows(rows, index, prototype, *, timestamp_columns=()):
    """Preserve empty and prefix dtypes, including all-NaT timestamp columns."""
    frame = pd.DataFrame(rows, index=index, columns=prototype)
    for name, value in prototype.items():
        if name in timestamp_columns:
            frame[name] = pd.to_datetime(frame[name], utc=True).dt.tz_convert(index.tz)
        elif isinstance(value, bool):
            frame[name] = frame[name].astype(bool)
        elif isinstance(value, int):
            frame[name] = frame[name].astype(np.int64)
        elif isinstance(value, float):
            frame[name] = frame[name].astype(float)
        else:
            frame[name] = frame[name].astype(object)
    return frame
