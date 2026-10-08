import numpy as np
import pandas as pd

from nn_meta import v9_oee_eval as ev


def test_trailing_rank_uses_only_prior_365_days():
    days = pd.Series(pd.date_range("2023-01-01", periods=80, freq="D").strftime("%Y-%m-%d"))
    x = np.arange(80, dtype=float)
    pct, ter = ev.trailing_rank(days, x)
    assert np.isnan(ter[:30]).all()                 # < 30 prior events
    assert ter[30] == 1 and pct[30] == 1.0          # above every prior value
    x2 = x.copy(); x2[50] = -1
    _, ter2 = ev.trailing_rank(days, x2)
    assert ter2[50] == -1
    same = pd.Series(["2023-01-01"] * 40)           # same-day events are not history
    assert np.isnan(ev.trailing_rank(same, np.arange(40.0))[1]).all()


def test_clustered_t_collapses_duplicate_days():
    r = np.array([0.1, 0.2, -0.05, 0.3])
    a = ev.clustered_t(r, np.array([1, 2, 3, 4]))
    b = ev.clustered_t(np.repeat(r, 2), np.repeat([1, 2, 3, 4], 2))
    assert abs(a["mean"] - b["mean"]) < 1e-12
    assert abs(a["t"] - b["t"]) < 1e-9 and b["clusters"] == 4


def test_holm():
    p = ev.holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert abs(p["a"] - 0.03) < 1e-12 and abs(p["c"] - 0.06) < 1e-12 and abs(p["b"] - 0.06) < 1e-12


def test_returns_and_costs():
    assert abs(ev.long_return([(1.0, 0.0)], [(2.0, 0.0)], 1.0) - (1.9995 / 1.0005 - 1)) < 1e-12
    worse = ev.long_return([(1.0, 0.05)], [(2.0, 0.05)], 1.5)
    assert worse < ev.long_return([(1.0, 0.05)], [(2.0, 0.05)], 1.0)
    # short fly, no spreads: credit 2 - 4 fees, close 1 + 4 fees, max loss 5 - credit
    r = ev.fly_return([(1.5, 0), (1.5, 0)], [(0.5, 0), (0.5, 0)], [(1.0, 0), (0.0, 0)],
                      [(0.0, 0), (0.0, 0)], 5.0, 1.0)
    F = ev.FEE
    assert abs(r - (1 - 8 * F) / (3 + 4 * F)) < 1e-12


def test_spread_model_lookup():
    from pathlib import Path
    sm = ev.SpreadModel(Path("nn_meta/validation/v8-spreads-option-20261008-r0/model.json"))
    h = sm.half_spread(3.0, 2, 0.0)
    assert 0 < h < 0.2
    assert sm.half_spread(3.0, 0, 0.0) == h          # DTE < 1 clamps to [1,3)
    assert sm.half_spread(3.0, 2, 0.5) == sm.half_spread(3.0, 2, 0.2)
