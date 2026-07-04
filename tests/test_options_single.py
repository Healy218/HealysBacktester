# tests/test_options_single.py
"""
Tests for the options subsystem.

The end-to-end test uses a SYNTHETIC data provider so it proves the full
pipeline (chain → selection → contract price → simulation → result row) works
today, independent of any vendor's historical-data availability. Also covers
OCC-symbol parsing and contract selection as pure units.
"""
import unittest
from datetime import date

import numpy as np
import pandas as pd

from options.data.provider import (
    OptionContract, OptionsDataProvider, parse_occ_symbol, build_occ_symbol,
)
from options.selection import contract_selector
from options.backtests import run_options_single


class TestOccSymbol(unittest.TestCase):
    def test_parse_occ_symbol(self):
        u, exp, right, strike = parse_occ_symbol("SPY260814C00746000")
        self.assertEqual(u, "SPY")
        self.assertEqual(exp, date(2026, 8, 14))
        self.assertEqual(right, "C")
        self.assertEqual(strike, 746.0)

    def test_round_trip(self):
        sym = build_occ_symbol("SPY", date(2026, 8, 14), "C", 746.0)
        self.assertEqual(sym, "SPY260814C00746000")
        self.assertEqual(parse_occ_symbol(sym), ("SPY", date(2026, 8, 14), "C", 746.0))

    def test_rejects_bad_symbol(self):
        with self.assertRaises(ValueError):
            parse_occ_symbol("not-an-occ-symbol")


class TestContractSelection(unittest.TestCase):
    @staticmethod
    def _chain(as_of, with_greeks=True):
        exp = date.fromordinal(as_of.toordinal() + 30)  # ~30 DTE
        rows = [(95, 0.70), (100, 0.50), (105, 0.30)]
        return [
            OptionContract(
                symbol=build_occ_symbol("SPY", exp, "C", k), underlying="SPY",
                expiration=exp, strike=float(k), right="C",
                delta=(d if with_greeks else None),
            )
            for k, d in rows
        ]

    def test_select_by_delta_picks_nearest_delta(self):
        as_of = date(2026, 1, 2)
        pick = contract_selector.select_by_dte_and_delta(
            self._chain(as_of), right="C", target_dte=30, target_delta=0.50, as_of=as_of)
        self.assertIsNotNone(pick)
        self.assertEqual(pick.strike, 100.0)

    def test_moneyness_fallback_when_no_greeks(self):
        as_of = date(2026, 1, 2)
        chain = self._chain(as_of, with_greeks=False)
        # No greeks → delta selector returns None, select_contract falls back to strike.
        self.assertIsNone(
            contract_selector.select_by_dte_and_delta(chain, right="C", as_of=as_of))
        pick = contract_selector.select_contract(
            chain, right="C", spot=101.0, target_dte=30, moneyness=0.0, as_of=as_of)
        self.assertIsNotNone(pick)
        self.assertEqual(pick.strike, 100.0)  # nearest strike to spot 101


class SyntheticOptionsProvider(OptionsDataProvider):
    """Fabricates an oscillating underlying, a small chain, and a contract path.

    The underlying oscillates so the MA crossover fires entries; the option
    price tracks the underlying so trades produce non-trivial P&L. Contract bars
    share the underlying's index so the signal aligns 1:1.
    """
    def __init__(self):
        self.idx = pd.bdate_range("2026-01-02", periods=60)  # tz-naive
        self.close = 100 + 5 * np.sin(np.linspace(0, 6 * np.pi, 60))

    def _ohlc(self, close):
        close = np.asarray(close, dtype=float)
        openp = np.concatenate([[close[0]], close[:-1]])
        return pd.DataFrame({
            "Open": openp,
            "High": np.maximum(openp, close) * 1.01,
            "Low": np.minimum(openp, close) * 0.99,
            "Close": close,
            "Volume": np.full(close.shape, 1000.0),
        }, index=self.idx)

    def get_underlying_bars(self, symbol, start, end, interval):
        return self._ohlc(self.close)

    def get_chain(self, underlying, *, right=None, expiration_gte=None,
                  expiration_lte=None, strike_gte=None, strike_lte=None, as_of=None):
        exp = self.idx[-1].date()
        return [
            OptionContract(
                symbol=build_occ_symbol(underlying, exp, "C", k), underlying=underlying,
                expiration=exp, strike=float(k), right="C", delta=d,
            )
            for k, d in [(95, 0.70), (100, 0.50), (105, 0.30)]
        ]

    def get_contract_bars(self, occ_symbol, start, end, interval):
        opt_close = np.clip(3.0 + 0.5 * (self.close - 100.0), 0.05, None)
        return self._ohlc(opt_close)


class TestSingleLegEndToEnd(unittest.TestCase):
    def test_run_options_single_end_to_end(self):
        backtest_config = {
            "INITIAL_CAPITAL": 100_000.0,
            "DEFAULT_SIZE": 0.5,
            "DEFAULT_SIZE_TYPE": "percent",
        }
        strategy_config = {"RIGHT": "C", "TARGET_DTE": 55, "TARGET_DELTA": 0.50,
                           "MA_FAST": 3, "MA_SLOW": 6}

        result = run_options_single.run(
            symbol="SPY", start_date="2026-01-02", end_date="2026-03-31",
            interval="1D", backtest_config=backtest_config,
            strategy_config=strategy_config, provider=SyntheticOptionsProvider(),
        )

        self.assertIsNone(result["error"], f"runner errored: {result['error']}")
        self.assertIsNotNone(result["portfolio"])
        self.assertFalse(result["price_data"].empty)
        self.assertEqual(len(result["top5"]), 1)

        row = result["top5"][0]
        for key in ("ranked_by", "param_label", "total_return_pct", "sharpe_ratio",
                    "max_drawdown_pct", "win_rate_pct", "total_trades",
                    "portfolio_col_int_idx"):
            self.assertIn(key, row)
        self.assertGreaterEqual(row["total_trades"], 1)
        self.assertIn("exp", row["param_label"])


if __name__ == "__main__":
    unittest.main()
