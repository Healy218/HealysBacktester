"""spx0 round 3: credit verticals (loss bounded by CONSTRUCTION — the round-2
naked-short blowup must be structurally impossible) and the intraday-native
signal seats. No archive access."""
import numpy as np
import pandas as pd
import pytest

from nn_meta.mark_stream import validate_mark_stream
from nn_meta.spx0 import config as sc
from nn_meta.spx0 import intraday
from nn_meta.spx0.build_dataset import (build_session_rows, prepare_signals,
                                        proxy_context_features, resample_5m)
from nn_meta.spx0.contracts import parse_occ, parse_occ_frame, pick_wing, strike_step
from nn_meta.spx0.costs import net_return_vertical, vertical_margin

DAY = pd.Timestamp("2025-06-10")
OPEN = pd.Timestamp("2025-06-10 13:30")
T_IN, T_OUT = pd.Timestamp("2025-06-10 14:00"), pd.Timestamp("2025-06-10 15:00")
VERT_1 = (sc.TradeVariant(-1001, True, float("inf"), wing_strikes=1),)


def _proxy(end=592.0):
    idx = pd.date_range(OPEN, periods=390, freq="1min")
    close = np.linspace(590.0, end, 390)
    return pd.DataFrame({"Open": close, "High": close + 0.1, "Low": close - 0.1,
                         "Close": close, "Volume": 1000.0}, index=idx)


def _options(minutes=390, put_slope=0.01):
    """Puts gain ``put_slope`` premium per strike point above 5880, so an
    adjacent-strike put spread carries a real credit."""
    rows = []
    ts = pd.date_range(OPEN, periods=minutes, freq="1min")
    for k in (5880, 5890, 5900, 5910, 5920, 5930):
        for right in "CP":
            base = (np.linspace(1.0, 0.5, minutes) if right == "C"
                    else np.linspace(0.8, 0.4, minutes) + (k - 5880) * put_slope)
            for t, p in zip(ts, base):
                rows.append({"occ": f"SPXW250610{right}{k*1000:08d}", "timestamp": t,
                             "Open": p, "High": p + 0.02, "Low": p - 0.02,
                             "Close": p, "Volume": 20})
    df = pd.DataFrame(rows)
    return pd.concat([df, parse_occ_frame(df["occ"])], axis=1)


def _prepared(bars5, entry_at, exit_at):
    idx = bars5.index
    z = pd.Series(False, index=idx)
    entries = z.copy(); entries.loc[entry_at] = True
    exits = z.copy(); exits.loc[exit_at] = True
    from nn_meta.spx0.build_dataset import TECHNICALS
    feats = pd.DataFrame(0.0, index=idx, columns=TECHNICALS)
    return {"rsi": ((entries, exits, z.copy(), z.copy()), feats)}


def _run(entry_at, exit_at, *, px=None, options=None, **kw):
    px = _proxy() if px is None else px
    b5 = resample_5m(px)
    rows, marks = build_session_rows(
        DAY, "SPX", proxy_1m=px, bars_5m=b5,
        options=_options() if options is None else options,
        prepared=_prepared(b5, entry_at, exit_at),
        ctx_1m=proxy_context_features(px), **kw)
    return pd.DataFrame(rows), pd.DataFrame(marks)


def test_strike_step_is_measured_not_assumed():
    z = _options(minutes=5)
    assert strike_step(z, index="SPX", right="P", near=5905.0) == 10.0


def test_wing_sits_otm_of_the_sold_put():
    z = _options(minutes=5)
    short_leg = parse_occ("SPXW250610P05900000")
    w = pick_wing(z, short_leg=short_leg, mapped_spot=5905.0, wing_strikes=1,
                  at=OPEN + pd.Timedelta(minutes=4))
    assert w is not None and w.right == "P" and w.strike == 5890.0


def test_vertical_carries_credit_wing_and_true_margin():
    ds, marks = _run(T_IN, T_OUT, variants=VERT_1)
    r = ds.iloc[0]
    assert r["executed"] and r["dte"] == -1001 and r["n_fills"] == 1 and r["n_legs"] == 2
    assert r["right"] == "P" and r["wing_strike"] == r["strike"] - 10.0
    width = r["strike"] - r["wing_strike"]
    assert 0 < r["entry_premium"] < width                 # a real credit
    assert r["margin"] == pytest.approx(width - r["entry_premium"])
    assert r["spx0_wing_width_frac"] == pytest.approx(width / (r["strike"] / (1 + r["moneyness"])), rel=1e-6)
    assert r["spx0_stop_frac"] == 0.0                     # no stop; wing is the bound
    vm = validate_mark_stream(marks).sort_values("mark_ts")
    assert vm["gross_return"].iloc[0] == 0.0
    assert np.isclose(vm["gross_return"].iloc[-1], r["gross_return"])


def test_vertical_settlement_loss_is_bounded_at_minus_one_margin():
    """Round-2's failure mode: premium explodes against the seller. A vertical
    that settles fully in the money loses EXACTLY its margin — never more."""
    px = _proxy(end=575.0)                    # mapped floor ≈ 5755: deep ITM puts
    z = _options(minutes=90)                  # prints stop at 15:00 → settlement
    ds, _ = _run(T_IN, pd.Timestamp("2025-06-10 19:55"), px=px, options=z,
                 variants=VERT_1)
    r = ds.iloc[0]
    assert r["executed"] and r["exit_reason"] == "settled_intrinsic"
    assert r["gross_return"] == pytest.approx(-1.0)       # (credit − width) / margin
    assert r["net_return"] >= -1.1                        # entry costs only on top


