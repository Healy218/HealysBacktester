import importlib.util
import sys

import numpy as np
import pandas as pd

spec = importlib.util.spec_from_file_location("run_v9_ove3", "scripts/run_v9_ove3.py")
o = importlib.util.module_from_spec(spec)
sys.modules["run_v9_ove3"] = o
spec.loader.exec_module(o)

DAYS = [f"2024-01-{d:02d}" for d in range(2, 31)]


def test_abnormal_uses_prior_days_only():
    f = pd.DataFrame({"ticker": "X", "date": DAYS[:25],
                      "x": [100.0 + (i % 3) for i in range(24)] + [10000.0]})
    z = o.abnormal(f, "x")
    assert np.isnan(z.iloc[14]) and np.isfinite(z.iloc[15])
    assert z.iloc[24] > 10                      # today's spike is not in its own baseline


def test_stock_trades_enter_next_open_and_block_reentry():
    b = pd.DataFrame({"open": 10.0, "close": 11.0, "adj_open": 10.0, "adj_close": 11.0}, index=DAYS)
    sig = pd.DataFrame({"ticker": ["X", "X", "X"], "date": [DAYS[0], DAYS[2], DAYS[6]]})
    rows = o.stock_trades(sig, "A1", {"X": b}, DAYS)
    assert [r["entry_day"] for r in rows] == [DAYS[1], DAYS[7]]     # DAYS[2] overlaps
    assert rows[0]["exit_day"] == DAYS[5]
    r = rows[0]["ret_1.0"]
    assert 0.09 < r < 0.1                       # 10% gross less spread and fees


def test_ab_signal_filters():
    n = 25
    f = pd.DataFrame({"ticker": "X", "date": DAYS[:n], "S": 100.0,
                      "st_otm_call_prem": [1000.0 + 10 * (i % 2) for i in range(n - 1)] + [1e6],
                      "st_otm_put_prem": 1000.0, "block_call_vol": 10.0, "st_otm_call_prem_at_high": 0.0,
                      "call_trades": 100, "put_trades": 100, "finra_short_ratio": 0.5,
                      "days_since_earnings": 30.0, "days_to_earnings": 30.0})
    adm = pd.DataFrame({"ticker": "X", "date": DAYS[:n], "admitted": True})
    s = o.ab_signals(f, adm, set())
    assert s["A1"].iloc[-1] and not s["A1"].iloc[:-1].any()
    f.loc[n - 1, "days_to_earnings"] = 3.0      # earnings within 5 days: filtered
    assert not o.ab_signals(f, adm, set())["A1"].iloc[-1]
    assert not o.ab_signals(f, adm, {"X"})["A1"].any()
