"""
Unit tests for utils/runner_utils.py — the shared helpers all backtest runners
delegate to. Pure functions, no network or heavy deps.

Run with:  python -m unittest discover -s tests   (or pytest tests/)
"""
import unittest

import numpy as np

from utils import runner_utils


class TestStopResolvers(unittest.TestCase):
    def test_sl_stop_enabled(self):
        cfg = {"USE_STOP_LOSS": True, "STOP_LOSS_PERCENT": 0.05}
        self.assertEqual(runner_utils.sl_stop(cfg), 0.05)

    def test_sl_stop_disabled(self):
        cfg = {"USE_STOP_LOSS": False, "STOP_LOSS_PERCENT": 0.05}
        self.assertIsNone(runner_utils.sl_stop(cfg))

    def test_sl_stop_enabled_but_zero_is_none(self):
        cfg = {"USE_STOP_LOSS": True, "STOP_LOSS_PERCENT": 0}
        self.assertIsNone(runner_utils.sl_stop(cfg))

    def test_sl_stop_missing_keys(self):
        self.assertIsNone(runner_utils.sl_stop({}))

    def test_tp_stop_enabled(self):
        cfg = {"USE_TAKE_PROFIT": True, "TAKE_PROFIT_PERCENT": 0.1}
        self.assertEqual(runner_utils.tp_stop(cfg), 0.1)

    def test_tp_stop_disabled(self):
        cfg = {"USE_TAKE_PROFIT": False, "TAKE_PROFIT_PERCENT": 0.1}
        self.assertIsNone(runner_utils.tp_stop(cfg))


class TestSimKwargs(unittest.TestCase):
    def test_defaults_applied(self):
        sk = runner_utils.sim_kwargs({})
        self.assertEqual(sk["initial_capital"], 100_000.0)
        self.assertEqual(sk["fees"], 0.001)
        self.assertEqual(sk["slippage"], 0.0005)
        self.assertEqual(sk["size"], 0.9)
        self.assertEqual(sk["size_type"], "percent")
        self.assertIsNone(sk["sl_stop"])
        self.assertIsNone(sk["tp_stop"])

    def test_explicit_sl_tp_passed_through(self):
        sk = runner_utils.sim_kwargs({}, sl=0.05, tp=0.1)
        self.assertEqual(sk["sl_stop"], 0.05)
        self.assertEqual(sk["tp_stop"], 0.1)

    def test_sl_tp_derived_from_cfg_when_omitted(self):
        cfg = {
            "USE_STOP_LOSS": True, "STOP_LOSS_PERCENT": 0.03,
            "USE_TAKE_PROFIT": True, "TAKE_PROFIT_PERCENT": 0.07,
        }
        sk = runner_utils.sim_kwargs(cfg)
        self.assertEqual(sk["sl_stop"], 0.03)
        self.assertEqual(sk["tp_stop"], 0.07)

    def test_config_overrides(self):
        cfg = {"INITIAL_CAPITAL": 50_000.0, "FEES_PERCENT": 0.002}
        sk = runner_utils.sim_kwargs(cfg)
        self.assertEqual(sk["initial_capital"], 50_000.0)
        self.assertEqual(sk["fees"], 0.002)

    def test_expected_keys_present(self):
        sk = runner_utils.sim_kwargs({})
        for key in (
            "initial_capital", "fees", "slippage", "size", "size_type",
            "sl_stop", "tp_stop", "trend_filter_window", "atr_sl_window",
            "atr_sl_multiplier", "use_trailing_stop", "atr_position_sizing",
            "risk_per_trade",
        ):
            self.assertIn(key, sk)


class TestRangeBuilders(unittest.TestCase):
    def test_arange_int_from_defaults(self):
        arr = runner_utils.arange_int({}, "A", "B", "C", (3, 9, 3))
        self.assertEqual(list(arr), [3, 6])
        self.assertTrue(np.issubdtype(arr.dtype, np.integer))

    def test_arange_int_from_cfg(self):
        cfg = {"A": 2, "B": 10, "C": 2}
        arr = runner_utils.arange_int(cfg, "A", "B", "C", (0, 0, 1))
        self.assertEqual(list(arr), [2, 4, 6, 8])

    def test_linspace_inclusive_endpoint(self):
        arr = runner_utils.linspace({}, "A", "B", "C", (0.0, 1.0, 0.5))
        self.assertEqual(len(arr), 3)
        self.assertAlmostEqual(arr[0], 0.0)
        self.assertAlmostEqual(arr[-1], 1.0)


class TestErr(unittest.TestCase):
    def test_err_shape_and_logging(self):
        import logging
        logger = logging.getLogger("test_runner_utils")
        result = runner_utils.err("boom", "MA", logger)
        self.assertEqual(
            result,
            {"top5": [], "error": "boom", "portfolio": None, "price_data": None},
        )


if __name__ == "__main__":
    unittest.main()
