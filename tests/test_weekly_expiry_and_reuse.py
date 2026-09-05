"""v6 mechanics (2026-09-05): weekly-expiry DTE variants and additive row reuse."""
import numpy as np
import pandas as pd
import pytest

from nn_meta import config
from nn_meta.weekly_expiry import weekly_expiry_symbols, dte_grid_for


def _universe(tmp_path):
    rows = []
    for d in pd.date_range("2026-01-05", "2026-06-26", freq="D"):
        if d.weekday() in (0, 2, 4):                 # SPY: Mon/Wed/Fri
            rows.append(("SPY", d))
        if d.weekday() == 4:                          # XYZ: Fridays only
            rows.append(("XYZ", d))
        if d.weekday() in (0, 4) and d.day < 8:       # ABC: sparse Mon/Fri
            rows.append(("ABC", d))
    df = pd.DataFrame(rows, columns=["underlying", "expiration"])
    df["ticker"] = "O:" + df["underlying"] + df["expiration"].dt.strftime("%y%m%d") + "C00100000"
    df["life_start"] = df["expiration"] - pd.Timedelta(days=30)
    df["strike"] = 100.0; df["type"] = "call"
    p = tmp_path / "universe.parquet"; df.to_parquet(p, index=False)
    return p


def test_weekly_symbols_need_mon_wed_fri_and_three_per_week(tmp_path):
    assert weekly_expiry_symbols(_universe(tmp_path)) == ["SPY"]


def test_dte_grid_for_appends_weekly_only_when_enabled_and_listed(monkeypatch):
    spec = {"weekly_symbols": ["SPY"]}
    monkeypatch.setattr(config, "WEEKLY_DTE_ENABLED", False)
    assert dte_grid_for("SPY", spec) == list(config.DTE_GRID)
    monkeypatch.setattr(config, "WEEKLY_DTE_ENABLED", True)
    assert dte_grid_for("SPY", spec) == sorted(set(config.DTE_GRID) | set(config.DTE_GRID_WEEKLY))
    assert dte_grid_for("XYZ", spec) == list(config.DTE_GRID)
    assert dte_grid_for("SPY", None) == list(config.DTE_GRID)


def test_build_symbol_rows_reuses_families_from_an_earlier_pool(monkeypatch):
    from nn_meta import build_meta_dataset as B
    idx = pd.date_range("2025-01-02 14:30", periods=300, freq="15min")
    bars = pd.DataFrame({"Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.0,
                         "Volume": 1000.0}, index=idx)
    monkeypatch.setattr(B, "load_underlying_15m", lambda sym: bars)
    proposed = []
    monkeypatch.setattr(B, "propose_trades",
                        lambda bars, strat, params, ws, we: proposed.append(strat) or [])
    reused = pd.DataFrame({"symbol": ["SPY"] * 2, "strategy": ["rsi", "rsi"],
                           "trade_idx": [0, 1], "dte": [5, 5],
                           "entry_ts": pd.to_datetime(["2025-01-02 15:00", "2025-01-03 15:00"]),
                           "net_return": [0.1, -0.1], "executed": [True, True]})
    from nn_meta.mark_stream import stable_trade_id
    tids = stable_trade_id(reused).tolist()
    marks = pd.DataFrame({"trade_id": [tids[0], "other"],
                          "mark_ts": pd.to_datetime(["2025-01-02 15:15", "2025-01-02 15:15"]),
                          "gross_return": [0.01, 0.5]})
    spec_entry = {"strategies": {"rsi": {"params": {}}, "ma": {"params": {}}}}
    sink = []
    out = B.build_symbol_rows("SPY", spec_entry, provider=None, marks_sink=sink,
                              reuse=(reused, marks))
    assert proposed == ["ma"]                          # rsi was NOT rebuilt
    assert len(out) == 2 and set(out["strategy"]) == {"rsi"}
    assert len(sink) == 1 and sink[0]["trade_id"].tolist() == [tids[0]]   # only its marks


