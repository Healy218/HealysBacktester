"""Depth-gated fill model for the spx0 pool (no quotes exist in the archive).

Fills are MODELED from printed volume, never assumed (DECISIONS 2026-08-19):
a bar is fillable for ``qty`` contracts only if it printed at least
``depth_mult * qty`` contracts. Buys fill at the bar HIGH, sells at the bar
LOW — the worst print, which is the only conservative bound OHLCV supports.
An entry that cannot fill is a rejected proposal (kept, ``executed=False``).
An exit that cannot fill walks forward to the next bar with depth; if none
exists before the session floor the contract settles to intrinsic.
Returned fill timestamps are the selected minute's END, when its depth and
worst print are known. ``session_floor_ts`` denotes the last minute's START;
settlement is recorded one minute later at the actual session close.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd


class FillFailure(str, Enum):
    NO_ENTRY_BAR = "no_entry_bar"
    NO_DEPTH_ENTRY = "no_depth_entry"
    NO_EXIT_BAR = "no_exit_bar"
    SETTLED_INTRINSIC = "settled_intrinsic"


@dataclass(frozen=True)
class DepthPolicy:
    qty: int = 1                 # contracts per trade
    depth_mult: float = 2.0      # take at most 1/depth_mult of printed volume
    entry_window_min: int = 3    # MINUTES after the signal the entry may fill in
                                 # (option bars are sparse — a bar count would
                                 # let an entry drift hours past its signal)

    @property
    def min_volume(self) -> float:
        return self.depth_mult * self.qty


def fillable(volume, policy: DepthPolicy) -> np.ndarray:
    v = np.asarray(volume, dtype=float)
    return np.isfinite(v) & (v >= policy.min_volume)


def entry_fill(bars: pd.DataFrame, signal_ts: pd.Timestamp, policy: DepthPolicy,
               *, sell: bool = False
               ) -> tuple[pd.Timestamp | None, float | None, float | None, FillFailure | None]:
    """First bar strictly AFTER the signal bar, within ``entry_window_min``
    minutes, with depth. A buy fills at the bar HIGH, a sell (opening a short)
    at the bar LOW — the worst print either way. Returns (fill_ts, price,
    depth=Volume, failure); a sell whose worst print is not positive is
    uninvestable and rejects like missing depth."""
    lim = signal_ts + pd.Timedelta(minutes=policy.entry_window_min)
    after = bars[(bars["timestamp"] > signal_ts) & (bars["timestamp"] <= lim)]
    if after.empty:
        return None, None, None, FillFailure.NO_ENTRY_BAR
    ok = after[fillable(after["Volume"], policy)]
    if ok.empty:
        return None, None, None, FillFailure.NO_DEPTH_ENTRY
    r = ok.iloc[0]
    price = float(r["Low"]) if sell else float(r["High"])
    if sell and price <= 0:
        return None, None, None, FillFailure.NO_DEPTH_ENTRY
    return pd.Timestamp(r["timestamp"]) + pd.Timedelta(minutes=1), price, float(r["Volume"]), None


def exit_fill(bars: pd.DataFrame, exit_signal_ts: pd.Timestamp, policy: DepthPolicy, *,
              session_floor_ts: pd.Timestamp, intrinsic_at_floor: float,
              buyback: bool = False
              ) -> tuple[pd.Timestamp, float, float, FillFailure | None]:
    """First bar at/after the exit signal with depth, no later than the session
    floor. A long's exit sells at the bar LOW; a short's exit buys back at the
    bar HIGH (worst print either way). Past the floor with no depth:
    cash-settles to ``intrinsic_at_floor`` at the floor timestamp — the long's
    payout, or exactly what the short owes."""
    cand = bars[(bars["timestamp"] >= exit_signal_ts) & (bars["timestamp"] <= session_floor_ts)]
    ok = cand[fillable(cand["Volume"], policy)]
    if not ok.empty:
        r = ok.iloc[0]
        price = float(r["High"]) if buyback else float(r["Low"])
        return pd.Timestamp(r["timestamp"]) + pd.Timedelta(minutes=1), price, float(r["Volume"]), None
    return pd.Timestamp(session_floor_ts) + pd.Timedelta(minutes=1), float(max(intrinsic_at_floor, 0.0)), 0.0, \
        FillFailure.SETTLED_INTRINSIC


def spread_entry_fill(short_bars: pd.DataFrame, wing_bars: pd.DataFrame,
                      signal_ts: pd.Timestamp, policy: DepthPolicy
                      ) -> tuple[pd.Timestamp | None, float | None, float | None,
                                 float | None, FillFailure | None]:
    """Package fill for a two-leg spread: the first bar strictly after the
    signal, within the entry window, where BOTH legs have depth. The package
    prints at the net of that bar's CLOSES — a real simultaneous pair — and
    per-leg half-spreads are the COST MODEL's job (worst-printing two legs
    independently in the same minute compounds pathologically and double
    counts what the cost scenarios already charge). Returns
    (fill_ts, short_px, wing_px, depth=min leg volume, failure)."""
    lim = signal_ts + pd.Timedelta(minutes=policy.entry_window_min)
    j = short_bars[["timestamp", "Close", "Volume"]].merge(
        wing_bars[["timestamp", "Close", "Volume"]], on="timestamp",
        suffixes=("_s", "_w"))
    j = j[(j["timestamp"] > signal_ts) & (j["timestamp"] <= lim)]
    if j.empty:
        return None, None, None, None, FillFailure.NO_ENTRY_BAR
    ok = j[fillable(j["Volume_s"], policy) & fillable(j["Volume_w"], policy)]
    if ok.empty:
        return None, None, None, None, FillFailure.NO_DEPTH_ENTRY
    r = ok.iloc[0]
    if float(r["Close_s"]) <= 0 or float(r["Close_w"]) <= 0:
        return None, None, None, None, FillFailure.NO_DEPTH_ENTRY
    return (pd.Timestamp(r["timestamp"]) + pd.Timedelta(minutes=1), float(r["Close_s"]), float(r["Close_w"]),
            float(min(r["Volume_s"], r["Volume_w"])), None)


def spread_exit_fill(short_bars: pd.DataFrame, wing_bars: pd.DataFrame,
                     exit_signal_ts: pd.Timestamp, policy: DepthPolicy, *,
                     session_floor_ts: pd.Timestamp, intrinsic_short: float,
                     intrinsic_wing: float
                     ) -> tuple[pd.Timestamp, float, float, float, FillFailure | None]:
    """First bar at/after the exit signal, no later than the floor, where BOTH
    legs have depth — the package closes at that bar's closes. No such bar:
    the spread cash-settles at the floor to each leg's intrinsic (the payoff
    is then bounded by the width by construction)."""
    j = short_bars[["timestamp", "Close", "Volume"]].merge(
        wing_bars[["timestamp", "Close", "Volume"]], on="timestamp",
        suffixes=("_s", "_w"))
    j = j[(j["timestamp"] >= exit_signal_ts) & (j["timestamp"] <= session_floor_ts)]
    ok = j[fillable(j["Volume_s"], policy) & fillable(j["Volume_w"], policy)]
    if not ok.empty:
        r = ok.iloc[0]
        return (pd.Timestamp(r["timestamp"]) + pd.Timedelta(minutes=1), float(r["Close_s"]),
                float(r["Close_w"]), float(min(r["Volume_s"], r["Volume_w"])), None)
    return (pd.Timestamp(session_floor_ts) + pd.Timedelta(minutes=1), float(max(intrinsic_short, 0.0)),
            float(max(intrinsic_wing, 0.0)), 0.0, FillFailure.SETTLED_INTRINSIC)


def intrinsic(right: str, strike: float, mapped_spot: float) -> float:
    s = float(mapped_spot) - float(strike)
    return max(s, 0.0) if right == "C" else max(-s, 0.0)
