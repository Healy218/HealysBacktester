"""AMD Po3 with Live Edge Stats [WillyAlgoTrader], pinned hkKioUnL.

Source header names WillyAlgoTrader and version2.2.0 but no explicit license.
TradingView's documented open-source default is MPL2.0:
https://www.tradingview.com/pine-script-docs/writing/publishing/
Changes: completed-bar events and causal statistics replace chart objects.
The author's underlying reference R model is not the options execution ledger.
"""
from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from v3._tv_setup_support import aligned_observations, confirmed_pivots, percentile_rank_previous, timed_bars
from v3._tv_trend_support import comparison_value as cmp, integer, pine_ohlc, positive
from v3.pine_compat import atr
from v3.tv_ict_killzones import SessionWindow, _timezone


@dataclass(frozen=True)
class AmdConfig:
    min_range_bars: int = 12
    max_range_bars: int = 96
    compression_percentile: int = 25
    stat_window: int = 200
    range_tolerance: float = .10
    min_range_width_pct: float = .15
    boundary_mode: str = "pivot"
    trim_tail_pct: int = 15
    sweep_return_bars: int = 8
    require_liquidity: bool = False
    sweep_depth_percentile: int = 100
    allow_rearm: bool = True
    distribution_timeout: int = 64
    stop_buffer_atr: float = .4
    fib_extension: float = 1.5
    use_killzones: bool = False
    use_htf_bias: bool = False
    alerts_on: bool = True
    minimum_tick: float = .01
    min_sample: int = 10

    def __post_init__(self):
        for name, low, high in (("min_range_bars", 8, 40), ("max_range_bars", 48, 192),
                                ("compression_percentile", 10, 50), ("stat_window", 100, 500),
                                ("trim_tail_pct", 0, 40), ("sweep_return_bars", 2, 16),
                                ("sweep_depth_percentile", 80, 100), ("distribution_timeout", 24, 128),
                                ("min_sample", 1, 50)):
            integer(name, getattr(self, name), low, high)
        for name, low, high in (("range_tolerance", 0, .30), ("min_range_width_pct", .05, 1),
                                ("stop_buffer_atr", 0, 1.5), ("fib_extension", 1, 3)):
            value = getattr(self, name)
            if isinstance(value, bool) or not np.isfinite(value) or not low <= value <= high:
                raise ValueError(f"{name} outside source input limits")
        if isinstance(self.minimum_tick, bool):
            raise ValueError("minimum_tick must be positive numeric")
        object.__setattr__(self, "minimum_tick", positive("minimum_tick", self.minimum_tick))
        if self.boundary_mode not in ("pivot", "absolute"):
            raise ValueError("unknown source boundary mode")
        for name in ("require_liquidity", "allow_rearm", "use_killzones", "use_htf_bias", "alerts_on"):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be boolean")


