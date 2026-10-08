import importlib.util
import sys

import numpy as np
import pandas as pd

spec = importlib.util.spec_from_file_location("run_v9_oee_h4", "scripts/run_v9_oee_h4.py")
h4 = importlib.util.module_from_spec(spec)
sys.modules["run_v9_oee_h4"] = h4
spec.loader.exec_module(h4)


def test_pick_requires_otm_side_and_tolerance():
    on_e = pd.DataFrame({"cp": ["C", "C", "P", "P"], "strike": [105.0, 112.0, 95.0, 80.0],
                         "close": [1.0, 0.3, 0.9, 0.05]})
    assert h4.pick(on_e, "C", 100.0, 110.0) == (112.0, 0.3)       # 1.8% from target
    assert h4.pick(on_e, "P", 100.0, 90.0) is None                 # nearest 95 is 5.6% off
    assert h4.pick(on_e, "C", 100.0, 104.0) == (105.0, 1.0)       # only strikes above spot
    assert h4.pick(on_e[on_e.cp == "P"], "C", 100.0, 110.0) is None


def _setup():
    a = pd.DataFrame({"ticker": ["X"] * 6, "S_entry": [100.0] * 6, "S_reaction": [100.0] * 6,
                      "entry_day": [f"2023-0{i}-10" for i in range(1, 7)],
                      "reaction_day": [f"2023-0{i}-11" for i in range(1, 7)],
                      "front_expiry": [f"2023-0{i}-13" for i in range(1, 7)], "front_dte": 3,
                      "realized_move": [0.25, -0.25, 0.25, -0.25, 0.0, 0.0], "session": "after_close"})
    a.index.name = "key"
    rows = []
    for k in a.index:
        rows += [{"key": k, "leg": "p10_C", "cp": "C", "strike": 110.0, "entry": 0.4, "exit": 0.1, "exit_how": "traded"},
                 {"key": k, "leg": "p10_P", "cp": "P", "strike": 90.0, "entry": 3.0, "exit": 1.0, "exit_how": "traded"}]
    return a, pd.DataFrame(rows)


def test_h4g_uses_prior_moves_only():
    a, legs = _setup()
    g = h4.h4g_cheap(a, legs)
    assert not g.iloc[:4].any()                       # < 4 prior events
    # prior moves +/-25% -> payoff ~ 18.4 or 12.1; cost 3.4 < median -> cheap
    assert g.iloc[4] and g.iloc[5]


def test_cheap_leg_qualifies_each_leg_on_its_own():
    a, legs = _setup()
    feats = pd.DataFrame({"move_ratio": np.nan, "tercile_h1a_score": np.nan}, index=a.index)
    sm = type("SM", (), {"half_spread": lambda self, p, d, o: 0.0})()
    tr = h4.build_trades(a, legs, feats, pd.Series(False, index=a.index), sm)
    f05 = tr[tr.variant == "H4f_cheap_leg_10pct_cut0.5"]
    f10 = tr[tr.variant == "H4f_cheap_leg_10pct_cut10"]
    assert set(f05["legs"]) == {"p10_C"}              # 0.4 <= 0.5, 3.0 > 0.5
    assert set(f10["legs"]) == {"p10_C,p10_P"}
    e10 = tr[tr.variant == "H4e10_strangle_10pct"].iloc[0]
    assert abs(e10["ret_1.0"] - ((1.1 - 2 * 0.0005) / (3.4 + 2 * 0.0005) - 1)) < 1e-12
