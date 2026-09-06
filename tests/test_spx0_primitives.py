"""spx0 primitives: OCC parsing + session ratio, depth-gated fills, dollar costs.
Self-contained; no archive access."""
import numpy as np
import pandas as pd
import pytest

from nn_meta.spx0.contracts import (parse_occ, parse_occ_frame, pick_atm,
                                    same_day_expiry, session_ratio)
from nn_meta.spx0.costs import BASE, STRESSED, gross_return, net_return
from nn_meta.spx0.fills import (DepthPolicy, FillFailure, entry_fill, exit_fill,
                                fillable, intrinsic)


def test_parse_occ_longest_root_first_and_strike_scale():
    c = parse_occ("SPXW250610P05900000")
    assert (c.root, c.index, c.right, c.strike) == ("SPXW", "SPX", "P", 5900.0)
    assert c.expiration == pd.Timestamp("2025-06-10")
    n = parse_occ("NDX250620C10200000")
    assert (n.root, n.index, n.strike) == ("NDX", "NDX", 10200.0)
    with pytest.raises(ValueError):
        parse_occ("AAPL250620C00200000")


def test_parse_occ_frame_matches_scalar_and_fails_closed():
    s = pd.Series(["SPXW250610P05900000", "NDXP250610C21700000"])
    f = parse_occ_frame(s)
    assert list(f["index"]) == ["SPX", "NDX"] and list(f["strike"]) == [5900.0, 21700.0]
    with pytest.raises(ValueError, match="unparseable"):
        parse_occ_frame(pd.Series(["SPXW250610P05900000", "junk"]))


def _zero_dte(ts):
    rows = []
    for k in (5880, 5890, 5900, 5910, 5920, 5930):
        rows.append({"occ": f"SPXW250610C{k*1000:08d}", "timestamp": ts, "Volume": 10,
                     "index": "SPX", "right": "C", "strike": float(k),
                     "expiration": pd.Timestamp("2025-06-10")})
    rows.append({"occ": "SPXW250611C05900000", "timestamp": ts, "Volume": 10,
                 "index": "SPX", "right": "C", "strike": 5900.0,
                 "expiration": pd.Timestamp("2025-06-11")})
    return pd.DataFrame(rows)


def test_session_ratio_is_measured_from_the_first_bar():
    ts = pd.Timestamp("2025-06-10 13:30")
    z = same_day_expiry(_zero_dte(ts), ts)
    assert len(z) == 6                                    # next-day contract excluded
    r = session_ratio(z, 590.5, index="SPX", first_bar_ts=ts)
    assert r == pytest.approx(5905.0 / 590.5)
    with pytest.raises(ValueError, match="cannot measure"):
        session_ratio(z.head(3), 590.5, index="SPX", first_bar_ts=ts)


def test_pick_atm_needs_a_recent_completed_print():
    ts = pd.Timestamp("2025-06-10 14:00")
    z = same_day_expiry(_zero_dte(ts), ts)
    # prints stamped ts complete at ts+1min: selectable from then on…
    c = pick_atm(z, index="SPX", right="C", mapped_spot=5912.0,
                 at=ts + pd.Timedelta(minutes=1))
    assert c is not None and c.strike == 5910.0
    # …but NOT at ts itself — the bar stamped ts is still forming (lookahead
    # fix, review 2026-08-24)
    assert pick_atm(z, index="SPX", right="C", mapped_spot=5912.0, at=ts) is None
    stale = pick_atm(z, index="SPX", right="C", mapped_spot=5912.0,
                     at=ts + pd.Timedelta(minutes=10))
    assert stale is None


def _bars():
    t0 = pd.Timestamp("2025-06-10 14:00")
    return pd.DataFrame({
        "timestamp": [t0 + pd.Timedelta(minutes=i) for i in range(6)],
        "Open": [0.30] * 6, "High": [0.32, 0.33, 0.34, 0.35, 0.36, 0.37],
        "Low": [0.28, 0.29, 0.30, 0.31, 0.32, 0.33], "Close": [0.30] * 6,
        "Volume": [1, 0, 5, 1, 9, 0],
    })


