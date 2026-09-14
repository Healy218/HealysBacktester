# SPDX-License-Identifier: MPL-2.0
# Adapted from Support Resistance Channels, © LonesomeTheBlue.
# https://www.tradingview.com/script/Ej53t8Wv-Support-Resistance-Channels/
# https://mozilla.org/MPL/2.0/ (publication 6)
# Changes: Python completed-bar channel snapshots and break signals, no drawing.
"""Causal pivot channels, retaining the source's selection and alert order.

Pivots become available after their right-side confirmation bars. Boxes in the
Pine script extend across historical chart space; this port preserves only
the channel state actually known on each row. TradingView fixtures are pending,
including exact ta.pivot* behavior when candidate extrema tie.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import os

from v3._tv_trend_support import comparison_value as cmp, integer, validate_bars


def _pivot(values, bar, period, high):
    if bar < 2 * period:
        return np.nan
    pivot = bar - period
    candidate = cmp(values[pivot])
    left = cmp(values[pivot - period:pivot])
    right = cmp(values[pivot + 1:bar + 1])
    # Latest equal extremum wins. This built-in edge remains a parity gate.
    valid = ((left <= candidate).all() and (right < candidate).all()) if high else (
        (left >= candidate).all() and (right > candidate).all())
    return values[pivot] if valid else np.nan


def support_resistance_channels(bars, *, pivot_period=10, pivot_source="High/Low",
                                channel_width_pct=5, minimum_strength=1,
                                max_channels=6, lookback=290):
    """Return ten raw channel slots, visible-channel alerts and pivot metadata.

    Optional source moving-average graphics do not affect these outputs and
    are omitted. Empty source slots are reported as na; alerts retain the
    source's raw zero sentinel behavior. ``pivot_index`` is historical metadata,
    never an instruction to backdate the row's signal.
    """
    validate_bars(bars)
    pivot_period = integer("pivot_period", pivot_period, 4, 30)
    channel_width_pct = integer("channel_width_pct", channel_width_pct, 1, 8)
    minimum_strength = integer("minimum_strength", minimum_strength)
    max_channels = integer("max_channels", max_channels, 1, 10)
    lookback = integer("lookback", lookback, 100, 400)
    if pivot_source not in ("High/Low", "Close/Open"):
        raise ValueError("pivot_source must be High/Low or Close/Open")
    high, low, close = (bars[c].to_numpy(float) for c in ("High", "Low", "Close"))
    src_high = high if pivot_source == "High/Low" else bars[["Open", "Close"]].max(axis=1).to_numpy()
    src_low = low if pivot_source == "High/Low" else bars[["Open", "Close"]].min(axis=1).to_numpy()
    if os.environ.get("NN_META_V6_ACCELERATE") == "1":
        from v3._sr_fast import channels
        values = channels(high, low, close, src_high, src_low, pivot_period,
                          channel_width_pct, minimum_strength, max_channels, lookback)
        columns = ["pivot_high", "pivot_low", "pivot_index", "pivot_confirmed", "channel_width",
                   "pivot_count", "inside_channel", "bull_signal", "bear_signal"] + [
            f"channel_{slot}_{field}" for slot in range(1,11) for field in ("top","bottom","strength")]
        result = pd.DataFrame(values, index=bars.index, columns=columns)
        for column in ("pivot_confirmed", "inside_channel", "bull_signal", "bear_signal"):
            result[column] = result[column].astype(bool)
        result["pivot_count"] = result["pivot_count"].astype(int)
        return result
    pivots, locations = [], []
    levels = np.zeros((10, 2))
    strengths = np.zeros(10)
    rows = []
    for i in range(len(bars)):
        ph = _pivot(src_high, i, pivot_period, True)
        pl = _pivot(src_low, i, pivot_period, False)
        has_high, has_low = not np.isnan(ph) and ph != 0, not np.isnan(pl) and pl != 0
        width = (high[max(0, i - 299):i + 1].max() - low[max(0, i - 299):i + 1].min()) * channel_width_pct / 100
        if has_high or has_low:
            pivots.insert(0, ph if has_high else pl)
            locations.insert(0, i)
            while locations and i - locations[-1] > lookback:
                locations.pop()
                pivots.pop()
            candidates = []
            recent_high, recent_low = cmp(high[max(0, i - lookback):i + 1]), cmp(low[max(0, i - lookback):i + 1])
            for anchor in pivots:
                hi = lo = anchor
                strength = 0
                for other in pivots:
                    distance = hi - other if cmp(other) <= cmp(hi) else other - lo
                    if cmp(distance) <= cmp(width):
                        if cmp(other) <= cmp(hi):
                            lo = min(lo, other)
                        else:
                            hi = max(hi, other)
                        strength += 20
                touches = ((recent_high <= cmp(hi)) & (recent_high >= cmp(lo))) | (
                    (recent_low <= cmp(hi)) & (recent_low >= cmp(lo)))
                candidates.append([float(strength + touches.sum()), hi, lo])
            levels.fill(0)
            strengths.fill(0)
            slot = 0
            for _ in pivots:
                best_value, best_index = -1, -1
                for candidate_index, (strength, _, _) in enumerate(candidates):
                    if strength > best_value and strength >= minimum_strength * 20:
                        best_value, best_index = strength, candidate_index
                if best_index >= 0:
                    strength, hi, lo = candidates[best_index]
                    levels[slot], strengths[slot] = (hi, lo), strength
                    for candidate in candidates:
                        if (cmp(lo) <= cmp(candidate[1]) <= cmp(hi)
                                or cmp(lo) <= cmp(candidate[2]) <= cmp(hi)):
                            candidate[0] = -1
                    slot += 1
                    if slot >= 10:
                        break
            # Preserve the source's final sorting loop, including its one-sided
            # strength assignment. Descending greedy selection normally makes
            # this branch inactive; silently correcting it changes the source.
            for x in range(9):
                for y in range(x + 1, 10):
                    if strengths[y] > strengths[x]:
                        strengths[y] = strengths[x]
                        levels[[x, y]] = levels[[y, x]]
        visible = levels[:max_channels]
        inside = any(cmp(bottom) <= cmp(close[i]) <= cmp(top) for top, bottom in visible)
        bull = bear = False
        if i and not inside:
            bull = any(cmp(close[i - 1]) <= cmp(top) and cmp(close[i]) > cmp(top) for top, _ in visible)
            bear = any(cmp(close[i - 1]) >= cmp(bottom) and cmp(close[i]) < cmp(bottom) for _, bottom in visible)
        row = {"pivot_high": ph, "pivot_low": pl,
               "pivot_index": i - pivot_period if has_high or has_low else np.nan,
               "pivot_confirmed": bool(has_high or has_low), "channel_width": width,
               "pivot_count": len(pivots), "inside_channel": inside,
               "bull_signal": bull, "bear_signal": bear}
        for slot, ((top, bottom), strength) in enumerate(zip(levels, strengths), 1):
            row[f"channel_{slot}_top"] = top if top != 0 else np.nan
            row[f"channel_{slot}_bottom"] = bottom if bottom != 0 else np.nan
            row[f"channel_{slot}_strength"] = strength
        rows.append(row)
    columns = ["pivot_high", "pivot_low", "pivot_index", "pivot_confirmed", "channel_width",
               "pivot_count", "inside_channel", "bull_signal", "bear_signal"] + [
                   f"channel_{slot}_{field}" for slot in range(1, 11) for field in ("top", "bottom", "strength")]
    result = pd.DataFrame(rows, index=bars.index, columns=columns)
    for column in ("pivot_confirmed", "inside_channel", "bull_signal", "bear_signal"):
        result[column] = result[column].astype(bool)
    return result
