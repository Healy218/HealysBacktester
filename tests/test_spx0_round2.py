"""spx0 second design round: sell-premium variants (margin-as-size, loss cap
via a premium stop above entry), the fold-selectable variant grid riding the
``dte`` column, and the v4 gate's ex-top3 baseline bar. No archive access."""
import numpy as np
import pandas as pd
import pytest

from nn_meta.mark_stream import stable_trade_id, validate_mark_stream
from nn_meta.spx0 import config as sc
from nn_meta.spx0.build_dataset import (build_session_rows, proxy_context_features,
                                        resample_5m)
from nn_meta.spx0.contracts import parse_occ_frame
from nn_meta.spx0.costs import (BASE, gross_return_short, net_return_short,
                                short_margin)
from nn_meta.v4_evaluate import _passes_gate

DAY = pd.Timestamp("2025-06-10")
OPEN = pd.Timestamp("2025-06-10 13:30")


def _proxy():
    idx = pd.date_range(OPEN, periods=390, freq="1min")
    close = 590 + np.linspace(0, 2, 390)
    return pd.DataFrame({"Open": close, "High": close + 0.1, "Low": close - 0.1,
                         "Close": close, "Volume": 1000.0}, index=idx)


def _options(put_path=None):
    rows = []
    ts = pd.date_range(OPEN, periods=390, freq="1min")
    for k in (5880, 5890, 5900, 5910, 5920, 5930):
        for right in "CP":
            occ = f"SPXW250610{right}{k*1000:08d}"
            prem = (np.linspace(1.0, 0.5, 390) if right == "C"
                    else (put_path if put_path is not None
                          else np.linspace(0.8, 0.4, 390)))
            for t, p in zip(ts, prem):
                rows.append({"occ": occ, "timestamp": t, "Open": p, "High": p + 0.02,
                             "Low": p - 0.02, "Close": p, "Volume": 20})
    df = pd.DataFrame(rows)
    df = pd.concat([df, parse_occ_frame(df["occ"])], axis=1)
    return df


def _prepared(bars5, entry_at, exit_at):
    idx = bars5.index
    z = pd.Series(False, index=idx)
    entries = z.copy(); entries.loc[entry_at] = True
    exits = z.copy(); exits.loc[exit_at] = True
    from nn_meta.spx0.build_dataset import TECHNICALS
    feats = pd.DataFrame(0.0, index=idx, columns=TECHNICALS)
    return {"rsi": ((entries, exits, z.copy(), z.copy()), feats)}


def _run(entry_at, exit_at, *, put_path=None, **kw):
    px = _proxy()
    b5 = resample_5m(px)
    rows, marks = build_session_rows(
        DAY, "SPX", proxy_1m=px, bars_5m=b5, options=_options(put_path),
        prepared=_prepared(b5, entry_at, exit_at),
        ctx_1m=proxy_context_features(px), **kw)
    return pd.DataFrame(rows), pd.DataFrame(marks)


T_IN, T_OUT = pd.Timestamp("2025-06-10 14:00"), pd.Timestamp("2025-06-10 15:00")


def test_variant_grid_shares_the_dedupe_key_and_splits_the_trade_id():
    ds, marks = _run(T_IN, T_OUT, variants=sc.ROUND2_VARIANTS)
    assert len(ds) == len(sc.ROUND2_VARIANTS)
    # one proposal: every variant shares (symbol, strategy, trade_idx)…
    assert ds[["symbol", "strategy", "trade_idx"]].drop_duplicates().shape[0] == 1
    # …and differs in the dte-slot variant code, so trade_ids stay unique
    assert sorted(ds["dte"]) == sorted(v.code for v in sc.ROUND2_VARIANTS)
    tid = stable_trade_id(ds[ds["executed"]])
    assert not tid.duplicated().any()
    assert set(validate_mark_stream(marks)["trade_id"].astype(str)) == set(tid)
    # the new variant-axis features are on every row
    assert set(ds["spx0_short"]) == {0.0, 1.0}
    assert (ds["spx0_stop_frac"] > 0).all()


