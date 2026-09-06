"""Causal numeric subset of ICT Killzones & Pivots [TFO], publication 19.

Derived from nW5oGfdO by tradeforopp; Mozilla Public License 2.0:
https://mozilla.org/MPL/2.0/
Source: indicators/tradingview_sources/nW5oGfdO.pine. Changes: Python feature
outputs, explicit exchange-period flags, completed-bar availability, and strict
input coverage checks. Drawings and trading rules are not synthesized.

Session membership uses bar OPEN times in the chosen timezone, as Pine time()
does. All returned observations are available only at ``available_at``. Session
extrema remain provisional until an outside bar is observed; confirmed values
are never written back onto earlier rows. A break event is not a trade signal.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import timedelta, timezone as fixed_timezone
import re
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from v3._tv_trend_support import comparison_value as cmp, integer, positive, validate_bars


DEFAULT_SESSIONS = {
    "ASIA": "2000-0000", "LNDN": "0200-0500",
    "NYAM": "0930-1100", "NYPM": "1330-1600",
}

_SESSION_BOOLS = ("in_session", "session_start", "session_end", "partial_session", "break_high",
                  "break_low", "alert_high", "alert_low", "midpoint_touch", "pivot_high_valid",
                  "pivot_low_valid")
_SESSION_INTS = ("completed_ranges", "high_break_count", "low_break_count", "pivot_total",
                 "pivot_high_hits", "pivot_low_hits")
_SESSION_TIMES = ("observed_start", "confirmed_at", "pivot_high_at", "pivot_low_at")
_SESSION_FLOATS = ("current_high", "current_low", "session_open", "current_range", "confirmed_high",
                   "confirmed_low", "range_value", "sd_value", "pivot_high_hit_pct",
                   "pivot_low_hit_pct", "pivot_high", "pivot_low", "pivot_midpoint")


def _timezone(name: str):
    """Pine GMT signs are ordinary UTC offsets, unlike Etc/GMT zone names."""
    match = re.fullmatch(r"GMT([+-])(\d{1,2})", name)
    if match:
        offset = int(match[2]) * (1 if match[1] == "+" else -1)
        if not -12 <= offset <= 14:
            raise ValueError("GMT offset must be in [-12, 14]")
        return fixed_timezone(timedelta(hours=offset))
    if name in ("GMT", "UTC"):
        return fixed_timezone.utc
    return ZoneInfo(name)


def _minute(value: str, *, allow_2400: bool = False) -> int:
    if allow_2400 and value == "2400":
        return 1440
    if not re.fullmatch(r"\d{4}", value):
        raise ValueError("times must use HHMM")
    hour, minute = int(value[:2]), int(value[2:])
    if hour > 23 or minute > 59:
        raise ValueError(f"invalid HHMM time: {value}")
    return hour * 60 + minute


@dataclass(frozen=True)
class SessionWindow:
    """One Pine session interval; overnight day masks name the END day.

    Disjoint and full-day sessions are deliberately unsupported: the source's
    false-to-true session transition does not provide daily resets for 24x7.
    """

    start: int
    end: int
    days: frozenset[int]

    @classmethod
    def parse(cls, value: str) -> "SessionWindow":
        match = re.fullmatch(r"(\d{4})-(\d{4})(?::([1-7]+))?", value)
        if not match:
            raise ValueError("session must be one HHMM-HHMM[:1234567] interval")
        start, end = _minute(match[1]), _minute(match[2], allow_2400=True) % 1440
        if start == end:
            raise ValueError("full-day sessions need an explicit source reset policy")
        return cls(start, end, frozenset(map(int, match[3] or "1234567")))

    def locate(self, local: pd.Timestamp) -> tuple[bool, str | None]:
        minute = local.hour * 60 + local.minute
        overnight = self.end < self.start
        inside = (minute >= self.start or minute < self.end) if overnight else (
            self.start <= minute < self.end)
        if not inside:
            return False, None
        start_date = local.date() - timedelta(days=int(overnight and minute < self.end))
        end_date = start_date + timedelta(days=int(overnight))
        pine_day = (end_date.weekday() + 1) % 7 + 1
        return (True, start_date.isoformat()) if pine_day in self.days else (False, None)


@dataclass
class _Pivot:
    high: float
    low: float
    high_at: pd.Timestamp
    low_at: pd.Timestamp
    high_valid: bool = True
    low_valid: bool = True
    midpoint_valid: bool = True
    stopped: bool = False


@dataclass
class _Level:
    high: float = np.nan
    low: float = np.nan
    high_valid: bool = False
    low_valid: bool = False
    active: bool = False
    total: int = 0
    high_hits: int = 0
    low_hits: int = 0


@dataclass
class _SessionState:
    previous_inside: bool = False
    previous_instance: str | None = None
    observed_start: pd.Timestamp = pd.NaT
    partial_session: bool = False
    high: float = np.nan
    low: float = np.nan
    session_open: float = np.nan
    confirmed_high: float = np.nan
    confirmed_low: float = np.nan
    confirmed_at: pd.Timestamp = pd.NaT
    total: int = 0
    high_hits: int = 0
    low_hits: int = 0
    pivots: list[_Pivot] = field(default_factory=list)
    ranges: deque = field(default_factory=deque)
    sd_current: list[float] = field(default_factory=list)
    sd_sessions: deque = field(default_factory=deque)
    sd_value: float = np.nan
    levels: list[_Level] = field(default_factory=list)


def _session_step(state, window, local, stamp, available, prices, cutoff, *,
                  max_days, data_lookback, range_measure, show_pivots,
                  show_midpoints, use_alerts, extend_which, multipliers, minimum_tick):
    opn, high, low, close = prices
    inside, instance = window.locate(local)
    if inside and state.previous_inside and instance != state.previous_instance:
        raise ValueError("missing outside-session bars across a day boundary; "
                         "Pine would merge distinct session instances")
    started, ended = inside and not state.previous_inside, state.previous_inside and not inside
    if started:
        state.observed_start = stamp
        state.partial_session = local.hour * 60 + local.minute != window.start
        state.high, state.low, state.session_open = high, low, opn
        if state.sd_current:
            state.sd_sessions.append(state.sd_current)
            state.sd_current = []
            while len(state.sd_sessions) > data_lookback:
                state.sd_sessions.popleft()
        samples = [value for session in state.sd_sessions for value in session]
        state.sd_value = float(np.std(samples, ddof=0)) if len(samples) > 1 else np.nan
        if show_pivots:
            state.pivots.insert(0, _Pivot(high, low, stamp, stamp))
            del state.pivots[max_days:]
            state.total += 1  # Source increments at START, despite tooltip saying end.
    if inside:
        state.high, state.low = max(state.high, high), min(state.low, low)
        if show_pivots:
            current = state.pivots[0]
            if cmp(high) > cmp(current.high):
                current.high, current.high_at = high, stamp
            if cmp(low) < cmp(current.low):
                current.low, current.low_at = low, stamp
    if ended:
        state.ranges.appendleft(state.high - state.low)
        while len(state.ranges) > data_lookback:
            state.ranges.pop()
        state.confirmed_high, state.confirmed_low = state.high, state.low
        state.confirmed_at = available

    high_breaks = low_breaks = 0
    latest_high_break = latest_low_break = midpoint_touch = False
    tracked = state.pivots if extend_which == "All" else state.pivots[:1]
    for i, pivot in enumerate(tracked):
        if cmp(high) > cmp(pivot.high) and pivot.high_valid:
            pivot.high_valid = False
            state.high_hits += 1
            high_breaks += 1
            latest_high_break |= i == 0
        elif cutoff:
            pivot.high_valid = False
        if cmp(low) < cmp(pivot.low) and pivot.low_valid:
            pivot.low_valid = False
            state.low_hits += 1
            low_breaks += 1
            latest_low_break |= i == 0
        elif cutoff:
            pivot.low_valid = False
        mid = (pivot.high + pivot.low) / 2
        if show_midpoints and not inside and not pivot.stopped and pivot.midpoint_valid:
            if cmp(low) <= cmp(mid) <= cmp(high):
                pivot.midpoint_valid = False
                midpoint_touch |= i == 0
        if cutoff:
            pivot.stopped = True

    if inside:
        state.sd_current.append(close - state.session_open)
    range_value = (float(np.mean(state.ranges)) if state.ranges else np.nan) if (
        range_measure == "Average") else (
        (float(np.median(state.ranges)) if state.ranges else np.nan) if (
            range_measure == "Median") else state.sd_value)
    result = {
        "in_session": inside, "session_start": started, "session_end": ended,
        "observed_start": state.observed_start, "partial_session": state.partial_session,
        "current_high": state.high, "current_low": state.low,
        "session_open": state.session_open, "current_range": state.high - state.low,
        "confirmed_high": state.confirmed_high, "confirmed_low": state.confirmed_low,
        "confirmed_at": state.confirmed_at, "range_value": range_value,
        "completed_ranges": len(state.ranges), "sd_value": state.sd_value,
        "break_high": latest_high_break, "break_low": latest_low_break,
        "alert_high": latest_high_break and use_alerts,
        "alert_low": latest_low_break and use_alerts,
        "high_break_count": high_breaks, "low_break_count": low_breaks,
        "midpoint_touch": midpoint_touch, "pivot_total": state.total,
        "pivot_high_hits": state.high_hits, "pivot_low_hits": state.low_hits,
        "pivot_high_hit_pct": 100 * state.high_hits / state.total if state.total else np.nan,
        "pivot_low_hit_pct": 100 * state.low_hits / state.total if state.total else np.nan,
    }
    pivot = state.pivots[0] if state.pivots else None
    result.update({
        "pivot_high": pivot.high if pivot else np.nan,
        "pivot_low": pivot.low if pivot else np.nan,
        "pivot_midpoint": (pivot.high + pivot.low) / 2 if pivot and show_midpoints else np.nan,
        "pivot_high_at": pivot.high_at if pivot else pd.NaT,
        "pivot_low_at": pivot.low_at if pivot else pd.NaT,
        "pivot_high_valid": pivot.high_valid if pivot else False,
        "pivot_low_valid": pivot.low_valid if pivot else False,
    })
    for j, (multiplier, level) in enumerate(zip(multipliers, state.levels)):
        high_hit = low_hit = False
        if started:
            level.active = np.isfinite(range_value) and cmp(range_value) > 0
            if level.active:
                level.high = np.floor((opn + multiplier * range_value) / minimum_tick + .5) * minimum_tick
                level.low = np.floor((opn - multiplier * range_value) / minimum_tick + .5) * minimum_tick
                level.high_valid = level.low_valid = True
                level.total += 1
        if inside and level.active:
            if level.high_valid and cmp(high) >= cmp(level.high):
                level.high_valid, high_hit = False, True
                level.high_hits += 1
            if level.low_valid and cmp(low) <= cmp(level.low):
                level.low_valid, low_hit = False, True
                level.low_hits += 1
            if cutoff:
                level.active = level.high_valid = level.low_valid = False
        result.update({f"level_{j}_{key}": value for key, value in {
            "high": level.high, "low": level.low, "active": level.active,
            "high_hit": high_hit, "low_hit": low_hit, "total": level.total,
            "high_hits": level.high_hits, "low_hits": level.low_hits,
        }.items()})
    state.previous_inside, state.previous_instance = inside, instance
    return result


def _dwm_features(bars: pd.DataFrame, flags: pd.DataFrame) -> pd.DataFrame:
    """Use exact exchange timeframe.change inputs, including first-row flags."""
    output = {}
    for period in flags.columns:
        opn = high = low = previous_high = previous_low = np.nan
        high_hit = low_hit = False
        total = high_hits = low_hits = 0
        rows = []
        for changed, prices in zip(flags[period], bars[["Open", "High", "Low"]].to_numpy(dtype=float)):
            bar_open, bar_high, bar_low = prices
            if changed:
                previous_high, previous_low = high, low
                opn, high, low = bar_open, bar_high, bar_low
                high_hit = low_hit = False
                if np.isfinite(previous_high):
                    total += 1
            else:
                high, low = np.maximum(high, bar_high), np.minimum(low, bar_low)
            broke_high = not high_hit and cmp(bar_high) > cmp(previous_high)
            broke_low = not low_hit and cmp(bar_low) < cmp(previous_low)
            if broke_high:
                high_hit = True
                high_hits += 1
            if broke_low:
                low_hit = True
                low_hits += 1
            rows.append({"period_start": bool(changed), "open": opn,
                         "current_high": high, "current_low": low,
                         "previous_high": previous_high, "previous_low": previous_low,
                         "previous_midpoint": (previous_high + previous_low) / 2,
                         "break_high": bool(broke_high), "break_low": bool(broke_low),
                         "total": total, "high_hits": high_hits, "low_hits": low_hits})
        for column in (rows[0] if rows else ("period_start", "open", "current_high", "current_low",
                       "previous_high", "previous_low", "previous_midpoint", "break_high",
                       "break_low", "total", "high_hits", "low_hits")):
            dtype = bool if column in ("period_start", "break_high", "break_low") else (
                int if column in ("total", "high_hits", "low_hits") else float)
            output[f"{period}_{column}"] = pd.Series([row[column] for row in rows],
                                                     index=bars.index, dtype=dtype)
    return pd.DataFrame(output, index=bars.index)


def ict_killzones(
    bars: pd.DataFrame, *, sessions: dict[str, str] | None = None,
    timezone: str = "America/New_York", bar_minutes: int = 15,
    timeframe_limit: int = 30, max_days: int = 3, data_lookback: int = 20,
    range_measure: str = "Average", show_pivots: bool = True,
    show_midpoints: bool = False, use_alerts: bool = True,
    extend_which: str = "Most Recent", cutoff: str | None = None,
    level_multipliers: tuple[float, ...] = (), minimum_tick: float = .01,
    opening_times: tuple[str, ...] = ("0930", "1200", "1600"),
    period_changes: pd.DataFrame | None = None, as_of: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Return session/pivot/level features for completed, bar-open-indexed OHLC.

    ``sessions`` lists enabled windows; defaults match the four enabled source
    windows. ``level_multipliers=()`` matches Show Range Levels=false; source
    enabled multipliers are (.25, .5, 1). ``cutoff=None`` matches disabled cutoff;
    the source's configured interval is "1800-1801". Chart-only extension style
    is omitted; extend_which changes the actual active pivot tracking window.

    ``period_changes`` optionally supplies exact boolean Pine timeframe.change
    flags for any of D/W/M, aligned to the bars. Their exchange calendar is not
    inferred from the display timezone. No D/W/M features are emitted without
    these required inputs. Custom sessions must align to bar boundaries. Gaps
    that hide a session reset raise instead of inventing missing bars/resets.
    """
    validate_bars(bars)
    if not isinstance(bars.index, pd.DatetimeIndex) or bars.index.tz is None:
        raise ValueError("ICT requires a timezone-aware DatetimeIndex of bar opens")
    bar_minutes = integer("bar_minutes", bar_minutes)
    timeframe_limit = integer("timeframe_limit", timeframe_limit)
    if bar_minutes > timeframe_limit:
        raise ValueError("timeframe exceeds source's inclusive display limit")
    max_days, data_lookback = integer("max_days", max_days), integer("data_lookback", data_lookback)
    minimum_tick = positive("minimum_tick", minimum_tick)
    if range_measure not in ("Average", "Median", "Standard Deviation"):
        raise ValueError("unknown source range measurement")
    if extend_which not in ("Most Recent", "All"):
        raise ValueError("extend_which must be Most Recent or All")
    for name, value in {"show_pivots": show_pivots, "show_midpoints": show_midpoints,
                        "use_alerts": use_alerts}.items():
        if not isinstance(value, bool):
            raise ValueError(f"{name} must be boolean")
    level_multipliers = tuple(float(value) for value in level_multipliers)
    if not np.isfinite(level_multipliers).all() or any(cmp(value) <= 0 for value in level_multipliers):
        raise ValueError("level multipliers must be finite and positive, as in the source parser")
    tz = _timezone(timezone)
    local = bars.index.tz_convert(tz)
    if ((local.second != 0) | (local.microsecond != 0) | (local.nanosecond != 0)
            | ((local.hour * 60 + local.minute) % bar_minutes != 0)).any():
        raise ValueError("bar opens must align to the requested minute grid")
    if len(bars) > 1 and (bars.index[1:] - bars.index[:-1] < pd.Timedelta(minutes=bar_minutes)).any():
        raise ValueError("bar-open timestamps overlap the declared bar duration")
    available = bars.index + pd.Timedelta(minutes=bar_minutes)
    if as_of is not None:
        as_of = pd.Timestamp(as_of)
        if as_of.tz is None:
            raise ValueError("as_of must be timezone-aware")
        if (available > as_of).any():
            raise ValueError("forming/future bars exceed as_of availability")
    sessions = DEFAULT_SESSIONS.copy() if sessions is None else dict(sessions)
    windows = {}
    for name, spec in sessions.items():
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name):
            raise ValueError("session names must be identifiers")
        if name in ("D", "W", "M", "open"):
            raise ValueError("session name conflicts with reserved feature namespace")
        window = SessionWindow.parse(spec)
        if window.start % bar_minutes or window.end % bar_minutes:
            raise ValueError("session boundaries must align to chart bars")
        windows[name] = window
    cutoff_window = SessionWindow.parse(cutoff) if cutoff is not None else None
    opening_times = tuple(opening_times)
    if len(set(opening_times)) != len(opening_times):
        raise ValueError("opening times must be unique")
    opening_minutes = {time: _minute(time) for time in opening_times}
    if period_changes is not None:
        if (not isinstance(period_changes, pd.DataFrame) or not period_changes.index.equals(bars.index)
                or not period_changes.columns.is_unique
                or not set(period_changes.columns).issubset({"D", "W", "M"})):
            raise ValueError("period_changes must align to bars with unique D/W/M columns")
        if any(not pd.api.types.is_bool_dtype(period_changes[column])
               or period_changes[column].isna().any() for column in period_changes):
            raise ValueError("period_changes must contain nonmissing boolean flags")

    states = {name: _SessionState(levels=[_Level() for _ in level_multipliers]) for name in windows}
    opening_values = {time: np.nan for time in opening_times}
    opening_active = {time: False for time in opening_times}
    opening_previous = {time: False for time in opening_times}
    rows = []
    for stamp, local_stamp, known_at, prices in zip(bars.index, local, available,
                                                  bars[["Open", "High", "Low", "Close"]].to_numpy(dtype=float)):
        is_cutoff = cutoff_window.locate(local_stamp)[0] if cutoff_window else False
        row = {"available_at": known_at, "cutoff": is_cutoff}
        for name, window in windows.items():
            values = _session_step(states[name], window, local_stamp, stamp, known_at, prices,
                                   is_cutoff, max_days=max_days, data_lookback=data_lookback,
                                   range_measure=range_measure, show_pivots=show_pivots,
                                   show_midpoints=show_midpoints, use_alerts=use_alerts,
                                   extend_which=extend_which, multipliers=level_multipliers,
                                   minimum_tick=minimum_tick)
            row.update({f"{name}_{key}": value for key, value in values.items()})
        for time, minute in opening_minutes.items():
            member = local_stamp.hour * 60 + local_stamp.minute == minute
            event = member and not opening_previous[time]
            if event:
                opening_values[time], opening_active[time] = prices[0], True
            if not member and is_cutoff:
                opening_active[time] = False
            row.update({f"open_{time}": opening_values[time], f"open_{time}_event": event,
                        f"open_{time}_active": opening_active[time]})
            opening_previous[time] = member
        rows.append(row)
    result = pd.DataFrame(rows, index=bars.index)
    if bars.empty:
        empty_columns = {"available_at": pd.Series(available, index=bars.index),
                         "cutoff": pd.Series(False, index=bars.index, dtype=bool)}
        for name in windows:
            for fields, dtype in ((_SESSION_BOOLS, bool), (_SESSION_INTS, int),
                                  (_SESSION_TIMES, bars.index.dtype), (_SESSION_FLOATS, float)):
                for suffix in fields:
                    empty_columns[f"{name}_{suffix}"] = pd.Series(index=bars.index, dtype=dtype)
            for j in range(len(level_multipliers)):
                for suffix, dtype in (("high", float), ("low", float), ("active", bool),
                                      ("high_hit", bool), ("low_hit", bool), ("total", int),
                                      ("high_hits", int), ("low_hits", int)):
                    empty_columns[f"{name}_level_{j}_{suffix}"] = pd.Series(index=bars.index, dtype=dtype)
        for time in opening_times:
            for suffix, dtype in (("", float), ("_event", bool), ("_active", bool)):
                empty_columns[f"open_{time}{suffix}"] = pd.Series(index=bars.index, dtype=dtype)
        result = pd.DataFrame(empty_columns, index=bars.index)
    # Keep the timezone contract even for prefixes containing only NaT values.
    for name in windows:
        for suffix in _SESSION_TIMES:
            column = f"{name}_{suffix}"
            if column in result:
                result[column] = pd.to_datetime(result[column], utc=True).dt.tz_convert(bars.index.tz)
    if period_changes is not None:
        result = pd.concat([result, _dwm_features(bars, period_changes)], axis=1)
    result.attrs.update({"source": "nW5oGfdO/v19", "scope": "features and break conditions",
                         "admission_status": "pending exported Pine fixtures",
                         "index_kind": "bar_open", "timezone": timezone,
                         "bar_minutes": bar_minutes, "dwm_periods": list(period_changes)
                         if period_changes is not None else []})
    return result
