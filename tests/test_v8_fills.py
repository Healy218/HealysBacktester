"""V8.0-fills: stock and option fill hand cases."""
import numpy as np

from nn_meta import v8_fills as vf

TABLE = {"cells": {(p, s, y): 5.0 for p in range(6) for s in range(13) for y in (2021, 2022)},
         "name_factor": {"CHEAP": 0.5}, "years": [2021, 2022]}


def test_buckets_and_slots():
    assert list(vf.price_bucket([4.99, 5.0, 99.9, 100.0, 1e4])) == [0, 1, 4, 5, 5]
    assert list(vf.snap_index([570, 585, 600, 615, 955])) == [0, 0, 0, 1, 12]


def test_stock_buy_sell_hand_case():
    f = vf.stock_fill([1, -1], [100.0, 100.0], [100, 100], ["X", "X"], [600, 600],
                      [2022, 2022], table=TABLE)
    # half spread 5 bp + 1 bp slippage = 6 bp each side
    assert np.allclose(f["fill_price"], [100.06, 99.94])
    assert np.isclose(f["cash"][0], -10006.0)
    sell_value = 99.94 * 100
    fee = sell_value * 0.3 / 1e4 + 100 * 0.000166
    assert np.isclose(f["fee"][1], fee) and np.isclose(f["cash"][1], sell_value - fee)


def test_stress_multiplier_name_factor_and_year_clamp():
    f = vf.stock_fill([1], [50.0], [10], ["CHEAP"], [700], [2030], cost_mult=1.5, table=TABLE)
    # 0.5 x 5 bp + 1 bp = 3.5 bp, x1.5 = 5.25 bp; 2030 clamps to 2022
    assert np.isclose(f["fill_price"][0], 50 * (1 + 5.25e-4))


def test_taf_cap_on_large_sells():
    f = vf.stock_fill([-1], [10.0], [100000], ["X"], [700], [2022], table=TABLE)
    assert np.isclose(f["fee"][0] - f["fill_price"][0] * 100000 * 0.3e-4, vf.TAF_CAP)


def test_option_fill_k():
    f = vf.option_fill([1, -1], [2.0, 2.0], [0.10, 0.10], [3, 3], k=0.5)
    assert np.allclose(f["fill_price"], [2.05, 1.95])
    assert np.allclose(f["cash"], [-2.05 * 300 - 0.15, 1.95 * 300 - 0.15])
