"""
Tests for the result-ranking / fill-to-TOP_N behaviour in param_utils and the
chunked_runner leaderboard helpers. Builds a small real vectorbt portfolio.

Run with:  python -m unittest discover -s tests   (or pytest tests/)
"""
import unittest

import numpy as np
import pandas as pd
import vectorbt as vbt

from utils import param_utils, chunked_runner
from utils.param_utils import TOP_N


def _portfolio(seed=3):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=200, freq="D")
    close = pd.Series(100 + np.cumsum(rng.normal(0, 1, 200)), index=idx)
    windows = np.arange(3, 21, 2)          # -> C(9, 2) = 36 combos
    fast, slow = vbt.MA.run_combs(close, window=windows, r=2)
    entries = fast.ma_crossed_above(slow)
    exits = fast.ma_crossed_below(slow)
    pf = vbt.Portfolio.from_signals(close, entries, exits, freq="1D", init_cash=100_000)
    return pf, close, entries, exits


class TestFillToTopN(unittest.TestCase):
    def test_single_pass_returns_up_to_top_n_distinct(self):
        pf, *_ = _portfolio()
        rows = param_utils.top5_from_portfolio(pf)
        self.assertLessEqual(len(rows), TOP_N)
        self.assertGreaterEqual(len(rows), 1)
        # columns are distinct across rows
        labels = [r["param_label"] for r in rows]
        self.assertEqual(len(labels), len(set(labels)))
        # first rows are the per-metric winners
        self.assertEqual(rows[0]["ranked_by"], "Best Sharpe")

    def test_chunked_path_fills_and_dedupes(self):
        pf, close, entries, exits = _portfolio()
        price_df = close.to_frame("Close")
        sim_kwargs = dict(
            initial_capital=100_000.0, fees=0.001, slippage=0.0005, size=0.9,
            size_type="percent", sl_stop=None, tp_stop=None, trend_filter_window=0,
            atr_sl_window=None, atr_sl_multiplier=2.0, use_trailing_stop=False,
            atr_position_sizing=False, risk_per_trade=0.01,
        )
        orig = chunked_runner._compute_chunk_size
        chunked_runner._compute_chunk_size = lambda n_rows: 4   # force chunking
        try:
            res = chunked_runner.simulate_and_rank(
                price_data=price_df, entries=entries, exits=exits,
                short_entries=None, short_exits=None, freq="1D",
                sim_kwargs=sim_kwargs, strategy_tag="TEST",
            )
        finally:
            chunked_runner._compute_chunk_size = orig

        self.assertIsNone(res["error"])
        self.assertIsNotNone(res["portfolio"])
        rows = res["top5"]
        self.assertLessEqual(len(rows), TOP_N)
        labels = [r["param_label"] for r in rows]
        self.assertEqual(len(labels), len(set(labels)), "chunked rows must be distinct columns")


class TestPrunePool(unittest.TestCase):
    def test_prune_keeps_top_k_by_sharpe_deduped(self):
        def row(label, sharpe):
            return {"sharpe_ratio": sharpe, "_saved_signals": {"col_label": label}}
        pool = [row("a", 1.0), row("b", 3.0), row("a", 2.5), row("c", 2.0)]
        out = chunked_runner._prune_sharpe_pool(pool, 2)
        # top-2 by Sharpe, keeping the higher-Sharpe instance of duplicate col "a"
        self.assertEqual([r["_saved_signals"]["col_label"] for r in out], ["b", "a"])


if __name__ == "__main__":
    unittest.main()
