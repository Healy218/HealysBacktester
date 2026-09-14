"""Setup Scanner [GBB] XWuYNmhD: six setups and the source reference book.

Adapted from the pinned open-source publication by GoodBadBitcoin (GBB). No explicit license is
in its source header; TradingView's documented default is MPL2.0:
https://www.tradingview.com/pine-script-docs/writing/publishing/
Changes: causal feature arrays replace drawing objects and the final dashboard.
Reference target/stop counters are not option-ledger results or profitability.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from v3._tv_setup_support import aligned_observations, confirmed_pivots, timed_bars
from v3._tv_trend_support import comparison_value as cmp, integer, pine_ohlc, positive
from v3.pine_compat import atr, ema, rsi, sma
from v3.tv_ict_killzones import SessionWindow, _timezone

SETUPS = ("VWAP", "EMA", "BRT", "SWEEP", "DIV", "ORB")


@dataclass
class SetupTrade:
    sid: int
    direction: int
    entry: float
    stop: float
    targets: tuple[float, float, float]
    open_bar: int
    stage: int = 0
    done: bool = False


@dataclass
class SetupTradeBook:
    """Exact source order, including oneWay's once-per-bar direction snapshot."""
    trades: list[SetupTrade] = field(default_factory=list)
    counters: np.ndarray = field(default_factory=lambda: np.zeros((6, 6), dtype=np.int64))
    last_close_bar: int = -99999

    def step(self, i, high, low, close, volatility, longs, shorts, *, stop_atr=1.2,
             targets=(1., 2., 3.), max_open=1, max_bars=60, reentry=0,
             one_way=True, keep_trades=8):
        entries = np.zeros((6, 2), dtype=bool)
        exits = np.zeros((6, 2), dtype=bool)
        outcomes = []
        ready = np.isfinite(volatility) and cmp(volatility) > 0
        if ready:
            for trade in reversed(self.trades):
                if trade.done:
                    continue
                stop = cmp(low) <= cmp(trade.stop) if trade.direction == 1 else cmp(high) >= cmp(trade.stop)
                hits = [cmp(high) >= cmp(t) if trade.direction == 1 else cmp(low) <= cmp(t) for t in trade.targets]
                outcome = None
                if stop:
                    if trade.stage == 0:
                        self.counters[trade.sid, 4] += 1
                    outcome = "stop"
                else:
                    if hits[0] and trade.stage < 1:
                        trade.stage = 1
                        self.counters[trade.sid, 1] += 1
                    if hits[1] and trade.stage < 2:
                        trade.stage = 2
                        self.counters[trade.sid, 2] += 1
                    if hits[2]:
                        self.counters[trade.sid, 3] += 1
                        outcome = "TP3"
                    elif i - trade.open_bar >= max_bars:
                        if trade.stage == 0:
                            self.counters[trade.sid, 5] += 1
                        outcome = "expired"
                if outcome:
                    trade.done = True
                    exits[trade.sid, 0 if trade.direction == 1 else 1] = True
                    outcomes.append((trade.sid, trade.direction, outcome, trade.stage, bool(stop and any(hits))))
            if outcomes:
                self.last_close_bar = i
            od = next((trade.direction for trade in reversed(self.trades) if not trade.done), 0)
            for sid in range(6):
                long, short = bool(longs[sid]), bool(shorts[sid])
                room = sum(not t.done for t in self.trades) < max_open
                cool = i - self.last_close_bar >= reentry
                direction_ok = not one_way or od == 0 or (long and od == 1) or (short and od == -1)
                direction = 1 if long else -1 if short else 0
                if direction and room and cool and direction_ok:
                    risk = volatility * stop_atr
                    self.trades.append(SetupTrade(sid, direction, close, close - direction * risk,
                                                  tuple(close + direction * risk * r for r in targets), i))
                    entries[sid, 0 if direction == 1 else 1] = True
                    self.counters[sid, 0] += 1
        while len(self.trades) > keep_trades:
            if not self.trades[0].done:
                break
            self.trades.pop(0)
        return entries, exits, tuple(outcomes)


def _vwap_series(bars, available, supplied, reset):
    if supplied is not None and reset is not None:
        raise ValueError("provide either observed VWAP or exchange reset flags")
    if supplied is not None:
        return aligned_observations(supplied, bars.index, available, ["vwap"]).vwap.to_numpy()
    if bars.Volume.isna().all() and reset is None:
        return np.full(len(bars), np.nan)  # Source explicitly disables VWAP without volume.
    if reset is None:
        raise ValueError("VWAP requires exact exchange-session reset flags or observed VWAP values")
    if (not isinstance(reset, pd.Series) or not reset.index.equals(bars.index)
            or not pd.api.types.is_bool_dtype(reset) or reset.isna().any()):
        raise ValueError("VWAP reset flags must be aligned nonmissing booleans")
    values = np.full(len(bars), np.nan)
    total = weighted = 0.
    started = False
    for i, (do_reset, price, volume) in enumerate(zip(reset, (bars.High + bars.Low + bars.Close) / 3, bars.Volume)):
        if do_reset:
            total = weighted = 0.
            started = True
        if started:
            total += volume
            weighted += price * volume
            values[i] = weighted / total if total > 0 else np.nan
    return values


