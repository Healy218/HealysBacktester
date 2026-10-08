"""V8 H1 calls: contract choice, exit pricing (incl. splits) and the book."""
import numpy as np
import pandas as pd

from nn_meta import v8_h1_calls as hc
from nn_meta import v8_vol as vv


def _chain(day, expiry, S=100.0, sig=0.3):
    T = (pd.Timestamp(expiry) - pd.Timestamp(day)).days / 365
    rows = []
    for K in np.arange(80, 121, 5.0):
        for cp in "CP":
            rows.append((expiry, cp, K, float(vv.black76(S, K, T, sig, cp == "C")), 10))
    return pd.DataFrame(rows, columns=["expiry", "cp", "strike", "close", "volume"])


def test_pick_call_targets_45_dte_and_060_delta():
    day = "2024-01-02"
    ch = pd.concat([_chain(day, "2024-02-09"), _chain(day, "2024-02-16"), _chain(day, "2024-03-28")])
    p = hc.pick_call(ch, day, 100.0)
    assert p["expiry"] == "2024-02-16" and p["dte"] == 45
    assert p["strike"] == 100.0 and abs(p["delta"] - 0.6) < 0.1   # 100 (0.52) beats 95 (0.70)


def test_exit_price_fallback_split_and_intrinsic():
    days = [f"d{i:02d}" for i in range(30)]
    one = lambda d: 1.0
    # traded on day 20
    assert hc.exit_price({("d20", 95.0): 7.0}, days, 0, 95.0, "d99", {}, one) == ("d20", 7.0, "traded")
    # no trade until day 22
    assert hc.exit_price({("d22", 95.0): 6.0}, days, 0, 95.0, "d99", {}, one)[2] == "traded+2"
    # 10:1 split: contract becomes strike 9.5, value x10
    ten = lambda d: 10.0
    assert hc.exit_price({("d20", 9.5): 0.7}, days, 0, 95.0, "d99", {}, ten) == ("d20", 7.0, "traded")
    # never trades: intrinsic from raw close in original units
    raw = {d: 10.2 for d in days}
    assert hc.exit_price({}, days, 0, 95.0, "d99", raw, ten) == ("d20", 7.0, "intrinsic")


def test_simulate_sizes_premium_and_books_at_exit():
    days = ["a", "b", "c"]
    tr = pd.DataFrame([{"ticker": "X", "entry_day": "a", "exit_day": "c", "entry_price": 2.0,
                        "exit_value": 3.0, "prio": 1.0}])
    eq, taken = hc.simulate(tr, days, 0.0)
    ret = (3.0 - 0.0005) / (2.0 + 0.0005) - 1
    assert np.isclose(taken["ret"].iloc[0], ret)
    assert np.isclose(eq[1], 1.0) and np.isclose(eq[2], 1.0 + 0.05 * ret)