@dataclass
class AmdState:
    phase: str = "idle"
    cycle_id: int = 0
    last_end: int = -100
    range_high: float = np.nan
    range_low: float = np.nan
    range_mid: float = np.nan
    range_width: float = np.nan
    range_start: int = -1
    expiry_anchor: int = -1
    range_age: int = 0
    atr_anchor: float = np.nan
    sweep_side: int = 0
    first_sweep_side: int = 0
    sweep_extreme: float = np.nan
    sweep_bar: int = -1
    rearm_used: bool = False
    direction: int = 0
    entry: float = np.nan
    stop: float = np.nan
    target: float = np.nan
    risk: float = np.nan
    dist_start: int = -1
    target_count: int = 0
    stop_count: int = 0
    timeout_count: int = 0
    ambiguous_count: int = 0
    failed_count: int = 0
    breakout_count: int = 0
    sum_r: float = 0.
    double_count: int = 0
    double_sum_r: float = 0.
    pivots_high: deque = field(default_factory=lambda: deque(maxlen=60))
    pivots_low: deque = field(default_factory=lambda: deque(maxlen=60))
    cycles: deque = field(default_factory=deque)
    form: deque = field(default_factory=lambda: deque(maxlen=10))
    alerted_high: bool = False
    alerted_low: bool = False

    def snapshot(self):
        """Detached Python state for reference restart checks; not an admission token."""
        return deepcopy(self)

    def _idle(self, i):
        self.phase, self.last_end = "idle", i

    def _range(self):
        self.range_width = self.range_high - self.range_low
        self.range_mid = (self.range_high + self.range_low) / 2

    def _liquidity(self, side, i):
        pivots = self.pivots_high if side == 1 else self.pivots_low
        boundary = self.range_high if side == 1 else self.range_low
        return sum(bar >= i - 96 and cmp(abs(value - boundary)) <= cmp(.1 * self.range_width)
                   for bar, value in pivots) >= 2

    def step(self, i, stamp, high, low, close, *, config=None, highs=None, lows=None,
             atrs=None, width_high=np.nan, width_low=np.nan, percent_rank=np.nan,
             depth_threshold=np.nan, pivot_high=np.nan, pivot_low=np.nan,
             in_killzone=True, htf_close=np.nan, htf_ema=np.nan):
        c = config or AmdConfig()
        if np.isfinite(pivot_high): self.pivots_high.append((i - 3, pivot_high))
        if np.isfinite(pivot_low): self.pivots_low.append((i - 3, pivot_low))
        tol = c.range_tolerance * self.range_width if np.isfinite(self.range_width) else 0.
        inside = cmp(self.range_low) <= cmp(close) <= cmp(self.range_high)
        breach_high = cmp(high) > cmp(self.range_high + tol)
        breach_low = cmp(low) < cmp(self.range_low - tol)
        events = {"range_created": False, "range_expired": False, "news_reset": False,
                  "immature_reset": False, "filtered_reset": False, "sweep_high": False,
                  "sweep_low": False, "alert_sweep_high": False, "alert_sweep_low": False,
                  "rearmed": False, "failed_manipulation": False, "breakout": False,
                  "long_entry": False, "short_entry": False, "long_exit": False,
                  "short_exit": False, "alert_distribution": False, "alert_outcome": False,
                  "outcome": "", "outcome_r": np.nan, "ambiguous_outcome": False}
        if self.phase == "idle":
            width = width_high - width_low
            if (i > c.stat_window and cmp(percent_rank) <= cmp(c.compression_percentile)
                    and cmp(width) >= cmp(c.min_range_width_pct / 100 * close) and i - self.last_end >= 10):
                if highs is None or lows is None or atrs is None:
                    raise ValueError("range detection needs causal OHLC/ATR history")
                win_last, top, bottom = 19, width_high, width_low
                if c.trim_tail_pct > 0:
                    while win_last > c.min_range_bars:
                        hi2, lo2 = np.max(highs[i - win_last + 1:i + 1]), np.min(lows[i - win_last + 1:i + 1])
                        if cmp((top - bottom) - (hi2 - lo2)) > cmp(c.trim_tail_pct / 100 * (top - bottom)):
                            win_last, top, bottom = win_last - 1, hi2, lo2
                        else:
                            break
                start = i - win_last
                if c.boundary_mode == "pivot":
                    candidates_high = [value for bar, value in self.pivots_high if bar >= start]
                    candidates_low = [value for bar, value in self.pivots_low if bar >= start]
                    if candidates_high: top = max(candidates_high)
                    if candidates_low: bottom = min(candidates_low)
                if cmp(top - bottom) >= cmp(c.min_range_width_pct / 100 * close):
                    self.range_start = self.expiry_anchor = start
                    self.range_high, self.range_low = top, bottom
                    self._range()
                    self.range_age = win_last
                    self.atr_anchor = atrs[i - win_last - 1]
                    self.rearm_used, self.first_sweep_side = False, 0
                    self.cycle_id += 1
                    self.alerted_high = self.alerted_low = False
                    self.phase = "accum"
                    events["range_created"] = True
        elif self.phase == "accum":
            self.range_age = i - self.range_start
            if i - self.expiry_anchor > c.max_range_bars:
                events["range_expired"] = True
                self._idle(i)
            elif breach_high and breach_low:
                events["news_reset"] = True
                self._idle(i)
            elif breach_high or breach_low:
                side = 1 if breach_high else -1
                if self.range_age < c.min_range_bars:
                    events["immature_reset"] = True
                    self._idle(i)
                else:
                    same_side = self.rearm_used and side == self.first_sweep_side
                    kz_ok = not c.use_killzones or in_killzone
                    excursion = high - self.range_high if side == 1 else self.range_low - low
                    depth_ok = c.sweep_depth_percentile >= 100 or cmp(excursion) <= cmp(depth_threshold)
                    liquid = not c.require_liquidity or self._liquidity(side, i)
                    if kz_ok and depth_ok and liquid and not same_side:
                        self.sweep_side, self.sweep_bar = side, i
                        self.sweep_extreme = high if side == 1 else low
                        if self.first_sweep_side == 0: self.first_sweep_side = side
                        key = "high" if side == 1 else "low"
                        events[f"sweep_{key}"] = True
                        already_alerted = self.alerted_high if side == 1 else self.alerted_low
                        if c.alerts_on and not already_alerted:
                            events[f"alert_sweep_{key}"] = True
                            if side == 1: self.alerted_high = True
                            else: self.alerted_low = True
                        self.phase = "manip" if inside else "sweepPending"
                    elif not inside:
                        events["filtered_reset"] = True
                        self._idle(i)
            else:
                if c.boundary_mode == "absolute":
                    self.range_high = min(max(self.range_high, high), self.range_high + tol)
                    self.range_low = max(min(self.range_low, low), self.range_low - tol)
                    self._range()
                else:
                    if i - 3 >= self.range_start and cmp(self.range_high) < cmp(pivot_high) <= cmp(self.range_high + tol):
                        self.range_high = pivot_high
                        self._range()
                    if i - 3 >= self.range_start and cmp(self.range_low) > cmp(pivot_low) >= cmp(self.range_low - tol):
                        self.range_low = pivot_low
                        self._range()
        elif self.phase == "sweepPending":
            self.sweep_extreme = max(self.sweep_extreme, high) if self.sweep_side == 1 else min(self.sweep_extreme, low)
            if i - self.sweep_bar > c.sweep_return_bars:
                self.breakout_count += 1
                events["breakout"] = True
                self._idle(i)
            elif inside:
                self.phase = "manip"
        elif self.phase == "dist":
            if i - self.dist_start >= 1:
                hit_target = cmp(high) >= cmp(self.target) if self.direction == 1 else cmp(low) <= cmp(self.target)
                hit_stop = cmp(low) <= cmp(self.stop) if self.direction == 1 else cmp(high) >= cmp(self.stop)
                timeout = i - self.dist_start > c.distribution_timeout
                if hit_target or hit_stop or timeout:
                    if hit_target and hit_stop:
                        self.ambiguous_count += 1
                        self.stop_count += 1
                        outcome, rr, code = "ambiguous", -1., 0
                    elif hit_target:
                        self.target_count += 1
                        outcome, rr, code = "target", abs(self.target - self.entry) / self.risk, 1
                    elif hit_stop:
                        self.stop_count += 1
                        outcome, rr, code = "stop", -1., 0
                    else:
                        self.timeout_count += 1
                        outcome, rr, code = "timeout", self.direction * (close - self.entry) / self.risk, 2
                    self.sum_r += rr
                    if self.rearm_used:
                        self.double_count += 1
                        self.double_sum_r += rr
                    self.cycles.append((stamp, code, rr))
                    while self.cycles and self.cycles[0][0] < stamp - pd.Timedelta(days=31): self.cycles.popleft()
                    self.form.append(code)
                    events.update({"outcome": outcome, "outcome_r": rr, "ambiguous_outcome": outcome == "ambiguous",
                                   "long_exit": self.direction == 1, "short_exit": self.direction == -1,
                                   "alert_outcome": c.alerts_on})
                    self._idle(i)
        if self.phase == "manip":
            direction = 1 if self.sweep_side == -1 else -1
            htf_ok = not c.use_htf_bias or (np.isfinite(htf_close) and np.isfinite(htf_ema) and (
                cmp(htf_close) > cmp(htf_ema) if direction == 1 else cmp(htf_close) < cmp(htf_ema)))
            if htf_ok:
                self.direction, self.entry = direction, close
                leg = self.range_high - self.sweep_extreme if direction == 1 else self.sweep_extreme - self.range_low
                self.target = self.range_high + (c.fib_extension - 1) * leg if direction == 1 else self.range_low - (c.fib_extension - 1) * leg
                self.stop = self.sweep_extreme - c.stop_buffer_atr * self.atr_anchor if direction == 1 else self.sweep_extreme + c.stop_buffer_atr * self.atr_anchor
                self.risk = max(abs(self.entry - self.stop), c.minimum_tick)
                self.dist_start, self.phase = i, "dist"
                events.update({"long_entry": direction == 1, "short_entry": direction == -1,
                               "alert_distribution": c.alerts_on})
            elif c.allow_rearm and not self.rearm_used:
                self.rearm_used, self.expiry_anchor, self.phase = True, i, "accum"
                events["rearmed"] = True
            else:
                self.failed_count += 1
                events["failed_manipulation"] = True
                self._idle(i)
        observations = {"phase": self.phase, "cycle_id": self.cycle_id, "range_high": self.range_high,
                        "range_low": self.range_low, "range_width": self.range_width, "range_mid": self.range_mid,
                        "range_start_bar": self.range_start, "range_age": self.range_age, "expiry_anchor": self.expiry_anchor,
                        "atr_anchor": self.atr_anchor, "sweep_side": self.sweep_side, "sweep_extreme": self.sweep_extreme,
                        "sweep_bar": self.sweep_bar, "first_sweep_side": self.first_sweep_side,
                        "rearm_used": self.rearm_used, "direction": self.direction, "entry": self.entry,
                        "stop": self.stop, "target": self.target, "risk": self.risk, "distribution_start_bar": self.dist_start,
                        "target_count": self.target_count, "stop_count": self.stop_count, "timeout_count": self.timeout_count,
                        "ambiguous_count": self.ambiguous_count, "failed_count": self.failed_count,
                        "breakout_count": self.breakout_count, "sum_r": self.sum_r,
                        "double_sweep_count": self.double_count, "double_sweep_sum_r": self.double_sum_r,
                        "form_codes": tuple(self.form)}
        for tag, days in (("all", None), ("24h", 1), ("30d", 30)):
            if days is None:
                targets, stops, timeouts, sum_r = self.target_count, self.stop_count, self.timeout_count, self.sum_r
            else:
                cycles = [cycle for cycle in self.cycles if cycle[0] >= stamp - pd.Timedelta(days=days)]
                targets, stops, timeouts = (sum(row[1] == code for row in cycles) for code in (1, 0, 2))
                sum_r = sum((row[2] for row in cycles), 0.)
            count = targets + stops + timeouts
            observations.update({f"{tag}_closed": count, f"{tag}_targets": targets, f"{tag}_stops": stops,
                                 f"{tag}_timeouts": timeouts, f"{tag}_sum_r": sum_r,
                                 f"{tag}_target_rate": 100 * targets / count if count >= c.min_sample else np.nan,
                                 f"{tag}_average_r": sum_r / count if count >= c.min_sample else np.nan})
        observations.update(events)
        return observations