def test_reusable_rows_only_for_families_with_identical_frozen_entries(tmp_path, monkeypatch):
    from nn_meta import build_meta_dataset as B
    import json
    monkeypatch.setattr(config, "ROOT", tmp_path)
    old = tmp_path / "artifacts_v5"; (old / "meta_rows").mkdir(parents=True); (old / "meta_marks").mkdir()
    (old / "baseline_spec.json").write_text(json.dumps({"symbols": {"SPY": {"strategies": {
        "rsi": {"params": {"w": 14}, "dte": 5}, "ma": {"params": {"w": 20}, "dte": 30}}}}}))
    pd.DataFrame({"symbol": ["SPY"] * 2, "strategy": ["rsi", "ma"], "trade_idx": [0, 0],
                  "dte": [5, 30], "entry_ts": pd.to_datetime(["2025-01-02", "2025-01-03"]),
                  "net_return": [0.1, 0.2], "executed": [True, True]}).to_parquet(old / "meta_rows" / "SPY.parquet")
    new_entry = {"strategies": {"rsi": {"params": {"w": 14}, "dte": 5},      # unchanged → reuse
                                "ma": {"params": {"w": 20}, "dte": 45},       # re-frozen → rebuild
                                "keltner": {"params": {"w": 10}, "dte": 5}}}  # new → build
    rows, mk = B._reusable_rows("SPY", new_entry, "v5", marks=False)
    assert rows["strategy"].tolist() == ["rsi"] and mk is None
    assert B._reusable_rows("XYZ", new_entry, "v5", marks=False) is None


def test_additive_freeze_sweeps_only_new_families_and_refreezes_weekly_names(monkeypatch):
    from nn_meta import baseline as B
    idx = pd.date_range("2025-01-02 14:30", periods=100, freq="15min")
    bars = pd.DataFrame({"Open": 1.0, "High": 1.0, "Low": 1.0, "Close": 1.0, "Volume": 1.0}, index=idx)
    monkeypatch.setattr(B, "load_underlying_15m", lambda sym: bars)
    swept = []
    def fake_freeze(symbol, strat, bars, provider, ts, te, dte_grid=None):
        swept.append((symbol, strat, tuple(dte_grid or [])))
        return {"params": {"p": 1}, "dte": 5, "train_option": {"5": {"per_trade_sharpe": 0.1}}}
    monkeypatch.setattr(B, "_freeze_one_strategy", fake_freeze)
    monkeypatch.setattr(config, "PROPOSAL_STRATEGIES", ["ma", "rsi", "keltner"])
    monkeypatch.setattr(config, "WEEKLY_DTE_ENABLED", True)
    base = {"strategies": {"ma": {"params": {"w": 9}, "dte": 30, "train_option": {"30": {"per_trade_sharpe": 0.9}}},
                           "rsi": {"params": {"w": 14}, "dte": 5, "train_option": {"5": {"per_trade_sharpe": 0.2}}}}}
    # ordinary name: inherit ma/rsi untouched, sweep only keltner, best across the union
    out = B.freeze_symbol("XYZ", provider=None, weekly_symbols=["SPY"], strategies=["keltner"], base_entry=base)
    assert [s[1] for s in swept] == ["keltner"] and swept[0][2] == tuple(config.DTE_GRID)
    assert out["strategies"]["ma"] == base["strategies"]["ma"] and out["best_strategy"] == "ma"
    # weekly name: grid changed -> every family re-frozen on the extended grid, base ignored
    swept.clear()
    out = B.freeze_symbol("SPY", provider=None, weekly_symbols=["SPY"], strategies=["keltner"], base_entry=base)
    assert sorted(s[1] for s in swept) == ["keltner", "ma", "rsi"]
    assert all(set(config.DTE_GRID_WEEKLY) <= set(s[2]) for s in swept)
    assert out["strategies"]["ma"]["params"] == {"p": 1}
