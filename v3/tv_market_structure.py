# SPDX-License-Identifier: MPL-2.0
# Adapted from Market Structure Break & Order Block, © EmreKb.
# https://www.tradingview.com/script/DkE7UniD/ (publication 9)
# https://mozilla.org/MPL/2.0/
# Changes: completed-bar numerical MSB/zigzag port; all graphics and mutable
# box arrays are omitted. Original Pine remains pinned with its attribution.
"""Causal EmreKb market structure state and the source's MSB alert.

This is deliberately the numerical MSB portion, not box/zone parity. Historical
zigzag anchors are output as metadata on their confirmation bar. No output is
written back to a previous pivot bar. TradingView export parity is pending.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from v3._tv_trend_support import comparison_value as cmp, integer, validate_bars


from v3._source_memo import memoized_source


@memoized_source
def market_structure_break(bars, *, zigzag_length=9, fib_factor=0.33):
    """Return source market/zigzag state and bullish/bearish MSB events.

    The input consists of completed, finite repository-format OHLC bars. A
    positive market direction is bullish. Historical pivot indices are zero-
    based positions in this input; the row index is the availability timestamp.
    """
    validate_bars(bars)
    zigzag_length = integer("zigzag_length", zigzag_length)
    fib_factor = float(fib_factor)
    if not np.isfinite(fib_factor) or not 0 <= fib_factor <= 1:
        raise ValueError("fib_factor must be between zero and one")
    high, low = bars.High.to_numpy(float), bars.Low.to_numpy(float)
    highs, lows = [np.nan] * 5, [np.nan] * 5
    high_indices, low_indices = [np.nan] * 5, [np.nan] * 5
    trend = market = 1
    prior_up = prior_down = False
    up_since = down_since = None
    latest_low_equal = latest_high_equal = np.nan
    rows = []
    for i in range(len(bars)):
        start = max(0, i - zigzag_length + 1)
        to_up = bool(cmp(high[i]) >= cmp(high[start:i + 1].max()))
        to_down = bool(cmp(low[i]) <= cmp(low[start:i + 1].min()))
        previous_trend, previous_market = trend, market
        trend = -1 if trend == 1 and to_down else 1 if trend == -1 and to_up else trend
        # ta.barssince(to_up[1]) counts the shifted condition, not the most
        # recent high itself; its minimum dynamic low/high lookback is one.
        up_since = 0 if i and prior_up else None if up_since is None else up_since + 1
        down_since = 0 if i and prior_down else None if down_since is None else down_since + 1
        low_length = up_since if up_since is not None and up_since > 0 else 1
        high_length = down_since if down_since is not None and down_since > 0 else 1
        low_value = low[max(0, i - low_length + 1):i + 1].min()
        high_value = high[max(0, i - high_length + 1):i + 1].max()
        if cmp(low_value) == cmp(low[i]):
            latest_low_equal = i
        if cmp(high_value) == cmp(high[i]):
            latest_high_equal = i
        # Pine ta.change on bar zero is na even if the seeded direction flips.
        trend_changed = bool(i and trend != previous_trend)
        low_confirmed = trend_changed and trend == 1
        high_confirmed = trend_changed and trend == -1
        if low_confirmed:
            lows.append(low_value)
            low_indices.append(latest_low_equal)
        if high_confirmed:
            highs.append(high_value)
            high_indices.append(latest_high_equal)
        h0, h1, l0, l1 = highs[-1], highs[-2], lows[-1], lows[-2]
        # At source lines106–110, market has just been assigned market[1].
        # Its change is therefore zero at both valuewhen calls; no historical
        # event can populate last_l0/last_h0 there. Preserve that statement order
        # instead of "repairing" the guard to evaluate the final market series.
        if market == 1 and cmp(l0) < cmp(l1) and cmp(l0) < cmp(l1 - abs(h0 - l1) * fib_factor):
            market = -1
        elif market == -1 and cmp(h0) > cmp(h1) and cmp(h0) > cmp(h1 + abs(h1 - l0) * fib_factor):
            market = 1
        changed = bool(i and market != previous_market)
        rows.append({"market_direction": market, "zigzag_direction": trend,
                     "high_0": h0, "high_1": h1, "low_0": l0, "low_1": l1,
                     "high_0_index": high_indices[-1], "high_1_index": high_indices[-2],
                     "low_0_index": low_indices[-1], "low_1_index": low_indices[-2],
                     "high_confirmed": high_confirmed, "low_confirmed": low_confirmed,
                     "bull_signal": changed and market == 1,
                     "bear_signal": changed and market == -1})
        prior_up, prior_down = to_up, to_down
    columns = ["market_direction", "zigzag_direction", "high_0", "high_1", "low_0", "low_1",
               "high_0_index", "high_1_index", "low_0_index", "low_1_index",
               "high_confirmed", "low_confirmed", "bull_signal", "bear_signal"]
    result = pd.DataFrame(rows, index=bars.index, columns=columns)
    for column in ("high_confirmed", "low_confirmed", "bull_signal", "bear_signal"):
        result[column] = result[column].astype(bool)
    return result
