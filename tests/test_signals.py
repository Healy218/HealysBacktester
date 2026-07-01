"""
Shape/behaviour tests for signal generators using synthetic price data.
No network access — prices are generated locally.

Run with:  python -m unittest discover -s tests   (or pytest tests/)
"""
import unittest

import numpy as np
import pandas as pd

from signals import ma_crossover


def _synthetic_close(n=300, seed=0):
    """A deterministic trending-then-reverting close series."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    trend = np.concatenate([np.linspace(100, 140, n // 2),
                            np.linspace(140, 110, n - n // 2)])
    noise = rng.normal(0, 0.5, n)
    return pd.Series(trend + noise, index=idx, name="Close")


class TestMaCrossoverSignals(unittest.TestCase):
    def test_returns_four_aligned_frames(self):
        close = _synthetic_close()
        windows = np.arange(5, 25, 5)
        entries, exits, s_entries, s_exits = ma_crossover.generate_ma_signals(
            close, windows, enable_shorting=False
        )
        # long-only: short frames are None
        self.assertIsNone(s_entries)
        self.assertIsNone(s_exits)
        # entries/exits share shape and index with the input
        self.assertEqual(entries.shape, exits.shape)
        self.assertEqual(len(entries), len(close))
        self.assertTrue(entries.index.equals(close.index))
        # boolean dtype and at least one signal fires on a trending series
        self.assertEqual(entries.values.dtype, np.bool_)
        self.assertTrue(bool(entries.values.any()))

    def test_column_count_is_n_choose_2(self):
        close = _synthetic_close()
        windows = np.arange(5, 25, 5)  # 4 windows -> C(4,2) = 6 pairs
        entries, _, _, _ = ma_crossover.generate_ma_signals(close, windows)
        self.assertEqual(entries.shape[1], 6)

    def test_shorting_enabled_returns_short_frames(self):
        close = _synthetic_close()
        windows = np.arange(5, 25, 5)
        entries, exits, s_entries, s_exits = ma_crossover.generate_ma_signals(
            close, windows, enable_shorting=True
        )
        self.assertIsNotNone(s_entries)
        self.assertIsNotNone(s_exits)
        self.assertEqual(s_entries.shape, entries.shape)

    def test_rejects_non_series_input(self):
        with self.assertRaises(TypeError):
            ma_crossover.generate_ma_signals([1, 2, 3], np.arange(5, 25, 5))

    def test_rejects_too_small_window_range(self):
        close = _synthetic_close()
        with self.assertRaises(ValueError):
            ma_crossover.generate_ma_signals(close, np.array([5]))


if __name__ == "__main__":
    unittest.main()