def test_variant_zero_reproduces_the_round1_long_build():
    legacy, legacy_marks = _run(T_IN, T_OUT)                       # round-1 path
    ds, marks = _run(T_IN, T_OUT, variants=sc.ROUND2_VARIANTS)
    v0 = ds[ds["dte"] == 0].reset_index(drop=True)
    assert len(legacy) == len(v0) == 1
    for col in legacy.columns:
        a, b = legacy.iloc[0][col], v0.iloc[0][col]
        assert (a == b) or (pd.isna(a) and pd.isna(b)), col
    tid0 = stable_trade_id(v0).iloc[0]
    m0 = marks[marks["trade_id"] == tid0].reset_index(drop=True)
    pd.testing.assert_frame_equal(
        legacy_marks.reset_index(drop=True), m0, check_dtype=False)


def test_short_sells_the_opposite_right_at_the_worst_print():
    ds, _ = _run(T_IN, T_OUT, variants=(sc.TradeVariant(-200, True, 2.0),))
    r = ds.iloc[0]
    # bullish signal (symbol keeps the signal's right) sells the PUT
    assert r["symbol"] == "SPX-C" and r["right"] == "P" and r["dte"] == -200
    assert r["executed"] and r["dir_short"] == 0.0 and r["spx0_short"] == 1.0
    # sell fills at the bar LOW (Close − 0.02 in the fixture)
    fill_bar_prem = np.interp(31, [0, 389], [0.8, 0.4])   # 14:01, put path
    assert r["entry_premium"] == pytest.approx(fill_bar_prem - 0.02, abs=1e-9)
    assert r["margin"] == pytest.approx(short_margin(r["entry_premium"], 2.0))
    # premium decays into the signal exit: the seller wins, buying back at High
    assert r["exit_reason"] == "signal" and r["gross_return"] > 0
    assert r["net_return"] < r["gross_return"]


def test_short_stop_caps_the_loss_near_minus_one_margin():
    # put premium quadruples against the seller: the 2× stop must fire
    rising = np.linspace(0.4, 1.6, 390)
    ds, marks = _run(T_IN, pd.Timestamp("2025-06-10 19:55"), put_path=rising,
                     variants=(sc.TradeVariant(-200, True, 2.0),))
    r = ds.iloc[0]
    assert r["executed"] and r["exit_reason"] == "stop_target"
    assert r["fill_exit_ts"] < pd.Timestamp("2025-06-10 19:55")
    # loss lands near −1× margin (the buyback High and the 1m grid add slip)
    assert -1.3 < r["gross_return"] < -0.9
    # marks are in margin units and end exactly at the row's gross_return
    vm = validate_mark_stream(marks).sort_values("mark_ts")
    assert vm["gross_return"].iloc[0] == 0.0
    assert np.isclose(vm["gross_return"].iloc[-1], r["gross_return"])


def test_short_settlement_pays_intrinsic_with_no_exit_crossing():
    n = net_return_short(0.50, 0.0, short_margin(0.50, 2.0), BASE, settled=True)
    g = gross_return_short(0.50, 0.0, short_margin(0.50, 2.0))
    # worthless expiry: full premium kept, entry-side costs only
    assert g == pytest.approx(1.0)
    assert n < g
    assert n == pytest.approx((0.50 - BASE.side_cost_points(0.50)) / 0.50)
    # a market buyback at the same price pays the exit side too
    assert net_return_short(0.50, 0.0, 0.50, BASE, settled=False) < n


def test_short_costs_reject_bad_inputs():
    with pytest.raises(ValueError):
        short_margin(0.5, 1.0)            # stop must exceed 1
    with pytest.raises(ValueError):
        short_margin(0.0, 2.0)
    with pytest.raises(ValueError):
        net_return_short(0.5, 0.1, 0.0)


