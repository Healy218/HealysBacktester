"""Pure-policy tests for the V4 ablation evaluator."""
import pytest
import numpy as np
import pandas as pd

from nn_meta.build_meta_dataset import META_FEATURES, V4_META_FEATURES
from nn_meta.mark_stream import stable_trade_id
from nn_meta.v4_evaluate import (choose_policy, marked_metrics, schema_features,
                                 _policy_rank, _select_winner)


def _spec():
    return {"symbols": {"SPY": {"strategies": {"rsi": {"dte": 5}}}}}


def _rows():
    return pd.DataFrame({
        "symbol": ["SPY", "SPY", "SPY"], "strategy": ["rsi"] * 3,
        "trade_idx": [1, 1, 2], "dte": [5, 10, 5],
        "entry_ts": pd.to_datetime(["2025-01-02", "2025-01-02", "2025-01-03"]),
        "exit_ts": pd.to_datetime(["2025-01-02 15:00", "2025-01-02 15:00", "2025-01-03 15:00"]),
        "executed": [True, True, True], "net_return": [0.10, 0.80, -0.10],
        "n_fills": [2, 2, 2],
    })


def _marked_rows():
    return pd.DataFrame({
        "symbol": ["SPY", "QQQ"], "strategy": ["rsi", "rsi"],
        "trade_idx": [1, 2], "dte": [5, 5],
        "entry_ts": pd.to_datetime(["2025-01-02 14:30", "2025-01-03 14:30"]),
        "fill_entry_ts": pd.to_datetime(["2025-01-02 14:45", "2025-01-03 14:45"]),
        "exit_ts": pd.to_datetime(["2025-01-03 14:30", "2025-01-04 14:30"]),
        "fill_exit_ts": pd.to_datetime(["2025-01-03 14:30", "2025-01-04 14:30"]),
        "executed": [True, True], "net_return": [0.18, -0.12],
        "gross_return": [0.20, -0.10], "n_fills": [2, 2],
    })


def _marked_stream(rows):
    tid = stable_trade_id(rows).tolist()
    return pd.DataFrame({
        "trade_id": [tid[0], tid[0], tid[0], tid[1], tid[1]],
        "mark_ts": pd.to_datetime(["2025-01-02 14:45", "2025-01-03 12:00",
                                    "2025-01-03 14:30", "2025-01-03 14:45",
                                    "2025-01-04 14:30"]),
        "gross_return": [0.0, -0.10, 0.20, 0.0, -0.10],
    })


def test_v4_schema_removes_only_execution_time_premium():
    assert schema_features("legacy") == META_FEATURES
    assert schema_features("v4") == V4_META_FEATURES
    assert "prem_spot" not in schema_features("v4")


def test_policy_selection_uses_the_shared_rank_portfolio():
    rows = _rows()
    policy = choose_policy(rows, np.array([0.8, 0.9, 0.1]), _spec(), thresholds=[0.5])
    assert policy["mode"] == "rank"
    assert policy["metrics"]["n_kept"] == 1
    assert policy["metrics"]["total_return"] > 0


def test_marked_metrics_routes_entered_trades_through_the_ledger():
    rows = _marked_rows()
    metrics = marked_metrics(rows, np.array([0.9, 0.9]), "rank", 0.5,
                             _marked_stream(rows))
    # Both distinct-symbol trades enter; the ledger re-derives P&L from marks.
    assert metrics is not None
    assert metrics["n_positions"] == 2
    assert metrics["max_drawdown"] > 0.0


def test_marked_metrics_returns_none_when_nothing_is_entered():
    rows = _marked_rows()
    assert marked_metrics(rows, np.array([0.1, 0.1]), "rank", 0.5,
                          _marked_stream(rows)) is None


def test_choose_policy_flags_gate_failures_as_ineligible():
    # Only 3 rows -> n_kept < MIN_KEPT_TRADES, so no candidate can clear the
    # gate. choose_policy must still return a winner (callers need something to
    # report), but it has to be marked ineligible, not silently promoted.
    rows = _rows()
    policy = choose_policy(rows, np.array([0.8, 0.9, 0.1]), _spec(), thresholds=[0.5])
    assert policy["eligible"] is False


def _policy(family, total_return, eligible):
    return {"family": family, "metrics": {"total_return": total_return},
            "eligible": eligible}


def test_select_winner_prefers_eligible_over_higher_return():
    # An ineligible family with a much higher raw return must NOT beat an
    # eligible one — this is the fold-selection half of the -26.3% "winner" bug.
    eligible = _policy("gbt", 0.30, True)
    flashy_but_failing = _policy("nn", 0.90, False)
    assert _select_winner([flashy_but_failing, eligible]) is eligible


