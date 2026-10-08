"""V8.2 vol inputs: Black-76 inversion, parity forward, IV30 interpolation, PIT HAR."""
import numpy as np
import pandas as pd

from nn_meta import v8_vol as vv


def test_implied_vol_roundtrip_and_bounds():
    for s in (0.1, 0.4, 1.2):
        for c in (True, False):
            p = vv.black76(100, 95, 0.1, s, c)
            assert abs(vv.implied_vol(p, 100, 95, 0.1, c) - s) < 1e-6
    assert np.isnan(vv.implied_vol(1.0, 100, 95, 0.1, True))   # below intrinsic


def test_atm_iv_from_synthetic_chain():
    S, sig, dte = 100.0, 0.25, 30
    rows = []
    for K in np.arange(90, 111, 1.0):
        for cp in "CP":
            px = float(vv.black76(S, K, dte / 365, sig, cp == "C"))
            rows.append(("2024-01-02", "X", "2024-02-01", cp, K, px, 10))
    ch = pd.DataFrame(rows, columns=["date", "ticker", "expiry", "cp", "strike", "close", "volume"])
    spot = pd.DataFrame({"date": ["2024-01-02"], "ticker": ["X"], "S": [S]})
    e = vv.atm_iv_by_expiry(ch, spot)
    assert abs(e["F"].iloc[0] - S) < 1e-6 and abs(e["iv_atm"].iloc[0] - sig) < 1e-4
    out = vv.iv30(e)
    assert out["iv30_method"].iloc[0] == "exact" and abs(out["iv30"].iloc[0] - sig) < 1e-4


def test_iv30_total_variance_interpolation():
    e = pd.DataFrame({"ticker": "X", "date": "d", "expiry": ["a", "b"], "dte": [20, 40],
                      "F": 100.0, "iv_atm": [0.20, 0.30], "sides": 2})
    w = 0.2 ** 2 * 20 + (0.3 ** 2 * 40 - 0.2 ** 2 * 20) * 0.5
    assert abs(vv.iv30(e)["iv30"].iloc[0] - np.sqrt(w / 30)) < 1e-12


def test_har_is_point_in_time():
    rng = np.random.default_rng(0)
    days = [d.date().isoformat() for d in pd.bdate_range("2021-01-04", periods=600)]
    rv = pd.DataFrame({"ticker": "X", "date": days, "rv": rng.gamma(2, 1e-4, 600)})
    a = vv.har_direct(rv).set_index("date")["har_vol"]
    rv2 = rv.copy(); rv2.loc[450:, "rv"] *= 50          # change the future only
    b = vv.har_direct(rv2).set_index("date")["har_vol"]
    assert np.allclose(a.iloc[:450].fillna(-1), b.iloc[:450].fillna(-1))