def test_gate_bar_is_the_baseline_ex_top3():
    metrics = {"n_kept": 20, "total_return": 0.50, "max_drawdown": 0.10}
    outlier_carried = {"n_kept": 50, "total_return": 18.54, "total_ex_top3": 0.10}
    assert _passes_gate(metrics, outlier_carried)
    # a candidate below the ex-top3 bar still fails
    assert not _passes_gate({**metrics, "total_return": 0.05}, outlier_carried)
    # no ex-top3 available: fall back to the raw return
    assert not _passes_gate(
        metrics, {"n_kept": 50, "total_return": 18.54, "total_ex_top3": None})
    assert _passes_gate(
        metrics, {"n_kept": 50, "total_return": 0.20, "total_ex_top3": None})


def test_decision_features_blind_to_the_forming_1m_bar():
    """Bars are start-stamped: the 1m bar stamped t is still forming at the
    5m signal close t. A price spike inside that bar must not reach any
    decision-side field (review 2026-08-24 lookahead finding)."""
    from nn_meta.spx0.build_dataset import build_session_rows
    spike_t = pd.Timestamp("2025-06-10 14:00")

    def _build(spike):
        px = _proxy()
        if spike:
            px.loc[spike_t, ["Open", "High", "Low", "Close"]] = 700.0
        b5 = resample_5m(px)
        rows, _ = build_session_rows(
            DAY, "SPX", proxy_1m=px, bars_5m=b5, options=_options(),
            prepared=_prepared(b5, spike_t, pd.Timestamp("2025-06-10 15:00")),
            ctx_1m=proxy_context_features(px), variants=sc.ROUND2_VARIANTS)
        return pd.DataFrame(rows)

    clean, spiked = _build(False), _build(True)
    decision_cols = ["strike", "moneyness", "spx0_rv_30", "spx0_rv_60",
                     "spx0_prem_spot_last", "spx0_prem_rich", "spx0_depth_signal"]
    for col in decision_cols:
        a, b = clean[col].tolist(), spiked[col].tolist()
        assert all((x == y) or (pd.isna(x) and pd.isna(y)) for x, y in zip(a, b)), col


def test_gate_small_baseline_falls_back_to_raw_return():
    """total_ex_top3 is a 0.0 SENTINEL for baselines entering <= 3 trades —
    the bar must fall back to the raw return, not become 0.0."""
    metrics = {"n_kept": 20, "total_return": 0.30, "max_drawdown": 0.10}
    tiny_baseline = {"n_kept": 3, "total_return": 0.50, "total_ex_top3": 0.0}
    assert not _passes_gate(metrics, tiny_baseline)
    assert _passes_gate({**metrics, "total_return": 0.60}, tiny_baseline)


def test_ev_portfolio_stops_entering_on_a_busted_book():
    """Per-margin returns below -1 can take equity negative; a dead book must
    not size new positions off negative equity (flipping losses into gains)."""
    from nn_meta.ev_sizing import ev_weighted_portfolio
    t0, t1, t2 = (pd.Timestamp("2025-06-10 14:00"), pd.Timestamp("2025-06-10 14:30"),
                  pd.Timestamp("2025-06-10 15:00"))
    cands = pd.DataFrame({
        "symbol": ["A", "B", "C"],
        "entry_ts": [t0, t0, t2], "exit_ts": [t1, t1, t2 + pd.Timedelta("30min")],
        "net_return": [-8.0, -8.0, 1.0], "pred_ev": [0.5, 0.5, 0.5],
    })
    total, max_dd, entered = ev_weighted_portfolio(cands, 2, 0.6)
    assert len(entered) == 2                     # the post-bust candidate is skipped
    assert np.isfinite(total) and total < -1.0   # honest busted-book report
    assert max_dd > 1.0


def test_magnitude_head_absent_rather_than_crashing_without_executed_rows():
    from nn_meta.v4_evaluate import fit_gbt_magnitude
    rows = pd.DataFrame({"executed": [False, False], "net_return": [np.nan, np.nan],
                         "f1": [0.1, 0.2]})
    assert fit_gbt_magnitude(rows, rows, features=["f1"], n_estimators=10) is None
