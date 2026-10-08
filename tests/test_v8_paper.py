"""V8 H1 paper decision logic."""
import numpy as np
import pandas as pd

from nn_meta import v8_paper as vp
from nn_meta import v8_vol as vv

DAYS = [d.date().isoformat() for d in pd.bdate_range("2026-10-01", periods=40)]


def test_execution_and_exit_days():
    assert vp.execution_day(pd.Timestamp("2026-10-01 20:21Z"), DAYS) == "2026-10-02"   # after close
    assert vp.execution_day(pd.Timestamp("2026-10-02 13:00Z"), DAYS) == "2026-10-02"   # 09:00 ET
    assert vp.execution_day(pd.Timestamp("2026-10-02 14:30Z"), DAYS) == "2026-10-05"   # 10:30 ET
    assert vp.exit_day("2026-10-02", DAYS) == DAYS[DAYS.index("2026-10-02") + 20]


def test_tercile_uses_only_earlier_exec_days():
    ev = pd.DataFrame({"ticker": [f"T{i}" for i in range(35)],
                       "tau": [pd.Timestamp(f"{d} 12:00Z") for d in DAYS[:35]],
                       "sue": np.arange(35, dtype=float)})
    s = vp.tercile_signals(ev, DAYS)
    assert not s["signal"].iloc[:30].any() and s["signal"].iloc[30:].all()


def test_plan_entries_priority_and_slots():
    c = pd.DataFrame({"ticker": ["A", "B", "C", "D"], "adv20": [1e8, 5e8, 5e8, 2e8]})
    assert vp.plan_entries(c, held={"D"}, slots=3) == ["B", "C"]
    assert vp.admitted(4.99, 1e9, 20) is False and vp.admitted(10, 3e7, 20) is True


def test_pick_call_from_quotes():
    S, sig, today = 100.0, 0.35, "2026-10-01"
    rows = []
    for exp in ("2026-11-06", "2026-11-13", "2026-12-18"):
        T = (pd.Timestamp(exp) - pd.Timestamp(today)).days / 365
        for K in np.arange(80, 121, 5.0):
            for cp in "CP":
                m = float(vv.black76(S, K, T, sig, cp == "C"))
                rows.append((f"X{exp}{cp}{K}", exp, cp, K, m - 0.05, m + 0.05))
    ch = pd.DataFrame(rows, columns=["symbol", "expiry", "cp", "strike", "bid", "ask"])
    p = vp.pick_call_from_quotes(ch, today, S)
    assert p["expiry"] == "2026-11-13" and p["dte"] == 43
    assert abs(p["delta"] - 0.6) < 0.1 and abs(p["F"] - S) < 1e-6


def test_client_order_id_is_deterministic():
    assert vp.client_order_id("call", "NVDA", "2026-10-02", "buy") == "v8h1-call-NVDA-2026-10-02-buy"
