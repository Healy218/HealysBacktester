# tests/test_rank_mode.py
"""select_meta rank mode: slot portfolio accounting, ranking, DTE dedupe."""
import numpy as np
import pandas as pd
import pytest

from nn_meta.select_meta import _rank_sim, evaluate_rank


def _cands(rows):
    """rows: list of (fill_entry_ts, exit_ts, net_return, symbol, pred)."""
    return pd.DataFrame([{
        "fill_entry_ts": pd.Timestamp(e), "exit_ts": pd.Timestamp(x),
        "net_return": r, "symbol": s, "pred": p,
        "strategy": "ma", "trade_idx": i, "dte": 10, "n_fills": 1,
    } for i, (e, x, r, s, p) in enumerate(rows)])


class TestRankSim:
    def test_single_position_pnl(self):
        c = _cands([("2025-01-02 15:00", "2025-01-03 15:00", 0.20, "SPY", 0.9)])
        total, dd, entered = _rank_sim(c, k=5, f=0.5)
        assert total == pytest.approx(0.5 * 0.20)
        assert entered == [0.20]

    def test_slot_cap_takes_best_scored(self):
        # two candidates at the SAME bar, one slot → higher pred wins
        c = _cands([
            ("2025-01-02 15:00", "2025-01-03 15:00", -0.5, "SPY", 0.6),
            ("2025-01-02 15:00", "2025-01-03 15:00", 0.8, "QQQ", 0.9),
        ])
        total, _, entered = _rank_sim(c, k=1, f=0.1)
        assert entered == [0.8]                     # QQQ (pred 0.9) took the slot
        assert total == pytest.approx(0.1 * 0.8)

    def test_one_position_per_symbol(self):
        c = _cands([
            ("2025-01-02 15:00", "2025-01-05 15:00", 0.3, "SPY", 0.9),
            ("2025-01-03 15:00", "2025-01-06 15:00", 0.4, "SPY", 0.8),  # SPY busy
            ("2025-01-03 15:00", "2025-01-06 15:00", 0.1, "QQQ", 0.7),
        ])
        _, _, entered = _rank_sim(c, k=5, f=0.1)
        assert entered == [0.3, 0.1]

    def test_slot_frees_after_exit(self):
        c = _cands([
            ("2025-01-02 15:00", "2025-01-03 15:00", 0.1, "SPY", 0.9),
            ("2025-01-06 15:00", "2025-01-07 15:00", 0.2, "SPY", 0.9),
        ])
        _, _, entered = _rank_sim(c, k=1, f=0.1)
        assert entered == [0.1, 0.2]                # second enters after first exits

    def test_compounding_at_entry_equity(self):
        c = _cands([
            ("2025-01-02 15:00", "2025-01-03 15:00", 1.0, "SPY", 0.9),
            ("2025-01-06 15:00", "2025-01-07 15:00", 1.0, "QQQ", 0.9),
        ])
        total, _, _ = _rank_sim(c, k=1, f=0.5)
        # eq 1.0 → +0.5 → 1.5; second sized 0.75 → +0.75 → 2.25
        assert total == pytest.approx(1.25)


class TestEvaluateRank:
    def test_dte_variants_dedupe_to_best_scored(self):
        rows = _cands([
            ("2025-01-02 15:00", "2025-01-03 15:00", 0.5, "SPY", 0.0),
            ("2025-01-02 15:00", "2025-01-03 15:00", -0.2, "SPY", 0.0),
        ])
        rows["trade_idx"] = 0                       # same proposal…
        rows["dte"] = [10, 45]                      # …two DTE variants
        pred = np.array([0.9, 0.7])                 # model prefers the 10 DTE
        m = evaluate_rank(rows, pred, threshold=0.5, k=5, f=0.1)
        assert m["n_kept"] == 1
        assert m["total_return"] == pytest.approx(0.1 * 0.5)

    def test_threshold_filters_before_ranking(self):
        rows = _cands([("2025-01-02 15:00", "2025-01-03 15:00", 0.5, "SPY", 0.0)])
        m = evaluate_rank(rows, np.array([0.4]), threshold=0.5)
        assert m["n_kept"] == 0 and m["total_return"] is None
