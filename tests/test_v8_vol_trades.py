"""V8.2 trade construction and simulation hand cases."""
import numpy as np
import pandas as pd

from nn_meta import v8_vol_trades as vt

NO_COST = ({}, {i: 0.0 for i in range(6)})       # zero half-spread everywhere


def _chain(prices):
    rows = [("2024-01-02", "X", "2024-02-01", cp, K, p, 5) for (cp, K), p in prices.items()]
    return pd.DataFrame(rows, columns=["date", "ticker", "expiry", "cp", "strike", "close", "volume"])


def test_iron_butterfly_hand_case():
    # spot 100, iv30 such that EM = 100 * 0.2 * sqrt(30/365) ~ 5.73 -> wings at 106 / 94
    prices = {("C", 100.0): 3.0, ("P", 100.0): 3.0, ("C", 106.0): 1.0, ("P", 94.0): 1.0,
              ("C", 99.0): 3.6, ("P", 99.0): 2.6, ("C", 101.0): 2.5, ("P", 101.0): 3.5}
    spot = pd.DataFrame({"ticker": ["X"], "date": ["2024-01-02"], "S": [100.0], "iv30": [0.2]})
    settle = pd.DataFrame({"ticker": "X", "date": ["2024-01-02", "2024-02-01"], "close": [100.0, 103.0]})
    c = vt.build_candidates(_chain(prices), spot, settle, NO_COST)
    ib = c[c["structure"] == "ib_w1.0"].iloc[0]
    assert ib["strikes"] == [100.0, 100.0, 106.0, 94.0] and ib["settle_date"] == "2024-02-01"
    credit = 3 + 3 - 1 - 1 - 0.05 * 4 / 100          # 3.998
    pnl = credit - 3.0                                # short call pays 3 at S_T = 103
    maxloss = 6.0 - credit
    assert np.isclose(ib["R_1.0"], pnl / maxloss)
    st = c[c["structure"] == "straddle"].iloc[0]
    debit = 6.0 + 0.05 * 2 / 100
    assert np.isclose(st["R_1.0"], (3.0 - debit) / debit)


def test_min_price_and_holdout_settlement_rules():
    prices = {("C", 100.0): 3.0, ("P", 100.0): 3.0, ("C", 106.0): 0.40, ("P", 94.0): 1.0}
    spot = pd.DataFrame({"ticker": ["X"], "date": ["2024-01-02"], "S": [100.0], "iv30": [0.2]})
    settle = pd.DataFrame({"ticker": "X", "date": ["2024-01-02", "2024-02-01"], "close": [100.0, 100.0]})
    c = vt.build_candidates(_chain(prices), spot, settle, NO_COST)
    assert "ib_w1.0" not in set(c["structure"])      # a $0.40 wing fails the $0.50 floor


def test_simulate_one_open_trade_and_risk_fraction():
    days = np.array(["d1", "d2", "d3", "d4"])
    cand = {("X", "d1"): (0.5, "d3"), ("X", "d2"): (0.5, "d4")}
    sig = {("X", "d1"): True, ("X", "d2"): True}
    eq, n = vt.simulate(days, cand, sig, {d: {"X"} for d in days})
    assert list(n) == [1, 0, 0, 0]                   # d2 blocked while d1's trade is open
    assert np.isclose(eq[2], 1.0 + 0.02 * 0.5)


def test_settlement_undoes_a_split_inside_the_trade():
    prices = {("C", 100.0): 3.0, ("P", 100.0): 3.0, ("C", 106.0): 1.0, ("P", 94.0): 1.0}
    spot = pd.DataFrame({"ticker": ["X"], "date": ["2024-01-02"], "S": [100.0], "iv30": [0.2]})
    # 10:1 split: raw settles at 10.3, adjusted stays continuous (103)
    settle = pd.DataFrame({"ticker": "X", "date": ["2024-01-02", "2024-02-01"],
                           "close": [100.0, 10.3], "adj_close": [100.0, 103.0]})
    st = vt.build_candidates(_chain(prices), spot, settle, NO_COST)
    st = st[st["structure"] == "straddle"].iloc[0]
    assert np.isclose(st["S_T"], 103.0)
