"""
Tests for the roadmap chart builders: buy-&-hold benchmark overlay, Monte Carlo
bootstrap, and the walk-forward per-fold breakdown. Offline (synthetic prices).

Run with:  python -m unittest discover -s tests   (or pytest tests/)
"""
import unittest

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import vectorbt as vbt

from analysis import plotting


def _portfolio(seed=5, n=400):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    close = pd.Series(100 + np.cumsum(rng.normal(0.05, 1, n)), index=idx)
    price_df = close.to_frame("Close")
    price_df["High"] = close + 1
    price_df["Low"] = close - 1
    fast = vbt.MA.run(close, 10).ma
    slow = vbt.MA.run(close, 30).ma
    entries = fast.vbt.crossed_above(slow)
    exits = fast.vbt.crossed_below(slow)
    pf = vbt.Portfolio.from_signals(close, entries, exits, freq="1D",
                                    init_cash=100_000, fees=0.001)
    return pf, price_df


class TestBenchmark(unittest.TestCase):
    def test_two_traces_strategy_and_benchmark(self):
        pf, price_df = _portfolio()
        fig = plotting.plot_equity_vs_benchmark(pf, price_df)
        self.assertIsInstance(fig, go.Figure)
        self.assertEqual(len(fig.data), 2)
        self.assertTrue(fig.data[0].name.startswith("Strategy"))
        self.assertTrue(fig.data[1].name.startswith("Buy & Hold"))

    def test_none_on_missing_close(self):
        pf, _ = _portfolio()
        self.assertIsNone(plotting.plot_equity_vs_benchmark(pf, pd.DataFrame({"X": [1]})))


class TestMonteCarlo(unittest.TestCase):
    def test_returns_figure_with_enough_trades(self):
        pf, _ = _portfolio()
        fig = plotting.plot_monte_carlo(pf, n_sims=300)
        self.assertIsInstance(fig, go.Figure)
        self.assertIn("Monte Carlo", fig.layout.title.text)

    def test_deterministic_with_seed(self):
        pf, _ = _portfolio()
        a = plotting.plot_monte_carlo(pf, n_sims=300, seed=1)
        b = plotting.plot_monte_carlo(pf, n_sims=300, seed=1)
        self.assertEqual(a.layout.title.text, b.layout.title.text)

    def test_none_when_too_few_trades(self):
        rng = np.random.default_rng(0)
        close = pd.Series(100 + np.cumsum(rng.normal(0, 1, 100)),
                          index=pd.date_range("2023-01-01", periods=100, freq="D"))
        held = vbt.Portfolio.from_holding(close, freq="1D")   # 1 trade
        self.assertIsNone(plotting.plot_monte_carlo(held))


class TestWalkForwardFolds(unittest.TestCase):
    def test_one_trace_per_fold(self):
        rng = np.random.default_rng(2)
        folds = []
        for k in range(3):
            r = pd.Series(rng.normal(0.001, 0.01, 60),
                          index=pd.date_range(f"2023-0{k + 1}-01", periods=60, freq="D"))
            folds.append({"fold": k + 1, "param_label": f"p={k}", "returns": r})
        fig = plotting.plot_walkforward_folds(folds)
        self.assertIsInstance(fig, go.Figure)
        self.assertEqual(len(fig.data), 3)

    def test_empty_returns_none(self):
        self.assertIsNone(plotting.plot_walkforward_folds([]))
        self.assertIsNone(plotting.plot_walkforward_folds([{"fold": 1, "returns": None}]))


if __name__ == "__main__":
    unittest.main()
