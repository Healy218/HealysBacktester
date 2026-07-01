"""
Tests for the scanner's per-strategy signal checkers, including the newly
added Bollinger Bands and Stochastic support. Offline (synthetic prices).

Run with:  python -m unittest discover -s tests   (or pytest tests/)
"""
import unittest

import numpy as np
import pandas as pd

from scanner import signal_scanner as ss

_VALID_SIGNALS = {"BUY", "SELL", "IN_TRADE", "OUT", "HOLD", "INSUFFICIENT_DATA"}


def _series(n=150, seed=7):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    close = pd.Series(100 + np.cumsum(rng.normal(0, 1, n)), index=idx)
    return close


class TestScannerBBands(unittest.TestCase):
    def test_valid_signal_and_bands(self):
        close = _series()
        out = ss._check_bbands(close, {"bb_window": 20, "bb_alpha": 2.0})
        self.assertIn(out["signal"], _VALID_SIGNALS)
        if out["signal"] != "INSUFFICIENT_DATA":
            # bands are ordered lower <= middle <= upper
            self.assertLessEqual(out["lower"], out["middle"])
            self.assertLessEqual(out["middle"], out["upper"])

    def test_insufficient_data(self):
        close = _series(n=5)
        out = ss._check_bbands(close, {"bb_window": 20, "bb_alpha": 2.0})
        self.assertEqual(out["signal"], "INSUFFICIENT_DATA")


class TestScannerStoch(unittest.TestCase):
    def test_valid_signal_and_bounds(self):
        close = _series()
        high, low = close + 1.0, close - 1.0
        out = ss._check_stoch(
            high, low, close,
            {"k_window": 14, "d_window": 3, "oversold": 20, "overbought": 80},
        )
        self.assertIn(out["signal"], _VALID_SIGNALS)
        if out["signal"] != "INSUFFICIENT_DATA":
            self.assertTrue(0 <= out["percent_k"] <= 100)
            self.assertTrue(0 <= out["percent_d"] <= 100)


class TestScanOneDispatch(unittest.TestCase):
    def test_unknown_strategy_errors(self):
        result = ss.scan_one({
            "strategy": "elliott", "symbol": "SPY", "interval": "1D", "params": {},
        })
        self.assertIsNotNone(result["error"])
        self.assertIn("Unknown strategy", result["error"])


if __name__ == "__main__":
    unittest.main()
