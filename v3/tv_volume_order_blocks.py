"""Volume-Weighted Order Block Zones [BigBeluga], source-backed numeric port.

Derived from KcnNgwDI by BigBeluga; CC BY-NC-SA 4.0:
https://creativecommons.org/licenses/by-nc-sa/4.0/
Changes: immutable causal zone snapshots and event features replace drawings.
The original Pine bytes are pinned in indicators/tradingview_sources/.

Volume controls the strength filter and visual opacity; zone boundaries remain
the pivot candle's unweighted high/low. Retroactive drawing origins are metadata
only: creation events first appear on the completed confirmation/trigger bar.
Built-in pivot tie behavior and external numerical parity remain fixture-gated.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from v3._tv_trend_support import comparison_value as cmp, integer, pine_ohlc, validate_bars
from v3.pine_compat import atr, sma


def volume_strength(volume: float, average: float) -> int:
    """Pine int truncates toward zero before the source clamps alpha to40..92."""
    ratio = volume / average if cmp(average) > 0 else 1.0
    alpha = min(max(int(96 - ratio * 12), 40), 92)
    return 100 - alpha


def _pivots(values: np.ndarray, length: int, *, high: bool) -> np.ndarray:
    """Confirm only after length right bars; rightmost equal extremum wins.

    The tie policy is an explicit Pine built-in assumption pending exported
    constant/tied-extremum fixtures, not a claimed cross-platform parity result.
    """
    result = np.full(len(values), np.nan)
    compared = cmp(values)
    for i in range(2 * length, len(values)):
        candidate = i - length
        left, right = compared[candidate - length:candidate], compared[candidate + 1:i + 1]
        accepted = ((compared[candidate] >= left).all() and (compared[candidate] > right).all()) if high else (
            (compared[candidate] <= left).all() and (compared[candidate] < right).all())
        if accepted:
            result[i] = values[candidate]
    return result


@dataclass(frozen=True)
class OrderBlock:
    """A causal observation; origin/cross bars can precede created_bar."""

    id: int
    bullish: bool
    high: float
    low: float
    trigger: float
    volume: float
    strength: int
    origin_bar: int
    origin_at: pd.Timestamp
    confirmed_bar: int
    cross_bar: int
    cross_at: pd.Timestamp
    created_bar: int
    available_at: pd.Timestamp
    retroactive: bool


@dataclass
class _Pending:
    high: float = np.nan
    low: float = np.nan
    level: float = np.nan
    volume: float = np.nan
    volume_average: float = np.nan
    origin: int = -1
    confirmed: int = -1
    triggered: bool = True


@dataclass
class _Machine:
    active: list[OrderBlock] = field(default_factory=list)
    bull: _Pending = field(default_factory=_Pending)
    bear: _Pending = field(default_factory=_Pending)
    next_id: int = 1
    last_bull_retest: int = 0
    last_bear_retest: int = 0

    def add(self, pending, bullish, i, cross, stamps, available, max_ob, *, retroactive):
        removed = []
        # Source removes overlapping zones only on the same side, inclusively.
        for j in range(len(self.active) - 1, -1, -1):
            old = self.active[j]
            if old.bullish == bullish and cmp(pending.high) >= cmp(old.low) and cmp(pending.low) <= cmp(old.high):
                removed.append((old.id, "overlap"))
                del self.active[j]
        zone = OrderBlock(self.next_id, bullish, pending.high, pending.low, pending.level,
                          pending.volume, volume_strength(pending.volume, pending.volume_average),
                          pending.origin, stamps[pending.origin], pending.confirmed, cross, stamps[cross],
                          i, available[i], retroactive)
        self.next_id += 1
        self.active.append(zone)
        if len(self.active) > max_ob:
            removed.append((self.active.pop(0).id, "capacity"))
        return zone, removed

    def manage(self, i, high, low, close):
        removed, bull_retest, bear_retest = [], -1, -1
        previous_high = high[i - 1] if i else np.nan
        previous_low = low[i - 1] if i else np.nan
        previous_close = close[i - 1] if i else np.nan
        # Newest zone gets first chance at the global per-side retest cooldown.
        for j in range(len(self.active) - 1, -1, -1):
            zone = self.active[j]
            invalid = cmp(low[i]) < cmp(zone.low) if zone.bullish else cmp(high[i]) > cmp(zone.high)
            if invalid:
                removed.append((zone.id, "invalidation"))
                del self.active[j]
                continue
            if zone.bullish:
                crossed = ((cmp(previous_low) <= cmp(zone.high) < cmp(low[i]))
                           or (cmp(previous_close) <= cmp(zone.high) < cmp(close[i])))
                if crossed and i - self.last_bull_retest > 5:
                    bull_retest, self.last_bull_retest = zone.id, i
            else:
                crossed = ((cmp(previous_high) >= cmp(zone.low) > cmp(high[i]))
                           or (cmp(previous_close) >= cmp(zone.low) > cmp(close[i])))
                if crossed and i - self.last_bear_retest > 5:
                    bear_retest, self.last_bear_retest = zone.id, i
        return removed, bull_retest, bear_retest


def _zone_fields(zone: OrderBlock | None) -> dict:
    return {"id": zone.id if zone else -1, "high": zone.high if zone else np.nan,
            "low": zone.low if zone else np.nan, "trigger": zone.trigger if zone else np.nan,
            "strength": float(zone.strength) if zone else np.nan,
            "origin_bar": zone.origin_bar if zone else -1,
            "confirmed_bar": zone.confirmed_bar if zone else -1,
            "cross_bar": zone.cross_bar if zone else -1,
            "created_bar": zone.created_bar if zone else -1,
            "origin_at": zone.origin_at if zone else pd.NaT,
            "cross_at": zone.cross_at if zone else pd.NaT,
            "available_at": zone.available_at if zone else pd.NaT}


def _empty_frame(index: pd.DatetimeIndex, include_snapshots: bool) -> pd.DataFrame:
    """Typed observation schema for a history with no bars."""
    row = {"available_at": pd.NaT, "atr": np.nan, "volume_sma": np.nan,
           "pivot_high": np.nan, "pivot_low": np.nan,
           "pivot_high_accepted": False, "pivot_low_accepted": False,
           "pivot_high_strength": np.nan, "pivot_low_strength": np.nan,
           "bull_retest": False, "bear_retest": False,
           "bull_retest_zone_id": -1, "bear_retest_zone_id": -1,
           "last_bull_retest_bar": 0, "last_bear_retest_bar": 0,
           "active_count": 0, "created_count": 0, "invalidation_count": 0,
           "overlap_removal_count": 0, "capacity_removal_count": 0}
    for side in ("bull", "bear"):
        row.update({f"{side}_active_count": 0, f"{side}_pending": False,
                    f"{side}_pending_origin_bar": -1, f"{side}_pending_trigger": np.nan,
                    f"{side}_created": False, f"{side}_created_retroactive": False})
        for state in ("created", "latest"):
            row.update({f"{side}_{state}_{key}": value for key, value in _zone_fields(None).items()})
    if include_snapshots:
        row.update({"active_zones": (), "created_zones": (), "removed_zone_events": ()})
    result = pd.DataFrame([row]).iloc[:0]
    result.index = index
    return result


def volume_order_blocks(
    bars: pd.DataFrame, *, sw_len: int = 10, max_ob: int = 10,
    displacement: float = 4.0, min_volume_strength: int = 0,
    bar_minutes: int = 15, include_zone_snapshots: bool = False,
    as_of: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Return causal pivot, creation, invalidation and B/S retest features.

    Requires finite OHLC and nonnegative volume, indexed by timezone-aware bar
    opens; each row is available at its open plus bar_minutes. Supply completed
    bars only, optionally enforced by as_of. B/S are the source's label events,
    not an invented trade-entry/exit policy or alert transport.

    The entire supplied history is the fixed calculation origin, with row0 as
    Pine bar_index0. The source declares calc_bars_count=3000: export fixtures
    must pin the same first calculation bar. This function never shifts a last
    3000-bar window when new data arrives, because doing so changes past state.

    Volume SMA20 and ATR100 lengths are fixed by the source. Active zones are
    bounded by max_ob across both directions. Pending pivots are replaced only
    by a new accepted pivot on the same side; a wick does not cancel a pending
    pivot. Optional zone snapshots are tuples of immutable OrderBlock objects.
    """
    validate_bars(bars)
    if not isinstance(bars.index, pd.DatetimeIndex) or bars.index.tz is None:
        raise ValueError("order blocks require timezone-aware bar-open timestamps")
    if ("Volume" not in bars or not pd.api.types.is_numeric_dtype(bars.Volume)
            or pd.api.types.is_bool_dtype(bars.Volume)
            or not np.isfinite(bars.Volume.to_numpy(dtype=float)).all() or (bars.Volume < 0).any()):
        raise ValueError("order blocks require finite nonnegative numeric Volume")
    sw_len = integer("sw_len", sw_len)
    max_ob = integer("max_ob", max_ob, minimum=0, maximum=500)
    min_volume_strength = integer("min_volume_strength", min_volume_strength, minimum=0, maximum=100)
    bar_minutes = integer("bar_minutes", bar_minutes)
    displacement = float(displacement)
    if not np.isfinite(displacement):
        raise ValueError("displacement must be finite")
    if not isinstance(include_zone_snapshots, bool):
        raise ValueError("include_zone_snapshots must be boolean")
    duration = pd.Timedelta(minutes=bar_minutes)
    if len(bars) > 1 and (bars.index[1:] - bars.index[:-1] < duration).any():
        raise ValueError("bar timestamps overlap the declared duration")
    available = bars.index + duration
    if as_of is not None:
        as_of = pd.Timestamp(as_of)
        if as_of.tz is None or (available > as_of).any():
            raise ValueError("as_of must be timezone-aware and exclude forming/future bars")
    high, low, close, volume = (bars[column].to_numpy(dtype=float) for column in ("High", "Low", "Close", "Volume"))
    volume_average = sma(bars.Volume.astype(float), 20).to_numpy()
    volatility = atr(pine_ohlc(bars), 100).to_numpy()
    pivot_high, pivot_low = _pivots(high, sw_len, high=True), _pivots(low, sw_len, high=False)
    machine = _Machine()
    rows = []
    for i in range(len(bars)):
        previous_bull_level, previous_bear_level = machine.bull.level, machine.bear.level
        created, removed = [], []
        accepted = {True: False, False: False}
        strength_at_pivot = {True: np.nan, False: np.nan}
        # Pine processes low-pivot retroactive creation before high-pivot creation.
        for bullish, pivot in ((True, pivot_low[i]), (False, pivot_high[i])):
            if not np.isfinite(pivot):
                continue
            origin = i - sw_len
            strength = volume_strength(volume[origin], volume_average[origin])
            strength_at_pivot[bullish] = strength
            if strength < min_volume_strength:
                continue
            accepted[bullish] = True
            level = low[origin] + volatility[i] * displacement if bullish else (
                high[origin] - volatility[i] * displacement)
            observed = high[origin + 1:i + 1] if bullish else low[origin + 1:i + 1]
            already_crossed = cmp(np.max(observed)) >= cmp(level) if bullish else cmp(np.min(observed)) <= cmp(level)
            pending = _Pending(high[origin], low[origin], level, volume[origin],
                               volume_average[origin], origin, i, bool(already_crossed))
            if bullish:
                machine.bull = pending
            else:
                machine.bear = pending
            if already_crossed:
                # Earliest chronological displacement during right-side confirmation bars.
                if bullish:
                    cross = next(j for j in range(origin + 1, i + 1)
                                 if cmp(close[j]) >= cmp(level) or cmp(high[j]) >= cmp(level))
                else:
                    cross = next(j for j in range(origin + 1, i + 1)
                                 if cmp(close[j]) <= cmp(level) or cmp(low[j]) <= cmp(level))
                mitigated = (cmp(low[cross:i + 1]) < cmp(pending.low)).any() if bullish else (
                    cmp(high[cross:i + 1]) > cmp(pending.high)).any()
                if not mitigated:
                    zone, deleted = machine.add(pending, bullish, i, cross, bars.index, available, max_ob,
                                                retroactive=True)
                    created.append(zone)
                    removed.extend(deleted)

        # Retroactive zones enter this pass. Delayed breakout zones below do not.
        deleted, bull_retest, bear_retest = machine.manage(i, high, low, close)
        removed.extend(deleted)
        for bullish, pending, previous_level in ((True, machine.bull, previous_bull_level),
                                                  (False, machine.bear, previous_bear_level)):
            if i == 0 or pending.origin < 0 or pending.triggered:
                continue
            crossed = (cmp(close[i]) > cmp(pending.level) and cmp(close[i - 1]) <= cmp(previous_level)) if bullish else (
                cmp(close[i]) < cmp(pending.level) and cmp(close[i - 1]) >= cmp(previous_level))
            if crossed:
                pending.triggered = True
                zone, deleted = machine.add(pending, bullish, i, i, bars.index, available, max_ob,
                                            retroactive=False)
                created.append(zone)
                removed.extend(deleted)

        row = {"available_at": available[i], "atr": volatility[i], "volume_sma": volume_average[i],
               "pivot_high": pivot_high[i], "pivot_low": pivot_low[i],
               "pivot_high_accepted": accepted[False], "pivot_low_accepted": accepted[True],
               "pivot_high_strength": float(strength_at_pivot[False]),
               "pivot_low_strength": float(strength_at_pivot[True]),
               "bull_retest": bull_retest >= 0, "bear_retest": bear_retest >= 0,
               "bull_retest_zone_id": bull_retest, "bear_retest_zone_id": bear_retest,
               "last_bull_retest_bar": machine.last_bull_retest,
               "last_bear_retest_bar": machine.last_bear_retest,
               "active_count": len(machine.active), "created_count": len(created),
               "invalidation_count": sum(reason == "invalidation" for _, reason in removed),
               "overlap_removal_count": sum(reason == "overlap" for _, reason in removed),
               "capacity_removal_count": sum(reason == "capacity" for _, reason in removed)}
        for side, bullish, pending in (("bull", True, machine.bull), ("bear", False, machine.bear)):
            active_side = [zone for zone in machine.active if zone.bullish == bullish]
            created_side = next((zone for zone in created if zone.bullish == bullish), None)
            row.update({f"{side}_active_count": len(active_side),
                        f"{side}_pending": pending.origin >= 0 and not pending.triggered,
                        f"{side}_pending_origin_bar": pending.origin,
                        f"{side}_pending_trigger": pending.level,
                        f"{side}_created": created_side is not None,
                        f"{side}_created_retroactive": created_side.retroactive if created_side else False})
            row.update({f"{side}_created_{key}": value for key, value in _zone_fields(created_side).items()})
            latest = active_side[-1] if active_side else None
            row.update({f"{side}_latest_{key}": value for key, value in _zone_fields(latest).items()})
        if include_zone_snapshots:
            row.update({"active_zones": tuple(machine.active), "created_zones": tuple(created),
                        "removed_zone_events": tuple(removed)})
        rows.append(row)
    result = pd.DataFrame(rows, index=bars.index)
    if not rows:
        result = _empty_frame(bars.index, include_zone_snapshots)
    for column in result:
        if column == "available_at" or column.endswith(("_origin_at", "_cross_at", "_available_at")):
            result[column] = pd.to_datetime(result[column], utc=True).dt.tz_convert(bars.index.tz)
    result.attrs.update({"source": "KcnNgwDI/v1", "scope": "features and label events",
                         "index_kind": "bar_open", "bar_minutes": bar_minutes,
                         "calculation_origin": "first supplied bar; no rolling calc_bars_count truncation",
                         "pivot_tie_policy": "rightmost tie; exported Pine fixture pending",
                         "admission_status": "pending exported Pine fixtures"})
    return result
