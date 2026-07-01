"""
Smoke test: every backtest runner imports cleanly and exposes a callable run()
with the expected keyword parameters. Guards against import-time regressions
(e.g. the shared runner_utils extraction) without hitting the network.

Run with:  python -m unittest discover -s tests   (or pytest tests/)
"""
import importlib
import inspect
import unittest

RUNNERS = [
    "run_ma", "run_bbands", "run_elliott", "run_stoch", "run_macd",
    "run_rsi", "run_volume", "run_sentiment", "run_walkforward",
]

EXPECTED_PARAMS = {
    "symbol", "start_date", "end_date", "interval",
    "backtest_config", "strategy_config",
}


class TestRunnerImports(unittest.TestCase):
    def test_all_runners_import_and_expose_run(self):
        for name in RUNNERS:
            with self.subTest(runner=name):
                mod = importlib.import_module(f"backtests.{name}")
                self.assertTrue(hasattr(mod, "run"), f"{name} has no run()")
                self.assertTrue(callable(mod.run))
                params = set(inspect.signature(mod.run).parameters)
                missing = EXPECTED_PARAMS - params
                self.assertFalse(missing, f"{name}.run missing params: {missing}")

    def test_runners_share_runner_utils_helpers(self):
        for name in RUNNERS:
            with self.subTest(runner=name):
                mod = importlib.import_module(f"backtests.{name}")
                # every runner exposes the error-result factory and sim kwargs builder
                self.assertTrue(hasattr(mod, "_err"))
                self.assertTrue(hasattr(mod, "_sim_kwargs"))
                err = mod._err("x")
                self.assertEqual(
                    err,
                    {"top5": [], "error": "x", "portfolio": None, "price_data": None},
                )


if __name__ == "__main__":
    unittest.main()