def test_vertical_costs_price_the_package_not_the_legs():
    from nn_meta.spx0.costs import BASE, package_cost_points
    m = vertical_margin(10.0, 0.5)
    settled = net_return_vertical(0.5, 0.0, m, settled=True)
    market = net_return_vertical(0.5, 0.0, m, settled=False)
    assert market < settled < 0.5 / m                     # costs bite, twice for market
    # one net-premium crossing + both contracts' fees — NOT each leg's
    # full-premium half-spread (an ATM spread would be overcharged ~10x)
    assert package_cost_points(0.5) == pytest.approx(
        BASE.half_spread(0.5) + 2 * BASE.fee_per_contract / 100.0)
    with pytest.raises(ValueError):
        vertical_margin(10.0, 10.0)                       # credit must be < width
    with pytest.raises(ValueError):
        vertical_margin(0.0, 0.5)


def test_intraday_seats_produce_causal_signals():
    px = _proxy()
    b5 = resample_5m(px)
    for name in sc.INTRADAY_STRATEGIES:
        e, x, se, sx = intraday.intraday_signals(name, b5)
        for s in (e, x, se, sx):
            assert s.dtype == bool and s.index.equals(b5.index)


def test_orb_fires_only_after_the_range_completes():
    idx = pd.date_range(OPEN, periods=390, freq="1min")
    close = np.concatenate([np.full(60, 590.0), np.full(330, 600.0)])  # break at 14:30
    px = pd.DataFrame({"Open": close, "High": close + 0.1, "Low": close - 0.1,
                       "Close": close, "Volume": 1000.0}, index=idx)
    e, _, se, _ = intraday.intraday_signals("orb_30", resample_5m(px))
    assert e.any() and not se.any()
    assert e.idxmax() > OPEN + pd.Timedelta(minutes=30)   # never inside the range


def test_gap_fill_fades_the_gap_on_the_first_bar():
    d1 = pd.date_range(OPEN, periods=390, freq="1min")
    d2 = pd.date_range(OPEN + pd.Timedelta(days=1), periods=390, freq="1min")
    c1 = np.full(390, 590.0)
    c2 = np.full(390, 594.0)                              # ~68bp gap up
    px = pd.DataFrame({"Open": np.r_[c1, c2], "High": np.r_[c1, c2] + 0.1,
                       "Low": np.r_[c1, c2] - 0.1, "Close": np.r_[c1, c2],
                       "Volume": 1000.0}, index=d1.append(d2))
    e, _, se, _ = intraday.intraday_signals("gap_fill_50", resample_5m(px))
    assert not e.any() and se.sum() == 1                  # short the up-gap, once
    assert se.idxmax().normalize() == d2[0].normalize()


def test_prepare_signals_includes_the_intraday_seats():
    b5 = resample_5m(_proxy())
    prepared = prepare_signals(b5, {"strategies": {}})    # no frozen v31 entries
    assert set(prepared) == set(sc.INTRADAY_STRATEGIES)


def test_round4_mapping_pairs_seats_with_structures(tmp_path):
    """Round 4: a variants MAPPING gives each seat only its own variants —
    vertical seats emit no long rows, gap_fill emits no verticals, unmapped
    seats emit nothing."""
    px = _proxy()
    b5 = resample_5m(px)
    mapping = {"rsi": sc.VERTICAL_VARIANTS, "macd": ()}
    rows, _ = build_session_rows(
        DAY, "SPX", proxy_1m=px, bars_5m=b5, options=_options(),
        prepared=_prepared(b5, T_IN, T_OUT),      # provides only an rsi signal
        ctx_1m=proxy_context_features(px), variants=mapping)
    ds = pd.DataFrame(rows)
    assert set(ds["strategy"]) == {"rsi"}
    assert set(ds["dte"]) == {v.code for v in sc.VERTICAL_VARIANTS}
    assert (ds["dte"] < 0).all()                  # no long rows for a vertical seat


def test_round4_frozen_spec_is_seat_aware():
    from nn_meta.spx0.evaluate import synthetic_spec
    ds = pd.DataFrame({
        "symbol": ["SPX-C"] * 4 + ["SPX-C"] * 2,
        "strategy": ["ma"] * 4 + ["gap_fill_50"] * 2,
        "dte": [-1001, -1002, -1004, -1001, 0, 30],
    })
    spec = synthetic_spec(ds)
    strats = spec["symbols"]["SPX-C"]["strategies"]
    assert strats["ma"]["dte"] == -1002           # ROUND4_FROZEN middle width
    assert strats["gap_fill_50"]["dte"] == 0      # long default
    # a seat whose frozen code is absent falls back to a code that EXISTS
    ds2 = ds[ds["dte"] != -1002]
    assert synthetic_spec(ds2)["symbols"]["SPX-C"]["strategies"]["ma"]["dte"] == -1004


def test_round4_config_only_maps_supported_pairs():
    assert set(sc.ROUND4_SEAT_VARIANTS) == {"ma", "orb_15", "rsi", "gap_fill_50"}
    for seat, vs in sc.ROUND4_SEAT_VARIANTS.items():
        short = all(v.wing_strikes > 0 for v in vs)
        assert short if seat != "gap_fill_50" else all(not v.short for v in vs)