def test_select_winner_falls_back_to_best_return_when_all_ineligible():
    a = _policy("gbt", -0.26, False)
    b = _policy("nn", -0.40, False)
    winner = _select_winner([a, b])
    assert winner is a and winner["eligible"] is False


def test_policy_rank_orders_eligible_first_then_by_return():
    assert _policy_rank(_policy("x", 0.1, True)) > _policy_rank(_policy("x", 9.9, False))
    assert _policy_rank(_policy("x", 0.5, True)) > _policy_rank(_policy("x", 0.2, True))
    # None return sorts to the very bottom, not crashes.
    assert _policy_rank(_policy("x", None, False))[1] == float("-inf")


# ── Option B: selection through the mark-to-market ledger ────────────────────

def _flip_fixture():
    """Three trade classes that separate the two selection bases.

    clean  (10, pred .9): +5% net, placid marks — the honest policy.
    toxic  (5,  pred .85): small positive FINAL return but interim marks at
           -90%, all five concurrent — invisible to final-return accounting,
           a >40% equity drawdown on the mark path.
    junk   (5,  pred .3): big losers no candidate keeps — they exist so the
           baseline (which keeps everything) is beatable.

    Shared-sim selection crowns thr .5 (clean+toxic: highest return, placid
    realized-only drawdown). Ledger selection must reject it (mark-path
    drawdown breaches the cap) and crown thr .88 (clean only).
    """
    rows, marks = [], []
    day = pd.Timestamp("2025-01-02 14:30")
    for i in range(10):                                     # clean
        e = day + pd.Timedelta(days=i)
        rows.append(("C%02d" % i, e, 0.05, 0.07, 0.9))
    tox_e = day + pd.Timedelta(days=20)
    for j in range(5):                                      # toxic
        rows.append(("T%d" % j, tox_e, 0.04, 0.06, 0.85))
    for j in range(5):                                      # junk
        e = day + pd.Timedelta(days=25 + j)
        rows.append(("J%d" % j, e, -0.50, -0.48, 0.3))

    df = pd.DataFrame({
        "symbol": [r[0] for r in rows], "strategy": "rsi",
        "trade_idx": 1, "dte": 5,
        "entry_ts": [r[1] for r in rows],
        "fill_entry_ts": [r[1] + pd.Timedelta(minutes=15) for r in rows],
        "exit_ts": [r[1] + pd.Timedelta(days=1) for r in rows],
        "fill_exit_ts": [r[1] + pd.Timedelta(days=1) for r in rows],
        "executed": True,
        "net_return": [r[2] for r in rows],
        "gross_return": [r[3] for r in rows],
        "n_fills": 2,
    })
    preds = np.array([r[4] for r in rows])
    tids = stable_trade_id(df).tolist()
    for i, r in df.iterrows():
        marks.append((tids[i], r["fill_entry_ts"], 0.0))
        if r["symbol"].startswith("T"):                     # the concurrent dip
            marks.append((tids[i], r["fill_entry_ts"] + pd.Timedelta(hours=3), -0.90))
        marks.append((tids[i], r["fill_exit_ts"], r["gross_return"]))
    stream = pd.DataFrame(marks, columns=["trade_id", "mark_ts", "gross_return"])
    spec = {"symbols": {s: {"strategies": {"rsi": {"dte": 5}}} for s in df["symbol"]}}
    return df, preds, stream, spec


def test_ledger_selection_rejects_mark_path_drawdown_the_shared_sim_cannot_see():
    df, preds, stream, spec = _flip_fixture()
    shared = choose_policy(df, preds, spec, thresholds=[0.5, 0.88])
    ledger = choose_policy(df, preds, spec, thresholds=[0.5, 0.88],
                           mark_stream=stream)
    assert shared["selection_basis"] == "shared_sim"
    assert shared["threshold"] == 0.5 and shared["eligible"]     # toxic looks fine
    assert ledger["selection_basis"] == "ledger"
    assert ledger["threshold"] == 0.88 and ledger["eligible"]    # toxic rejected
    assert ledger["metrics"]["basis"] == "ledger"
    assert "cost_scenario" in ledger["metrics"]
    assert ledger["baseline_return"] is not None                 # ledger baseline


def test_ledger_selection_without_stream_is_bit_identical_to_legacy():
    rows = _rows()
    a = choose_policy(rows, np.array([0.8, 0.9, 0.1]), _spec(), thresholds=[0.5])
    b = choose_policy(rows, np.array([0.8, 0.9, 0.1]), _spec(), thresholds=[0.5],
                      mark_stream=None)
    assert a["metrics"] == b["metrics"] and a["threshold"] == b["threshold"]
    assert b["selection_basis"] == "shared_sim"