def amd_po3(bars, *, config=None, bar_minutes=15, as_of=None,
            killzone_timezone="UTC", london_session="0700-1000", new_york_session="1330-1600",
            htf_observations=None, htf_minutes=240):
    """Causal full finite-bar state core; optional HTF inputs must predate bar open.

    HTF observations must be the exact previous completed HTF close and EMA50
    mapped as Pine [1]+lookahead_on, with aligned close/ema50/available_at columns.
    No external series is inferred from the eventual complete chart.
    """
    c = config or AmdConfig()
    if not isinstance(c, AmdConfig): raise ValueError("config must be AmdConfig")
    available = timed_bars(bars, bar_minutes, as_of)
    high, low, close = (bars[column].to_numpy(dtype=float) for column in ("High", "Low", "Close"))
    previous = bars.Close.shift(1)
    tr = pd.concat([bars.High - bars.Low, (bars.High - previous).abs(), (bars.Low - previous).abs()], axis=1).max(axis=1)
    a = atr(pine_ohlc(bars), 14).to_numpy()
    a = np.maximum(np.where(np.isnan(a), tr.to_numpy(), a), c.minimum_tick)
    wh, wl = bars.High.rolling(20, min_periods=1).max().to_numpy(), bars.Low.rolling(20, min_periods=1).min().to_numpy()
    ranks = percentile_rank_previous(wh - wl, c.stat_window)
    tr_variable = tr.copy()
    if len(tr_variable): tr_variable.iloc[0] = np.nan
    rank_index = int(np.ceil(c.stat_window * c.sweep_depth_percentile / 100)) - 1
    depth = tr_variable.rolling(c.stat_window, min_periods=c.stat_window).apply(lambda x: np.sort(x)[rank_index], raw=True).to_numpy()
    ph, pl = confirmed_pivots(high, 3, high=True), confirmed_pivots(low, 3, high=False)
    london, new_york = SessionWindow.parse(london_session), SessionWindow.parse(new_york_session)
    if any(window.start % bar_minutes or window.end % bar_minutes for window in (london, new_york)):
        raise ValueError("killzone boundaries must align to chart bars")
    local = bars.index.tz_convert(_timezone(killzone_timezone))
    kz = [london.locate(stamp)[0] or new_york.locate(stamp)[0] for stamp in local]
    if c.use_htf_bias:
        if integer("htf_minutes", htf_minutes) < bar_minutes:
            raise ValueError("HTF bias cannot use a lower timeframe")
        htf = aligned_observations(htf_observations, bars.index, bars.index, ["close", "ema50"])
        htf_close, htf_ema = htf.close.to_numpy(), htf.ema50.to_numpy()
    else:
        htf_close = htf_ema = np.full(len(bars), np.nan)
    state = AmdState()
    rows = []
    for i, stamp in enumerate(bars.index):
        row = state.step(i, stamp, high[i], low[i], close[i], config=c, highs=high, lows=low, atrs=a,
                         width_high=wh[i], width_low=wl[i], percent_rank=ranks[i], depth_threshold=depth[i],
                         pivot_high=ph[i], pivot_low=pl[i], in_killzone=kz[i], htf_close=htf_close[i], htf_ema=htf_ema[i])
        row.update({"available_at": available[i], "atr": a[i], "compression_rank": ranks[i],
                    "channel_high": wh[i], "channel_low": wl[i], "depth_threshold": depth[i],
                    "pivot_high": ph[i], "pivot_low": pl[i], "in_killzone": kz[i]})
        rows.append(row)
    result = pd.DataFrame(rows, index=bars.index)
    result.attrs.update({"source": "hkKioUnL/v1", "scope": "reference state, alerts, causal statistics",
                         "admission_status": "pending exported Pine fixtures", "index_kind": "bar_open"})
    return result