from v3._source_memo import memoized_source


@memoized_source
def setup_scanner(bars: pd.DataFrame, *, enabled=SETUPS, atr_length=14, stop_atr=1.2,
                  targets=(1., 2., 3.), max_open=1, max_bars=60, reentry=0,
                  one_way=True, keep_trades=8, volume_multiplier=1., pivot_length=5,
                  vwap_away=6, ema_window=3, retest_tolerance=.3, retest_window=20,
                  sweep_length=20, divergence_gap=60, opening_session="0930-1600",
                  opening_timezone="America/New_York", opening_minutes=15,
                  vwap_observations=None, vwap_reset=None, strict_session_coverage=True,
                  bar_minutes=15, as_of=None) -> pd.DataFrame:
    """All six identities and source priority; default VWAP needs exchange data.

    Complete bar OHLC is required. Volume may be NaN as in Pine: its participation
    gate passes missing volume, while VWAP becomes unavailable. Session day gaps
    are rejected by default; explicitly disabling strict coverage reproduces the
    source's literal membership transition and exposes session_gap diagnostics.
    """
    available = timed_bars(bars, bar_minutes, as_of)
    bars = bars.copy()
    if "Volume" not in bars:
        bars["Volume"] = np.nan
    if (not pd.api.types.is_numeric_dtype(bars.Volume) or pd.api.types.is_bool_dtype(bars.Volume)
            or np.isinf(bars.Volume.to_numpy(dtype=float)).any() or (bars.Volume < 0).any()):
        raise ValueError("Volume must be nonnegative numeric or NaN")
    enabled = tuple(enabled)
    if len(set(enabled)) != len(enabled) or not set(enabled).issubset(SETUPS):
        raise ValueError("enabled setups must be unique source identities")
    integers = {"atr_length": (atr_length, 2, None), "pivot_length": (pivot_length, 2, None),
                "max_open": (max_open, 1, 5), "max_bars": (max_bars, 5, None),
                "reentry": (reentry, 0, None), "keep_trades": (keep_trades, 1, 40),
                "vwap_away": (vwap_away, 1, None), "ema_window": (ema_window, 1, None),
                "retest_window": (retest_window, 2, None), "sweep_length": (sweep_length, 5, None),
                "divergence_gap": (divergence_gap, 5, None), "opening_minutes": (opening_minutes, 1, None)}
    for name, (value, minimum, maximum) in integers.items():
        integer(name, value, minimum, maximum)
    stop_atr = positive("stop_atr", stop_atr, minimum=.2)
    targets = tuple(positive("target", value, minimum=.2) for value in targets)
    if len(targets) != 3:
        raise ValueError("source has exactly three targets")
    retest_tolerance = positive("retest_tolerance", retest_tolerance, minimum=.05)
    volume_multiplier = float(volume_multiplier)
    if not np.isfinite(volume_multiplier) or volume_multiplier < 0:
        raise ValueError("volume_multiplier must be finite and nonnegative")
    for name, value in (("one_way", one_way), ("strict_session_coverage", strict_session_coverage)):
        if not isinstance(value, bool):
            raise ValueError(f"{name} must be boolean")
    session = SessionWindow.parse(opening_session)
    if session.start % bar_minutes or session.end % bar_minutes:
        raise ValueError("opening session must align to chart bars")
    local = bars.index.tz_convert(_timezone(opening_timezone))
    high, low, close, opn, volume = (bars[c].to_numpy(dtype=float) for c in ("High", "Low", "Close", "Open", "Volume"))
    volatility = atr(pine_ohlc(bars), atr_length).to_numpy()
    e9, e21, e50 = (ema(bars.Close, n).to_numpy() for n in (9, 21, 50))
    rv, vm = rsi(bars.Close, 14).to_numpy(), sma(bars.Volume, 20).to_numpy()
    vw = _vwap_series(bars, available, vwap_observations, vwap_reset) if "VWAP" in enabled else np.full(len(bars), np.nan)
    ph, pl = confirmed_pivots(high, pivot_length, high=True), confirmed_pivots(low, pivot_length, high=False)
    sw_lo = bars.Low.rolling(sweep_length, min_periods=1).min().shift(1).to_numpy()
    sw_hi = bars.High.rolling(sweep_length, min_periods=1).max().shift(1).to_numpy()
    below = above = 0
    touch_up = touch_down = -1
    brt_level = [np.nan, np.nan]
    brt_break = [False, False]
    brt_bar = [-1, -1]
    brt_pending = [np.nan, np.nan]
    last_pivot = [(np.nan, np.nan, -1), (np.nan, np.nan, -1)]
    or_high = or_low = np.nan
    or_done = or_fired = previous_session = False
    previous_instance = None
    or_start = None
    book = SetupTradeBook()
    state = np.zeros(6, dtype=int)
    rows = []
    for i in range(len(bars)):
        ready = np.isfinite(volatility[i]) and cmp(volatility[i]) > 0
        vol_ok = (volume_multiplier <= 0 or np.isnan(volume[i]) or np.isnan(vm[i])
                  or cmp(volume[i]) >= cmp(vm[i] * volume_multiplier))
        bull_bar, bear_bar = cmp(close[i]) > cmp(opn[i]), cmp(close[i]) < cmp(opn[i])
        longs, shorts, forming = np.zeros(6, bool), np.zeros(6, bool), np.zeros(6, bool)
        old_below, old_above = below, above
        if np.isfinite(vw[i]):
            below = below + 1 if cmp(close[i]) < cmp(vw[i]) else 0
            above = above + 1 if cmp(close[i]) > cmp(vw[i]) else 0
        if "VWAP" in enabled and np.isfinite(vw[i]):
            if i:
                longs[0] = ready and cmp(close[i]) > cmp(vw[i]) and cmp(close[i - 1]) <= cmp(vw[i - 1]) and old_below >= vwap_away and vol_ok
                shorts[0] = ready and cmp(close[i]) < cmp(vw[i]) and cmp(close[i - 1]) >= cmp(vw[i - 1]) and old_above >= vwap_away and vol_ok
                forming[0] = not longs[0] and not shorts[0] and (
                    (below >= vwap_away and cmp(close[i]) > cmp(close[i - 1]) and cmp(vw[i] - close[i]) < cmp(volatility[i] * .4)) or
                    (above >= vwap_away and cmp(close[i]) < cmp(close[i - 1]) and cmp(close[i] - vw[i]) < cmp(volatility[i] * .4)))
        if cmp(low[i]) <= cmp(e21[i]): touch_up = i
        if cmp(high[i]) >= cmp(e21[i]): touch_down = i
        trend_up = i >= 3 and cmp(e21[i]) > cmp(e50[i]) > cmp(e50[i - 3])
        trend_down = i >= 3 and cmp(e21[i]) < cmp(e50[i]) < cmp(e50[i - 3])
        if "EMA" in enabled:
            longs[1] = bool(i and ready and trend_up and touch_up >= 0 and i - touch_up <= ema_window and cmp(close[i]) > cmp(e9[i]) and bull_bar and cmp(close[i]) > cmp(high[i - 1]) and vol_ok)
            shorts[1] = bool(i and ready and trend_down and touch_down >= 0 and i - touch_down <= ema_window and cmp(close[i]) < cmp(e9[i]) and bear_bar and cmp(close[i]) < cmp(low[i - 1]) and vol_ok)
            forming[1] = not longs[1] and not shorts[1] and ((trend_up and cmp(low[i]) <= cmp(e21[i]) and cmp(close[i]) < cmp(e9[i])) or (trend_down and cmp(high[i]) >= cmp(e21[i]) and cmp(close[i]) > cmp(e9[i])))
        busy = lambda side: brt_break[side] and i - brt_bar[side] <= retest_window
        for side, pivot in enumerate((ph[i], pl[i])):
            if np.isfinite(pivot):
                if busy(side): brt_pending[side] = pivot
                else: brt_level[side], brt_break[side], brt_pending[side] = pivot, False, np.nan
            broken = cmp(close[i]) > cmp(brt_level[side]) if side == 0 else cmp(close[i]) < cmp(brt_level[side])
            if np.isfinite(brt_level[side]) and not brt_break[side] and broken:
                brt_break[side], brt_bar[side] = True, i
        live = ["BRT" in enabled and busy(side) and i > brt_bar[side] for side in (0, 1)]
        longs[2] = live[0] and ready and cmp(low[i]) <= cmp(brt_level[0] + volatility[i] * retest_tolerance) and cmp(close[i]) > cmp(brt_level[0]) and bull_bar
        shorts[2] = live[1] and ready and cmp(high[i]) >= cmp(brt_level[1] - volatility[i] * retest_tolerance) and cmp(close[i]) < cmp(brt_level[1]) and bear_bar
        for side, signal in enumerate((longs[2], shorts[2])):
            if signal: brt_break[side] = False
            if not busy(side) and np.isfinite(brt_pending[side]):
                brt_level[side], brt_break[side], brt_pending[side] = brt_pending[side], False, np.nan
        forming[2] = any(live) and not longs[2] and not shorts[2]
        if "SWEEP" in enabled:
            longs[3] = ready and cmp(low[i]) < cmp(sw_lo[i]) < cmp(close[i]) and bull_bar and cmp(close[i] - low[i]) > cmp(high[i] - close[i]) and vol_ok
            shorts[3] = ready and cmp(high[i]) > cmp(sw_hi[i]) > cmp(close[i]) and bear_bar and cmp(high[i] - close[i]) > cmp(close[i] - low[i]) and vol_ok
            forming[3] = not longs[3] and not shorts[3] and (cmp(low[i]) < cmp(sw_lo[i]) or cmp(high[i]) > cmp(sw_hi[i]))
        for side, pivot in enumerate((pl[i], ph[i])):
            if np.isfinite(pivot):
                old_p, old_r, old_bar = last_pivot[side]
                current_r = rv[i - pivot_length]
                diverges = cmp(pivot) < cmp(old_p) and cmp(current_r) > cmp(old_r) if side == 0 else cmp(pivot) > cmp(old_p) and cmp(current_r) < cmp(old_r)
                signal = "DIV" in enabled and ready and np.isfinite(old_p) and i - old_bar <= divergence_gap and diverges
                if side == 0: longs[4] = signal
                else: shorts[4] = signal
                last_pivot[side] = (pivot, current_r, i)
        member, instance = session.locate(local[i])
        gap = member and previous_session and instance != previous_instance
        if gap and strict_session_coverage and "ORB" in enabled:
            raise ValueError("missing outside-session bars conceal opening-range day reset")
        new_session = member and not previous_session
        if new_session:
            or_high, or_low, or_done, or_fired, or_start = high[i], low[i], False, False, bars.index[i]
        elif member and not or_done:
            if or_start is not None and bars.index[i] - or_start >= pd.Timedelta(minutes=opening_minutes):
                or_done = True
            else:
                or_high, or_low = max(or_high, high[i]), min(or_low, low[i])
        longs[5] = "ORB" in enabled and ready and member and or_done and not or_fired and cmp(close[i]) > cmp(or_high)
        shorts[5] = "ORB" in enabled and ready and member and or_done and not or_fired and cmp(close[i]) < cmp(or_low)
        if longs[5] or shorts[5]: or_fired = True
        forming[5] = "ORB" in enabled and member and or_done and not or_fired
        previous_session, previous_instance = member, instance
        entries, exits, outcomes = book.step(i, high[i], low[i], close[i], volatility[i], longs, shorts,
                                            stop_atr=stop_atr, targets=targets, max_open=max_open,
                                            max_bars=max_bars, reentry=reentry, one_way=one_way, keep_trades=keep_trades)
        if ready:
            state = np.array([0 if name not in enabled else 3 if longs[j] else 4 if shorts[j] else 2 if forming[j] else 1 for j, name in enumerate(SETUPS)])
        row = {"available_at": available[i], "atr": volatility[i], "ema9": e9[i], "ema21": e21[i], "ema50": e50[i],
               "rsi": rv[i], "volume_sma": vm[i], "volume_ok": bool(vol_ok), "vwap": vw[i],
               "any_long": bool(longs.any()), "any_short": bool(shorts.any()),
               "took_long": bool(entries[:, 0].any()), "took_short": bool(entries[:, 1].any()),
               "long_exit": bool(exits[:, 0].any()), "short_exit": bool(exits[:, 1].any()),
               "open_count": sum(not t.done for t in book.trades), "last_close_bar": book.last_close_bar,
               "or_high": or_high, "or_low": or_low, "or_done": or_done, "or_fired": or_fired,
               "session_gap": gap, "or_in_session": member, "outcomes": outcomes,
               "brt_high": brt_level[0], "brt_low": brt_level[1], "brt_high_pending": brt_pending[0], "brt_low_pending": brt_pending[1]}
        for j, name in enumerate(SETUPS):
            row.update({f"{name}_raw_long": bool(longs[j]), f"{name}_raw_short": bool(shorts[j]),
                        f"{name}_forming": bool(forming[j]), f"{name}_state": int(state[j]),
                        f"{name}_long_entry": bool(entries[j, 0]), f"{name}_short_entry": bool(entries[j, 1]),
                        f"{name}_long_exit": bool(exits[j, 0]), f"{name}_short_exit": bool(exits[j, 1])})
            row.update({f"{name}_{key}": int(book.counters[j, k]) for k, key in enumerate(("fired", "tp1", "tp2", "tp3", "stop_before_tp1", "expiry_before_tp1"))})
        rows.append(row)
    result = pd.DataFrame(rows, index=bars.index)
    result.attrs.update({"source": "XWuYNmhD/v2", "setup_priority": SETUPS,
                         "admission_status": "pending exported Pine fixtures", "index_kind": "bar_open"})
    return result