def test_write_report_surfaces_pbo_when_the_winner_carries_it(tmp_path):
    # Regression (2026-09-04): choose_policy computed PBO but evaluate_window's
    # per-fold summary never copied it, so no report ever showed the section.
    from nn_meta.v4_evaluate import _write_report
    base_winner = {
        "family": "nn", "mode": "filter", "threshold": 0.5, "dd_brake": None,
        "eligible": True, "selection_basis": "ledger", "marked": None,
        "test": {"total_return": 0.1, "max_drawdown": 0.05},
        "pbo": {"pbo": 0.25, "n_combinations": 70, "n_days": 40},
    }
    results = [{"schema": "v4", "purged": True, "embargo": "1D", "dd_cap": 0.4,
                "winner": base_winner}]
    out = tmp_path / "r.md"
    _write_report(results, out)
    text = out.read_text()
    assert "## PBO" in text and "| 1 | 0.25 | 70 | 40 |" in text
    results[0]["winner"] = {**base_winner, "pbo": None}
    _write_report(results, out)
    assert "## PBO" not in out.read_text()


def _gate_case():
    # The 2026-09-04 v5 finalize numbers: the standing bar refused a candidate
    # that beats the same book on every risk-aware or order-robust reading.
    baseline = {"n_kept": 203, "total_return": 27.81, "max_drawdown": 0.466,
                "total_ex_top3": 3.819, "ex_top3_max_drawdown": 0.575,
                "ex_top3_median_draws": -0.394, "total_ex_topk": -0.441, "ex_topk_k": 11}
    candidate = {"n_kept": 154, "total_return": 2.013, "max_drawdown": 0.164}
    return baseline, candidate


def test_gate_variants_read_the_same_book_differently():
    from nn_meta.v4_evaluate import _passes_gate
    baseline, cand = _gate_case()
    assert not _passes_gate(cand, baseline, gate_bar="ex_top3")       # +201% < +382%
    assert _passes_gate(cand, baseline, gate_bar="risk")              # 12.3 > 6.6 per unit DD
    assert _passes_gate(cand, baseline, gate_bar="median_draws")      # +201% > -39%
    assert _passes_gate(cand, baseline, gate_bar="ex_topk_pct")       # +201% > -44%
    # risk: a candidate with the baseline's own drawdown must still out-return it
    worse = {"n_kept": 154, "total_return": 2.0, "max_drawdown": 0.40}   # 5.0 < 6.6
    assert not _passes_gate(worse, baseline, gate_bar="risk")
    # MIN_KEPT and the DD cap bind under every variant
    for g in ("ex_top3", "risk", "median_draws", "ex_topk_pct"):
        assert not _passes_gate({**cand, "n_kept": 5}, baseline, gate_bar=g)
        assert not _passes_gate({**cand, "max_drawdown": 0.41}, baseline, gate_bar=g)
    # variants fall back to the standing bar when their extras are absent
    plain = {k: v for k, v in baseline.items() if k in ("n_kept", "total_return", "total_ex_top3")}
    assert not _passes_gate(cand, plain, gate_bar="median_draws")
    assert not _passes_gate(cand, plain, gate_bar="ex_topk_pct")
    with pytest.raises(ValueError):
        _passes_gate(cand, baseline, gate_bar="nope")


def test_choose_policy_reports_every_gate_from_one_book():
    df, preds, stream, spec = _flip_fixture()
    policy = choose_policy(df, preds, spec, thresholds=[0.5, 0.88],
                           mark_stream=stream, report_all_gates=True)
    assert policy["gate_bar"] == "ex_top3"
    bars = policy["gate_bars"]
    assert set(bars) >= {"ex_top3", "risk", "median_draws", "ex_topk_pct", "ex_topk_k"}
    assert bars["ex_topk_k"] >= 3 and len(bars["ex_top3_draws"]) == 8
    for c in policy["candidate_grid"]:
        assert set(c["eligible_by_gate"]) == {"ex_top3", "risk", "median_draws", "ex_topk_pct"}
        assert c["eligible"] == c["eligible_by_gate"]["ex_top3"]
    # the standing path is untouched when nothing is requested
    plain = choose_policy(df, preds, spec, thresholds=[0.5, 0.88], mark_stream=stream)
    assert "gate_bars" not in plain and "eligible_by_gate" not in plain["candidate_grid"][0]
    assert plain["threshold"] == policy["threshold"] and plain["eligible"] == policy["eligible"]
    # a variant can be the selecting gate
    alt = choose_policy(df, preds, spec, thresholds=[0.5, 0.88], mark_stream=stream,
                        gate_bar="median_draws")
    assert alt["gate_bar"] == "median_draws" and "gate_bars" in alt
