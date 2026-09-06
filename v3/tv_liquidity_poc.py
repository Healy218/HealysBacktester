# SPDX-License-Identifier: CC-BY-NC-SA-4.0
# Adapted from Structural Liquidity & POC Matrix, © BigBeluga.
# https://www.tradingview.com/script/I8HrQVRv-Structural-Liquidity-POC-Matrix-BigBeluga/
# https://creativecommons.org/licenses/by-nc-sa/4.0/
# Changes: causal completed-prefix profile snapshots and numerical events;
# drawing objects/colors omitted, undefined profile states explicitly reported.
"""Liquidity sweeps and close-allocated volume bins from pinned Pine v1.

The source computes its profile only on barstate.islast. Historical profile
rows here mean "the last-bar result of this completed prefix", never a final
chart profile painted backwards. Sweep labels are events, not trade entries.
"""
from __future__ import annotations

import numpy as np

from v3._tv_profile_support import profile_observations, frame_from_rows
from v3._tv_trend_support import comparison_value as cmp, integer, pine_ohlc
from v3.pine_compat import atr, round_half_up


def structural_liquidity_poc(bars, *, liquidity_length=100, fade_liquidity=100,
                             show_poc=True, bar_minutes=15, as_of=None,
                             include_bins=False, max_profile_bins=100_000):
    """Return observed liquidity state, label events and current-prefix POC.

    Finite nonnegative volume is required. ATR100 × .2 defines the bin width;
    each close contributes its entire bar volume to one bin if in range.
    Undefined ATR/zero-width states return no profile with an explicit status.
    Excessively large arrays fail rather than silently changing resolution.
    Original drawing-buffer limits are an external fixture concern: retain a
    fixed calculation origin and never truncate/rebase an existing history.
    """
    available = profile_observations(bars, bar_minutes, as_of)
    liquidity_length = integer("liquidity_length", liquidity_length)
    fade_liquidity = integer("fade_liquidity", fade_liquidity, -(2**31), 2**31 - 1)
    max_profile_bins = integer("max_profile_bins", max_profile_bins)
    if not isinstance(show_poc, bool) or not isinstance(include_bins, bool):
        raise ValueError("show_poc and include_bins must be boolean")
    high, low, close, volume = (bars[key].to_numpy(float) for key in ("High", "Low", "Close", "Volume"))
    step = (atr(pine_ohlc(bars), 100) * .2).to_numpy()
    top = bottom = np.nan
    top_count = bottom_count = 0
    top_index = bottom_index = 0
    profile_top = profile_bottom = 0.
    tint = 0
    prototype = {"available_at": None, "rolling_high": np.nan, "rolling_low": np.nan,
                 "new_rolling_high": False, "new_rolling_low": False,
                 "liquidity_top": np.nan, "liquidity_bottom": np.nan,
                 "top_count": 0, "bottom_count": 0, "top_sweep": False, "bottom_sweep": False,
                 "top_anchor_changed": False, "bottom_anchor_changed": False,
                 "top_anchor_index": 0, "bottom_anchor_index": 0, "profile_start_index": 0,
                 "profile_start_at": None, "profile_top": 0., "profile_bottom": 0.,
                 "profile_midpoint": 0., "profile_tint_direction": 0,
                 "bin_step": np.nan, "bin_count": 0, "max_bin_volume": np.nan,
                 "allocated_volume": np.nan, "excluded_volume": np.nan,
                 "poc_bin_index": -1, "poc_price": np.nan, "poc_visible": False,
                 "profile_ready": False, "profile_status": "atr_warmup"}
    if include_bins:
        prototype["volume_bins"] = ()
    rows = []
    for i in range(len(bars)):
        left = max(0, i - liquidity_length + 1)
        highest, lowest = high[left:i + 1].max(), low[left:i + 1].min()
        high_event, low_event = bool(cmp(high[i]) == cmp(highest)), bool(cmp(low[i]) == cmp(lowest))
        previous_top, previous_bottom = top, bottom
        if high_event and top_count == 0:
            top_count = 1
        if high_event:
            top = highest
        if top_count >= 1:
            top_count += 1
        if top_count == fade_liquidity:
            top_count, top = 0, np.nan
        top_anchor = top_count == 2
        if top_anchor:
            top_index, profile_top = i, top
        # Pine comparison with either na is false; np.nan != finite would be
        # true in Python and would destroy the source's initial anchor state.
        top_sweep = bool(np.isfinite(top) and np.isfinite(previous_top) and cmp(top) != cmp(previous_top))
        if top_sweep:
            top_count, top = 0, np.nan
        if low_event and bottom_count == 0:
            bottom_count = 1
        if low_event:
            bottom = lowest
        if bottom_count >= 1:
            bottom_count += 1
        if bottom_count == fade_liquidity:
            bottom_count, bottom = 0, np.nan
        bottom_anchor = bottom_count == 2
        if bottom_anchor:
            bottom_index, profile_bottom = i, bottom
        bottom_sweep = bool(np.isfinite(bottom) and np.isfinite(previous_bottom)
                            and cmp(bottom) != cmp(previous_bottom))
        if bottom_sweep:
            bottom_count, bottom = 0, np.nan
        if low_event:
            tint = -1
        if high_event:
            tint = 1  # source high-event assignment has priority on outside bars
        start = min(bottom_index, top_index)
        row = dict(prototype)
        row.update(available_at=available[i], rolling_high=highest, rolling_low=lowest,
                   new_rolling_high=high_event, new_rolling_low=low_event,
                   liquidity_top=top, liquidity_bottom=bottom, top_count=top_count,
                   bottom_count=bottom_count, top_sweep=top_sweep, bottom_sweep=bottom_sweep,
                   top_anchor_changed=top_anchor, bottom_anchor_changed=bottom_anchor,
                   top_anchor_index=top_index, bottom_anchor_index=bottom_index,
                   profile_start_index=start, profile_start_at=bars.index[start],
                   profile_top=profile_top, profile_bottom=profile_bottom,
                   profile_midpoint=(profile_top + profile_bottom) / 2,
                   profile_tint_direction=tint, bin_step=step[i])
        if np.isfinite(step[i]) and step[i] > 0:
            ratio = (profile_top - profile_bottom) / step[i]
            if not np.isfinite(ratio):
                raise ValueError("non-finite profile bin count")
            count = max(1, int(round_half_up(ratio)))
            if count > max_profile_bins:
                raise ValueError(f"profile needs {count} bins, exceeding max_profile_bins")
            bins = np.zeros(count)
            indices = np.floor((close[start:i + 1] - profile_bottom) / step[i])
            accepted = (indices >= 0) & (indices < count)
            # np.add.at preserves accumulation order from the oldest bar to
            # the current bar, as the source's start..bar_index loop does.
            np.add.at(bins, indices[accepted].astype(int), volume[start:i + 1][accepted])
            poc = int(np.argmax(bins))  # first maximum wins even if all zero
            max_volume = float(bins[poc])
            row.update(bin_count=count, max_bin_volume=max_volume,
                       allocated_volume=float(bins.sum()),
                       excluded_volume=float(volume[start:i + 1][~accepted].sum()),
                       poc_bin_index=poc, poc_price=profile_bottom + (poc + .5) * step[i],
                       poc_visible=bool(show_poc and max_volume > 0),
                       profile_ready=max_volume > 0,
                       profile_status="ready" if max_volume > 0 else "zero_allocated_volume")
            # The source computes this POC price for a zero-volume profile but
            # its drawing widths divide by zero. Expose the number separately
            # from its unusable profile/visibility status.
            if include_bins:
                row["volume_bins"] = tuple(float(value) for value in bins)
        elif np.isfinite(step[i]):
            row["profile_status"] = "zero_atr"
        rows.append(row)
    result = frame_from_rows(rows, bars.index, prototype,
                             timestamp_columns=("available_at", "profile_start_at"))
    result.attrs.update(source="I8HrQVRv/v1", snapshot_basis="each completed prefix's last bar",
                        admission_status="feature-only; pending exported TradingView fixtures",
                        index_kind="bar_open", bar_minutes=bar_minutes)
    return result
