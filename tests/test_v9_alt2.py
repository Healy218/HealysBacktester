import importlib.util
import sys

import pandas as pd

spec = importlib.util.spec_from_file_location("run_v9_alt2", "scripts/run_v9_alt2.py")
m = importlib.util.module_from_spec(spec)
sys.modules["run_v9_alt2"] = m
spec.loader.exec_module(m)


def test_stock_ret_long_and_short_are_mirror_images_before_costs():
    b = pd.DataFrame({"close": [100.0, 90.0], "adj_close": [100.0, 90.0]}, index=["2024-01-02", "2024-01-03"])
    e = pd.Series({"ticker": "ZZZZ", "entry_day": "2024-01-02", "reaction_day": "2024-01-03"})
    long_, short = m.stock_ret(e, 1, {"ZZZZ": b}, 0.0), m.stock_ret(e, -1, {"ZZZZ": b}, 0.0)
    assert abs(long_ - (-0.1 * (1 - 0) - 0.9 * 0.3e-4)) < 1e-6
    assert abs(short - (100 * (1 - 0.3e-4) - 90) / (100 * (1 - 0.3e-4))) < 1e-12
    assert m.stock_ret(e, -1, {"ZZZZ": b}, 1.0) < short     # costs reduce the short's return
