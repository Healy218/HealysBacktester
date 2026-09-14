# SPDX-License-Identifier: CC-BY-NC-SA-4.0
# Adapted from HTF Log-Regression Volume Profile, © BigBeluga.
# https://www.tradingview.com/script/kwXpL7yZ-HTF-Log-Regression-Volume-Profile-BigBeluga/
# https://creativecommons.org/licenses/by-nc-sa/4.0/
# Changes: numerical snapshots, explicit exchange-period flags and availability;
# drawing objects/colors omitted, undefined zero-height states marked invalid.
"""Developing and completed HTF log-profile features from pinned Pine v4.

No external HTF OHLC is requested by this source. The caller supplies exact
exchange-aligned timeframe.change flags; UTC resampling is not equivalent.
Developing regression fits can revise earlier chart geometry, so every row
stores only the fit known then. Finished profiles are never backfilled.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from v3._tv_profile_support import profile_observations, frame_from_rows
from v3._tv_trend_support import comparison_value as cmp, integer
from v3.pine_compat import round_half_up


def auto_htf_period(chart_period: str) -> str:
    """Literal source mapping, including its distinction between D and 1D."""
    if not isinstance(chart_period, str) or not chart_period:
        raise ValueError("chart_period must be a nonempty Pine timeframe string")
    try:
        number = float(chart_period)
    except ValueError:
        number = np.nan
    if np.isfinite(number):
        return ("240" if number <= 1 else "720" if number < 15 else "2D" if number < 60
                else "1W" if number < 240 else "1M" if number < 1440 else "12M")
    return "2M" if chart_period == "1D" else "3M" if chart_period in ("2D", "3D") else (
        "12M" if chart_period in ("W", "1W", "1M") else "D")


_NUMERICAL = {
    "regression_slope": np.nan, "regression_intercept": np.nan,
    "regression_start": np.nan, "regression_end": np.nan, "deviation": np.nan,
    "session_high": np.nan, "session_low": np.nan, "session_midpoint": np.nan,
    "upper_start": np.nan, "upper_end": np.nan, "lower_start": np.nan, "lower_end": np.nan,
    "buy_volume": 0., "sell_volume": 0., "directional_volume": 0., "doji_volume": 0.,
    "delta_pct": 0., "allocated_volume": 0., "excluded_volume": 0.,
    "max_bin_volume": 0., "poc_bin_index": -1,
    "poc_start": np.nan, "poc_end": np.nan, "poc_line_start_index": -1,
    "poc_line_start_price": np.nan, "poc_line_end_index": -1,
    "poc_up": False, "poc_visible": False, "profile_ready": False,
    "profile_status": "regression_warmup",
}


def _session_values(opens, highs, lows, closes, volumes, length, start, end,
                    channel_width, bin_count, show_profile, show_poc, include_bins):
    row = dict(_NUMERICAL)
    if include_bins:
        row["volume_bins"] = tuple(0. for _ in range(bin_count))
    opn, high, low, close, vol = (a[start:end + 1] for a in (opens, highs, lows, closes, volumes))
    row.update(session_high=float(high.max()), session_low=float(low.min()),
               session_midpoint=float((high.max() + low.min()) / 2))
    # Source loops newest-to-oldest; doji volume contributes to profile bins
    # but neither buy/sell nor their delta denominator.
    buy = sell = doji = 0.
    for o, c, v in zip(opn[::-1], close[::-1], vol[::-1]):
        if cmp(c) > cmp(o):
            buy += v
        elif cmp(c) < cmp(o):
            sell += v
        else:
            doji += v
    total = buy + sell
    row.update(buy_volume=buy, sell_volume=sell, directional_volume=total,
               doji_volume=doji, delta_pct=(buy - sell) / total * 100 if total > 0 else 0.)
    if length > len(close):
        row.update(profile_status="partial_initial_session", excluded_volume=float(vol.sum()))
        return row
    row["deviation"] = float(np.std(close, ddof=0))
    if length < 2:
        row["excluded_volume"] = float(vol.sum())
        return row  # regression denominator is zero on a one-bar session
    sx = sy = sxx = sxy = 0.
    for i, value in enumerate(close[::-1], 1):
        logged = math.log(value)
        sx += i
        sy += logged
        sxx += i * i
        sxy += logged * i
    slope = (length * sxy - sx * sy) / (length * sxx - sx * sx)
    intercept = (sy - slope * sx) / length
    reg_start, reg_end = math.exp(intercept + slope * length), math.exp(intercept)
    deviation = row["deviation"]
    upper_start, upper_end = reg_start + deviation * channel_width, reg_end + deviation * channel_width
    lower_start, lower_end = reg_start - deviation * channel_width, reg_end - deviation * channel_width
    row.update(regression_slope=slope, regression_intercept=intercept,
               regression_start=reg_start, regression_end=reg_end,
               upper_start=upper_start, upper_end=upper_end,
               lower_start=lower_start, lower_end=lower_end)
    bins = np.zeros(bin_count)
    allocated = excluded = 0.
    zero_height = False
    if show_profile:
        for i, (price, volume) in enumerate(zip(close[::-1], vol[::-1])):
            mid = math.exp(intercept + slope * i)
            upper, lower = mid + deviation * channel_width, mid - deviation * channel_width
            if cmp(lower) <= cmp(price) <= cmp(upper):
                height = upper - lower
                if height == 0:
                    zero_height = True
                    break
                location = min(max(math.floor((price - lower) / (height / bin_count)), 0), bin_count - 1)
                bins[location] += volume
                allocated += volume
            else:
                excluded += volume
    else:
        excluded = float(vol.sum())
    if zero_height:
        row.update(profile_status="undefined_zero_channel_height", allocated_volume=np.nan,
                   excluded_volume=np.nan, max_bin_volume=np.nan)
        if include_bins:
            row["volume_bins"] = tuple(np.nan for _ in range(bin_count))
        return row
    row.update(allocated_volume=allocated, excluded_volume=excluded,
               max_bin_volume=float(bins.max()),
               profile_status="disabled" if not show_profile else "zero_allocated_volume")
    if include_bins:
        row["volume_bins"] = tuple(float(v) for v in bins)
    if bins.max() > 0:
        poc = int(np.argmax(bins))
        bin_step = (upper_start - lower_start) / bin_count
        offset = (poc + .5) * bin_step
        poc_start, poc_end = lower_start + offset, lower_end + offset
        source_start = end - length + 1
        # Actual drawing starts15 bars after source_start, even when that is
        # beyond the current bar. Geometry is not future price information.
        poc_line_start = poc_start - (poc_start - poc_end) / (length - 1) * 15
        row.update(poc_bin_index=poc, poc_start=poc_start, poc_end=poc_end,
                   poc_line_start_index=source_start + 15, poc_line_start_price=poc_line_start,
                   poc_line_end_index=end, poc_up=bool(cmp(poc_end) >= cmp(poc_start)),
                   poc_visible=show_poc, profile_ready=True, profile_status="ready")
    return row


def htf_log_regression_profile(bars, htf_change, *, chart_period="15", auto_htf=True,
                               manual_htf="D", channel_width=1., bin_count=30,
                               show_profile=True, show_poc=True, bar_minutes=15,
                               as_of=None, include_bins=False, observation_positions=None):
    """Return current and most-recent-completed session profiles.

    ``htf_change`` must be a nonmissing boolean Series aligned to bars, captured
    or generated from the exchange's actual Pine timeframe.change period. Its
    optional ``attrs['htf_period']`` must match the selected period. At15min the
    source auto-period is2D. Calendar derivation is intentionally external.

    New rows are known only at available_at (bar close). A completed snapshot
    is published on the first observed bar of the next HTF session, retains its
    previous observation time separately, and is never assigned to earlier rows.
    """
    available = profile_observations(bars, bar_minutes, as_of, logarithmic=True)
    positions = list(range(len(bars))) if observation_positions is None else list(observation_positions)
    if (any(type(p) is not int or not 0 <= p < len(bars) for p in positions)
            or positions != sorted(set(positions))):
        raise ValueError("observations must be distinct ordered full-history positions")
    requested = set(positions)
    if not isinstance(chart_period, str) or not chart_period.isdigit() or int(chart_period) != bar_minutes:
        raise ValueError("this adapter requires minute chart_period matching bar_minutes")
    bin_count = integer("bin_count", bin_count, 5, 100)
    channel_width = float(channel_width)
    if not np.isfinite(channel_width):
        raise ValueError("channel_width must be finite")
    for name, value in (("auto_htf", auto_htf), ("show_profile", show_profile),
                        ("show_poc", show_poc), ("include_bins", include_bins)):
        if not isinstance(value, bool):
            raise ValueError(f"{name} must be boolean")
    period = auto_htf_period(chart_period) if auto_htf else manual_htf
    if not isinstance(period, str) or not period:
        raise ValueError("manual_htf must be a nonempty Pine timeframe string")
    if (not isinstance(htf_change, pd.Series) or not htf_change.index.equals(bars.index)
            or not pd.api.types.is_bool_dtype(htf_change) or htf_change.isna().any()):
        raise ValueError("htf_change must be an aligned nonmissing boolean Series")
    if htf_change.attrs.get("htf_period", period) != period:
        raise ValueError("HTF flag period does not match selected source period")
    # Completed state depends only on the final observation of each previous
    # HTF session. Retain all flags/history, but avoid drawing unused developing
    # profiles. The original session calculation and summation order stay exact.
    needed = requested | {int(i) - 1 for i in np.flatnonzero(htf_change.to_numpy()) if i > 0}
    arrays = [bars[c].to_numpy(float) for c in ("Open", "High", "Low", "Close", "Volume")]
    numerical = dict(_NUMERICAL)
    if include_bins:
        numerical["volume_bins"] = ()
    prototype = {"available_at": None, "new_htf": False, "htf_length": 1,
                 "session_start_index": -1, "session_start_at": None,
                 "partial_initial_session": False, "session_completed": False,
                 "completed_available_at": None, "completed_last_observed_at": None,
                 "completed_session_start_at": None, "completed_htf_length": 0,
                 "completed_partial_initial_session": False, **numerical,
                 **{"completed_" + key: value for key, value in numerical.items()}}
    rows = []
    length, observed_start = 1, 0
    partial = True
    previous = None
    completed = {key: value for key, value in prototype.items() if key.startswith("completed_")}
    for i, changed in enumerate(htf_change):
        ended = bool(changed and i > 0)
        if changed:
            if previous is not None:
                completed = {"completed_" + key: previous[key] for key in numerical}
                completed.update(completed_available_at=available[i],
                                 completed_last_observed_at=available[i - 1],
                                 completed_session_start_at=previous["session_start_at"],
                                 completed_htf_length=previous["htf_length"],
                                 completed_partial_initial_session=previous["partial_initial_session"])
            length, observed_start, partial = 1, i, False
        else:
            length += 1  # source does this even on bar0 if its flag is false
        if i not in needed:
            continue
        start_index = i - length + 1
        values = _session_values(*arrays, length, observed_start, i, channel_width,
                                  bin_count, show_profile, show_poc, include_bins)
        row = {"available_at": available[i], "new_htf": bool(changed), "htf_length": length,
               "session_start_index": start_index,
               "session_start_at": bars.index[start_index] if start_index >= 0 else pd.NaT,
               "partial_initial_session": partial, "session_completed": ended,
               **values, **completed}
        if i in requested:
            rows.append(row)
        previous = row
    timestamps = ("available_at", "session_start_at", "completed_available_at",
                  "completed_last_observed_at", "completed_session_start_at")
    result = frame_from_rows(rows, bars.index[positions], prototype, timestamp_columns=timestamps)
    result.attrs.update(source="kwXpL7yZ/v4", htf_period=period,
                        htf_flags_contract="caller-supplied exchange-aligned timeframe.change",
                        admission_status="feature-only; pending exported TradingView fixtures",
                        index_kind="bar_open", bar_minutes=bar_minutes)
    return result