def test_entry_fill_is_after_signal_and_depth_gated():
    bars, pol = _bars(), DepthPolicy(qty=1, depth_mult=2.0, entry_window_min=3)
    assert list(fillable(bars["Volume"], pol)) == [False, False, True, False, True, False]
    ts, price, depth, fail = entry_fill(bars, bars["timestamp"][0], pol)
    assert fail is None and ts == bars["timestamp"][2] + pd.Timedelta(minutes=1) and price == 0.34 and depth == 5
    # window of 1 bar after the signal: bar 1 has no depth -> rejected, kept as data
    _, _, _, fail = entry_fill(bars, bars["timestamp"][0], DepthPolicy(entry_window_min=1))
    assert fail is FillFailure.NO_DEPTH_ENTRY
    _, _, _, fail = entry_fill(bars, bars["timestamp"][5], pol)
    assert fail is FillFailure.NO_ENTRY_BAR


def test_exit_fill_walks_forward_then_settles_to_intrinsic():
    bars, pol = _bars(), DepthPolicy()
    floor = bars["timestamp"][5]
    ts, price, _, fail = exit_fill(bars, bars["timestamp"][3], pol,
                                   session_floor_ts=floor, intrinsic_at_floor=0.0)
    assert fail is None and ts == bars["timestamp"][4] + pd.Timedelta(minutes=1) and price == 0.32   # LOW
    ts, price, depth, fail = exit_fill(bars, bars["timestamp"][5], pol,
                                       session_floor_ts=floor, intrinsic_at_floor=1.25)
    assert fail is FillFailure.SETTLED_INTRINSIC and ts == floor + pd.Timedelta(minutes=1) and price == 1.25
    assert intrinsic("C", 5900, 5912.5) == 12.5 and intrinsic("P", 5900, 5912.5) == 0.0


def test_costs_are_in_points_and_bite_small_premiums():
    # 0.30 premium: base round trip = 2 × (0.05 + 0.013) = 0.126 points ≈ 42%
    assert gross_return(0.30, 0.30) == 0.0
    flat = net_return(0.30, 0.30, BASE)
    assert -0.45 < flat < -0.30
    assert net_return(0.30, 0.30, STRESSED) < flat
    # spread scales above 1.00, so a 3.00 premium pays more points but less %
    assert BASE.half_spread(3.0) == pytest.approx(0.15)
    assert net_return(3.0, 3.0, BASE) > flat
    with pytest.raises(ValueError):
        net_return(0.0, 0.1)


def test_entry_window_is_minutes_not_sparse_bars():
    # one print 1 minute after the signal with no depth, the next print 90
    # minutes later with depth: a bar-count window would fill it, a time
    # window must reject it.
    t0 = pd.Timestamp("2025-06-10 14:00")
    bars = pd.DataFrame({"timestamp": [t0, t0 + pd.Timedelta(minutes=1),
                                       t0 + pd.Timedelta(minutes=90)],
                         "Open": 0.3, "High": 0.3, "Low": 0.3, "Close": 0.3,
                         "Volume": [5, 1, 50]})
    _, _, _, fail = entry_fill(bars, t0, DepthPolicy(entry_window_min=3))
    assert fail is FillFailure.NO_DEPTH_ENTRY


def test_implied_index_level_uses_parity_pairs():
    from nn_meta.spx0.contracts import implied_index_level
    at = pd.Timestamp("2025-06-10 19:59")
    rows = []
    for k in (5880, 5890, 5900, 5910, 5920):
        c, p = max(5903.2 - k, 0) + 0.2, max(k - 5903.2, 0) + 0.2      # parity-consistent
        rows += [{"index": "SPX", "right": "C", "strike": float(k), "Close": c, "timestamp": at},
                 {"index": "SPX", "right": "P", "strike": float(k), "Close": p, "timestamp": at}]
    z = pd.DataFrame(rows)
    assert implied_index_level(z, index="SPX", at=at) == pytest.approx(5903.2, abs=1e-6)
    assert implied_index_level(z.head(4), index="SPX", at=at) is None      # < 3 pairs
