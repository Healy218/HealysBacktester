# SPDX-License-Identifier: MPL-2.0
# Adapted from Volume Footprint: Measuring by Math & Geometry, © ata_sabanci.
# https://www.tradingview.com/script/Tm1cGCPD-Volume-Footprint-Measuring-by-Math-Geometry/
# https://mozilla.org/MPL/2.0/
# Changes: completed-prefix numerical snapshots, explicit engine availability,
# no chart/table rendering, no trade rules, and no synthetic native footprint.
"""Pinned publication 4 footprint mathematics, with separate engine contracts.

Geometric buy/sell amounts are modeled allocations, not observed aggressor
trades. Intrabar amounts must be explicitly supplied signed up/down volumes
from TradingView/ta/14.requestUpAndDownVolume on the declared lower timeframe.
That engine still distributes those amounts over price by the source's bells.
Native TradingView footprint rows cannot be recovered from OHLCV or inferred
from these intrabar totals and are deliberately unavailable here.

Source table/profile work runs on barstate.islast. Each historical output is
the result of running that work on the corresponding completed prefix. POC
retains the source's stale-value behavior, with a separate freshness flag.
Numerical source tests are not exported TradingView parity fixtures.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
import pandas as pd

from v3._tv_profile_support import frame_from_rows, profile_observations
from v3._tv_trend_support import comparison_value as cmp, integer, positive


def _round(value):
    return int(math.floor(value + .5))


def _table_cdf(z):
    """Source A&S approximation, intentionally distinct from profile CDF."""
    x = abs(z)
    t = 1.0 / (1.0 + .2316419 * x)
    poly = t * (.319381530 + t * (-.356563782 + t * (
        1.781477937 + t * (-1.821255978 + t * 1.330274429))))
    phi = .3989422804014327 * math.exp(-.5 * x * x)
    return max(0., min(1., 1. - phi * poly if z >= 0 else phi * poly))


def _profile_erfc(x):
    """Literal Cody rational approximation used by the pinned source."""
    y = abs(x)
    if y <= .46875:
        z = y * y if y > 1.11e-16 else 0.
        num, den = .185777706184603153 * z, z
        for a, b in ((3.16112374387056560, 23.6012909523441209),
                     (113.864154151050156, 244.024637934444173),
                     (377.485237685302021, 1282.61652607737228)):
            num, den = (num + a) * z, (den + b) * z
        return 1. - x * (num + 3209.37758913846947) / (den + 2844.23683343917062)
    r = 0.
    if y <= 4.:
        num, den = 2.15311535474403846e-8 * y, y
        for a, b in ((.564188496988670089, 15.7449261107098347),
                     (8.88314979438837594, 117.693950891312499),
                     (66.1191906371416295, 537.181101862009858),
                     (298.635138197400131, 1621.38957456669019),
                     (881.952221241769090, 3290.79923573345963),
                     (1712.04761263407058, 4362.61909014324716),
                     (2051.07837782607147, 3439.36767414372164)):
            num, den = (num + a) * y, (den + b) * y
        r = (num + 1230.33935479799725) / (den + 1230.33935480374942)
    elif y < 26.543:
        z = 1. / (y * y)
        num, den = .0163153871373020978 * z, z
        for a, b in ((.305326634961232344, 2.56852019228982242),
                     (.360344899949804439, 1.87295284992346047),
                     (.125781726111229246, .527905102951428412),
                     (.0160837851487422766, .0605183413124413191)):
            num, den = (num + a) * z, (den + b) * z
        r = z * (num + .000658749161529837803) / (den + .00233520497626869185)
        r = (.56418958354775628695 - r) / y
    if y < 26.543:
        ysq = math.floor(y * 16.) / 16.
        r *= math.exp(-ysq * ysq) * math.exp(-(y - ysq) * (y + ysq))
    return r if x >= 0 else 2. - r


def _profile_cdf(z):
    return .5 * _profile_erfc(-z * .7071067811865476)


def _imbalances(buy, sell, ratio):
    # Missing opposing rows remain missing; summed-window rows are real zeros.
    b = np.zeros(len(buy), dtype=bool)
    s = np.zeros(len(sell), dtype=bool)
    b[1:] = (cmp(buy[1:]) > 0) & (cmp(buy[1:]) > cmp(sell[:-1] * ratio))
    s[:-1] = (cmp(sell[:-1]) > 0) & (cmp(sell[:-1]) > cmp(buy[1:] * ratio))
    return b, s


def _gaussian_rows(buy, sell, high, low, close, axis, view, tick, bell_div, ratio):
    n = 2 * view + 1
    rows = np.full((2, n), np.nan)
    off = np.zeros(2)
    kmin, kmax = axis - view, axis + view
    tick_lo, tick_hi = _round(low / tick), _round(high / tick)
    if cmp(high - low) <= 0:
        flat = _round(close / tick)
        if kmin <= flat <= kmax:
            rows[:, flat - kmin] = (buy, sell)
        else:
            off[:] = (buy, sell)
    else:
        sigma = (high - low) / bell_div
        frame_bot, frame_top = (kmin - .5) * tick, (kmax + .5) * tick
        start, end = max(tick_lo, kmin), min(tick_hi, kmax)
        for side, amount, mu in ((0, buy, low + (close - low) / 2.),
                                 (1, sell, close + (high - close) / 2.)):
            cdf_low = _table_cdf((low - mu) / sigma)
            mass = _table_cdf((high - mu) / sigma) - cdf_low
            ok = cmp(mass) > cmp(1e-12)
            if cmp(frame_bot) > cmp(low) and ok:
                off[side] += max(0., (_table_cdf((min(frame_bot, high) - mu) / sigma)
                                     - cdf_low) / mass) * amount
            if start <= end:
                previous = _table_cdf((max((start - .5) * tick, low) - mu) / sigma)
                for k in range(start, end + 1):
                    following = _table_cdf((min((k + .5) * tick, high) - mu) / sigma)
                    rows[side, k - kmin] = max(0., (following - previous) / mass) * amount if ok else 0.
                    previous = following
            if cmp(frame_top) < cmp(high) and ok:
                off[side] += max(0., (_table_cdf((high - mu) / sigma)
                                     - _table_cdf((max(frame_top, low) - mu) / sigma)) / mass) * amount
    bimb, simb = _imbalances(rows[0], rows[1], ratio)
    return rows[0], rows[1], off[0], off[1], bimb, simb


def _metrics(prices, buy, sell, va_pct, ratio, *, require_positive):
    total = buy + sell
    best, poc = (0. if require_positive else -1.), -1
    for k, value in enumerate(total):
        if cmp(value) > cmp(best):
            best, poc = value, k
    bimb, simb = _imbalances(buy, sell, ratio)
    result = {"poc": np.nan, "poc_index": poc, "val": np.nan, "vah": np.nan,
              "imbalance_above": np.nan, "imbalance_above_side": 0,
              "imbalance_below": np.nan, "imbalance_below_side": 0}
    if poc < 0:
        return result
    lo = hi = poc
    acc, target = total[poc], va_pct / 100. * sum(total)
    while cmp(acc) < cmp(target) and (lo > 0 or hi < len(total) - 1):
        up, down = total[hi + 1] if hi < len(total) - 1 else 0., total[lo - 1] if lo > 0 else 0.
        if hi == len(total) - 1 or (lo > 0 and cmp(up) < cmp(down)):
            lo -= 1
            acc += down
        else:  # source ties expand upward
            hi += 1
            acc += up
    result.update(poc=float(prices[poc]), val=float(prices[lo]), vah=float(prices[hi]))
    for name, indices in (("above", range(poc + 1, len(total))), ("below", range(poc - 1, -1, -1))):
        for k in indices:
            if bimb[k] or simb[k]:
                result[f"imbalance_{name}"] = float(prices[k])
                result[f"imbalance_{name}_side"] = 1 if bimb[k] else -1
                break
    return result


@dataclass(frozen=True)
class _Component:
    mu: float
    sigma: float
    coef: float
    low: float
    high: float


def _density(price, components):
    result = np.zeros_like(price, dtype=float)
    for comp in components:
        z = (price - comp.mu) / comp.sigma
        value = comp.coef * .3989422804014327 * np.exp(-.5 * z * z)
        result += np.where((cmp(price) >= cmp(comp.low)) & (cmp(price) <= cmp(comp.high)), value, 0.)
    return result


def _band_mass(low, high, components):
    total = 0.
    for comp in components:
        a, b = max(low, comp.low), min(high, comp.high)
        if cmp(b) > cmp(a):
            total += comp.coef * comp.sigma * (_profile_cdf((b - comp.mu) / comp.sigma)
                                              - _profile_cdf((a - comp.mu) / comp.sigma))
    return total


def _simpson(low, high, sigma, comps, denominator=1.):
    n = max(12, int(math.ceil(16. * (high - low) / sigma)))
    n += n % 2
    step = (high - low) / n
    # Source guard for pathologically large arrays, never silently coarsen.
    if n > 1_000_000:
        raise ValueError("footprint diagnostic integration exceeds 1000000 subdivisions")
    values = _density(low + np.arange(n + 1) * step, comps) / denominator
    acc = values[0] + values[-1]
    for k in range(1, n):
        acc += (4. if k % 2 else 2.) * values[k]
    return acc * step / 3.


def _diagnostics(comps_b, comps_s, atoms, sum_b, sum_s, low, high):
    """Source Simpson mass audit and normalized-density crossing integration."""
    components = comps_b + comps_s
    raw_cuts = sorted([low, high] + [v for c in components for v in (c.low, c.high)])
    cuts = []
    for value in raw_cuts:
        if not cuts or cmp(value) != cmp(cuts[-1]):
            cuts.append(value)
    int_b = int_s = int_min = 0.
    for seg_lo, seg_hi in zip(cuts, cuts[1:]):
        mid = .5 * (seg_lo + seg_hi)
        active_b = [c for c in comps_b if cmp(c.low) <= cmp(mid) <= cmp(c.high)]
        active_s = [c for c in comps_s if cmp(c.low) <= cmp(mid) <= cmp(c.high)]
        if not active_b and not active_s:
            continue
        sigma = min(c.sigma for c in active_b + active_s)
        int_b += _simpson(seg_lo, seg_hi, sigma, active_b)
        int_s += _simpson(seg_lo, seg_hi, sigma, active_s)
        if cmp(sum_b) <= 0 or cmp(sum_s) <= 0:
            continue
        def difference(x):
            return float(_density(x, active_b)) / sum_b - float(_density(x, active_s)) / sum_s
        subcuts = [seg_lo]
        previous = difference(seg_lo)
        for j in range(1, 13):
            x = seg_lo + (seg_hi - seg_lo) * j / 12
            current = difference(x)
            if cmp(previous * current) < 0:
                rlo, rhi = seg_lo + (seg_hi - seg_lo) * (j - 1) / 12, x
                iterations = 0
                while cmp(rhi - rlo) > cmp(abs(.5 * (rlo + rhi)) * 2.3e-16) and iterations < 90:
                    middle = .5 * (rlo + rhi)
                    if cmp(difference(rlo) * difference(middle)) <= 0:
                        rhi = middle
                    else:
                        rlo = middle
                    iterations += 1
                subcuts.append(.5 * (rlo + rhi))
            previous = current
        subcuts.append(seg_hi)
        for a, b in zip(subcuts, subcuts[1:]):
            if cmp(b) <= cmp(a):
                continue
            use_buy = cmp(difference(.5 * (a + b))) <= 0
            int_min += _simpson(a, b, sigma, active_b if use_buy else active_s,
                                sum_b if use_buy else sum_s)
    atom_b, atom_s = sum(a[1] for a in atoms), sum(a[2] for a in atoms)
    atom_overlap = 0.
    used = set()
    if cmp(sum_b) > 0 and cmp(sum_s) > 0:
        for i, atom in enumerate(atoms):
            if i in used:
                continue
            pb = ps = 0.
            for j in range(i, len(atoms)):
                if j not in used and cmp(atoms[j][0]) == cmp(atom[0]):
                    used.add(j)
                    pb += atoms[j][1]
                    ps += atoms[j][2]
            atom_overlap += min(pb / sum_b, ps / sum_s)
    rb = abs((int_b + atom_b) / sum_b - 1.) if cmp(sum_b) > 0 else 0.
    rs = abs((int_s + atom_s) / sum_s - 1.) if cmp(sum_s) > 0 else 0.
    overlap = 100. * (int_min + atom_overlap) if cmp(sum_b) > 0 and cmp(sum_s) > 0 else np.nan
    return overlap, (rb + rs) * 1_000_000.


def _intrabar_amounts(bars, available, stream, lower_minutes, bar_minutes):
    """Validate actual signed library aggregates; absence is never volume zero."""
    lower_minutes = integer("intrabar_minutes", lower_minutes)
    if lower_minutes > bar_minutes:
        raise ValueError("intrabar_minutes must not exceed chart bar duration")
    if not isinstance(stream, pd.DataFrame) or not stream.index.equals(bars.index):
        raise ValueError("intrabar stream must be a DataFrame aligned exactly to bar opens")
    required = ("up_volume", "down_volume", "observed_at")
    if any(name not in stream for name in required):
        raise ValueError("intrabar stream requires up_volume, down_volume, observed_at")
    for name in required[:2]:
        if not pd.api.types.is_numeric_dtype(stream[name]) or pd.api.types.is_bool_dtype(stream[name]):
            raise ValueError("intrabar volumes must be numeric signed library outputs")
    up, down = (stream[name].to_numpy(float) for name in required[:2])
    missing = np.isnan(up)
    if not np.array_equal(missing, np.isnan(down)):
        raise ValueError("missing intrabar up/down volumes must be paired")
    if np.isinf(up).any() or np.isinf(down).any() or (up[~missing] < 0).any() or (down[~missing] > 0).any():
        raise ValueError("up_volume must be nonnegative and down_volume nonpositive")
    if not isinstance(stream.observed_at.dtype, pd.DatetimeTZDtype):
        raise ValueError("intrabar observed_at must be timezone-aware")
    observed = pd.DatetimeIndex(stream.observed_at)
    if not np.array_equal(observed.isna(), missing):
        raise ValueError("engine data requires observed_at; absent data requires NaT")
    # Fail closed instead of moving late aggregate data into a historical bar.
    if ((observed[~missing] < bars.index[~missing]) | (observed[~missing] > available[~missing])).any():
        raise ValueError("intrabar observed_at lies outside its completed bar's availability")
    return up, np.abs(down), observed


def volume_footprint(bars, *, tick_size, engine="geometric", intrabar_stream=None,
                     intrabar_minutes=1, window=5, view_ticks=5, bell_div=3.,
                     profile_period=23, profile_resolution=100, value_area_pct=70.,
                     imbalance_pct=300., bar_minutes=15, as_of=None,
                     include_levels=False, include_diagnostics=True):
    """Return source numerical features for each completed bar prefix.

    ``include_levels`` adds immutable bottom-to-top table levels, per-selected
    bar row volumes/imbalance flags, and sampled chart density tuples. Chart
    sample values are volume-per-price intensity, not per-row volume; chart
    POC and imbalance band-volume columns integrate a one-tick band instead.

    ``intrabar_stream`` contains exact aligned ``up_volume`` (>=0),
    ``down_volume`` (<=0), and timezone-aware ``observed_at``. Missing library
    outputs must be paired NaN with NaT. Already aggregated streams do not
    establish tick-level aggressor classifications or completeness of a feed.
    Strict bar-close availability rejects late observations rather than
    assigning future data to earlier feature rows.
    """
    if engine == "native":
        raise NotImplementedError("native footprint requires exact provider footprint.rows() price/volume/imbalance objects; OHLCV and intrabar totals cannot supply them")
    if engine not in ("geometric", "intrabar"):
        raise ValueError("engine must be geometric, intrabar, or native")
    available = profile_observations(bars, bar_minutes, as_of)
    tick = positive("tick_size", tick_size)
    window = integer("window", window, 2, 60)
    view = integer("view_ticks", view_ticks, 1, 50)
    period = integer("profile_period", profile_period, 2, 60)
    resolution = integer("profile_resolution", profile_resolution, 20, 400)
    for name, value, minimum, maximum in (("bell_div", bell_div, 1, 10),
                                          ("value_area_pct", value_area_pct, 1, 100),
                                          ("imbalance_pct", imbalance_pct, 1, 1000)):
        positive(name, value)
        if not minimum <= value <= maximum:
            raise ValueError(f"{name} must be in [{minimum}, {maximum}]")
    if not isinstance(include_levels, bool) or not isinstance(include_diagnostics, bool):
        raise ValueError("include_levels and include_diagnostics must be boolean")
    high, low, close, volume = (bars[k].to_numpy(float) for k in ("High", "Low", "Close", "Volume"))
    if engine == "geometric":
        if intrabar_stream is not None:
            raise ValueError("intrabar_stream is only valid for the intrabar engine")
        share = np.divide(close - low, high - low, out=np.full(len(bars), .5), where=cmp(high - low) > 0)
        buy, sell = volume * share, volume * (1. - share)
        observed = available
    else:
        buy, sell, observed = _intrabar_amounts(bars, available, intrabar_stream, intrabar_minutes, bar_minutes)
    ratio = imbalance_pct / 100.
    prototype = {"available_at": None, "engine_observed_at": None, "engine": engine,
                 "engine_data_available": False, "buy_volume": np.nan, "sell_volume": np.nan,
                 "total_volume": np.nan, "delta_volume": np.nan, "buy_share_pct": np.nan,
                 "sell_share_pct": np.nan, "intrabar_coverage_bars": 0,
                 "axis_price": np.nan, "window_bars": 0, "window_buy_volume": 0.,
                 "window_sell_volume": 0., "window_in_frame_buy": 0., "window_in_frame_sell": 0.,
                 "window_off_frame_buy": 0., "window_off_frame_sell": 0.,
                 "dashboard_poc": np.nan, "dashboard_val": np.nan, "dashboard_vah": np.nan,
                 "dashboard_imbalance_above": np.nan, "dashboard_imbalance_above_side": 0,
                 "dashboard_imbalance_below": np.nan, "dashboard_imbalance_below_side": 0,
                 "profile_data_bars": 0, "profile_buy_volume": 0., "profile_sell_volume": 0.,
                 "profile_low": np.nan, "profile_high": np.nan, "profile_status": "no_engine_data",
                 "chart_poc": np.nan, "chart_poc_fresh": False, "chart_poc_buy_volume": np.nan,
                 "chart_poc_sell_volume": np.nan, "chart_val": np.nan, "chart_vah": np.nan,
                 "chart_imbalance_above": np.nan, "chart_imbalance_above_side": 0,
                 "chart_imbalance_below": np.nan, "chart_imbalance_below_side": 0,
                 "chart_imbalance_above_buy_volume": np.nan, "chart_imbalance_above_sell_volume": np.nan,
                 "chart_imbalance_below_buy_volume": np.nan, "chart_imbalance_below_sell_volume": np.nan,
                 "profile_overlap_pct": np.nan, "profile_residual_ppm": np.nan,
                 "profile_tilt_pct": np.nan, "diagnostics_computed": False}
    if include_levels:
        prototype.update(table_prices=(), table_buy_volumes=(), table_sell_volumes=(),
                         window_offsets=(), window_buy_rows=(), window_sell_rows=(),
                         window_buy_imbalances=(), window_sell_imbalances=(),
                         profile_prices=(), profile_buy_density=(), profile_sell_density=())
    rows = []
    chart_poc = np.nan
    coverage = 0
    for i in range(len(bars)):
        row = dict(prototype)
        has_data = bool(np.isfinite(buy[i]) and np.isfinite(sell[i]))
        coverage = min(5000, coverage + 1) if has_data else 0
        total = buy[i] + sell[i]
        row.update(available_at=available[i], engine_observed_at=observed[i], engine_data_available=has_data,
                   buy_volume=buy[i], sell_volume=sell[i], total_volume=total, delta_volume=buy[i] - sell[i],
                   buy_share_pct=100. * buy[i] / total if cmp(total) > 0 else np.nan,
                   sell_share_pct=100. * (1. - buy[i] / total) if cmp(total) > 0 else np.nan,
                   intrabar_coverage_bars=coverage if engine == "intrabar" else 0)
        axis = _round(close[i] / tick)
        row["axis_price"] = axis * tick
        prices = np.arange(axis - view, axis + view + 1) * tick
        sum_b, sum_s = np.zeros(len(prices)), np.zeros(len(prices))
        selected = []
        for j in range(i, max(-1, i - 5000), -1):
            if len(selected) >= window:
                break
            if not np.isfinite(buy[j] + sell[j]) or cmp(buy[j] + sell[j]) <= 0:
                continue
            if _round(low[j] / tick) > axis + view or _round(high[j] / tick) < axis - view:
                continue
            br, sr, bo, so, bi, si = _gaussian_rows(buy[j], sell[j], high[j], low[j], close[j], axis, view, tick, bell_div, ratio)
            if not (np.isfinite(br).any() or np.isfinite(sr).any()):
                continue
            selected.append((i - j, br, sr, bi, si))
            sum_b += np.nan_to_num(br)
            sum_s += np.nan_to_num(sr)
            row["window_buy_volume"] += buy[j]
            row["window_sell_volume"] += sell[j]
            row["window_off_frame_buy"] += bo
            row["window_off_frame_sell"] += so
        row.update(window_bars=len(selected), window_in_frame_buy=float(sum(sum_b)), window_in_frame_sell=float(sum(sum_s)))
        dashboard = _metrics(prices, sum_b, sum_s, value_area_pct, ratio, require_positive=True)
        row.update({f"dashboard_{k}": v for k, v in dashboard.items() if k != "poc_index"})
        if include_levels:
            row.update(table_prices=tuple(prices), table_buy_volumes=tuple(sum_b), table_sell_volumes=tuple(sum_s),
                       window_offsets=tuple(x[0] for x in selected), window_buy_rows=tuple(tuple(x[1]) for x in selected),
                       window_sell_rows=tuple(tuple(x[2]) for x in selected), window_buy_imbalances=tuple(tuple(x[3]) for x in selected),
                       window_sell_imbalances=tuple(tuple(x[4]) for x in selected))
        comps_b, comps_s, atoms = [], [], []
        sum_pb = sum_ps = 0.
        lo = hi = np.nan
        for j in range(i, max(-1, i - period), -1):
            if not np.isfinite(buy[j] + sell[j]):
                continue
            row["profile_data_bars"] += 1
            lo = low[j] if np.isnan(lo) else min(lo, low[j])
            hi = high[j] if np.isnan(hi) else max(hi, high[j])
            sum_pb += buy[j]
            sum_ps += sell[j]
            if cmp(high[j] - low[j]) <= 0:
                atoms.append((close[j], buy[j], sell[j]))
            else:
                sigma = (high[j] - low[j]) / bell_div
                for comps, amount, mu in ((comps_b, buy[j], low[j] + (close[j] - low[j]) / 2.),
                                          (comps_s, sell[j], close[j] + (high[j] - close[j]) / 2.)):
                    z = _profile_cdf((high[j] - mu) / sigma) - _profile_cdf((low[j] - mu) / sigma)
                    if cmp(amount) > 0 and cmp(z) > 0:
                        comps.append(_Component(mu, sigma, amount / (sigma * z), low[j], high[j]))
        row.update(profile_low=lo, profile_high=hi, profile_buy_volume=sum_pb, profile_sell_volume=sum_ps)
        if row["profile_data_bars"]:
            row["profile_status"] = "zero_volume"
        if np.isfinite(lo) and cmp(sum_pb + sum_ps) > 0:
            row["profile_tilt_pct"] = 100. * (sum_pb - sum_ps) / (sum_pb + sum_ps)
            if include_diagnostics:
                overlap, residual = _diagnostics(comps_b, comps_s, atoms, sum_pb, sum_ps, lo, hi)
                row.update(profile_overlap_pct=overlap, profile_residual_ppm=residual, diagnostics_computed=True)
            row["profile_status"] = "flat_atoms_only"
            if cmp(hi - lo) > 0:
                profile_prices = lo + np.arange(resolution + 1) * ((hi - lo) / resolution)
                pb, ps = _density(profile_prices, comps_b), _density(profile_prices, comps_s)
                chart = _metrics(profile_prices, pb, ps, value_area_pct, ratio, require_positive=False)
                chart_poc = chart["poc"]
                row.update({f"chart_{k}": v for k, v in chart.items() if k != "poc_index"})
                row.update(chart_poc_fresh=True, chart_poc_buy_volume=_band_mass(chart_poc - tick / 2., chart_poc + tick / 2., comps_b),
                           chart_poc_sell_volume=_band_mass(chart_poc - tick / 2., chart_poc + tick / 2., comps_s),
                           profile_status="ready" if comps_b or comps_s else "atoms_without_density")
                for direction in ("above", "below"):
                    price = chart[f"imbalance_{direction}"]
                    if np.isfinite(price):
                        row[f"chart_imbalance_{direction}_buy_volume"] = _band_mass(price - tick / 2., price + tick / 2., comps_b)
                        row[f"chart_imbalance_{direction}_sell_volume"] = _band_mass(price - tick / 2., price + tick / 2., comps_s)
                if include_levels:
                    row.update(profile_prices=tuple(profile_prices), profile_buy_density=tuple(pb), profile_sell_density=tuple(ps))
        row["chart_poc"] = chart_poc  # Pine var persists when no new control level is computed
        rows.append(row)
    result = frame_from_rows(rows, bars.index, prototype, timestamp_columns=("available_at", "engine_observed_at"))
    result.attrs.update(public_id="Tm1cGCPD", publication_version=4, engine=engine,
                        source_semantics="completed-prefix last-bar snapshots; default metric scopes both",
                        intrabar_minutes=intrabar_minutes if engine == "intrabar" else None,
                        native_footprint_supported=False, parity_status="exported TradingView fixtures pending")
    return result
