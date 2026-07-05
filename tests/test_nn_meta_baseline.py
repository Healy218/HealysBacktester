# tests/test_nn_meta_baseline.py
"""Pure helpers of nn_meta/baseline.py (no data, no network)."""
import numpy as np
import pytest

from nn_meta import config
from nn_meta.baseline import _parse_ma_label, choose_dte, equity_metrics


class TestParseLabel:
    def test_standard_label(self):
        assert _parse_ma_label("fast=10, slow=50") == (10, 50)

    def test_float_formatting(self):
        assert _parse_ma_label("fast=10.0, slow=50.0") == (10, 50)


class TestEquityMetrics:
    def test_compounding_and_drawdown(self):
        m = equity_metrics([0.5, -0.5, 0.2], f=1.0)
        # equity: 1.5 → 0.75 → 0.90
        assert m["total_return"] == pytest.approx(0.9 - 1.0)
        assert m["max_drawdown"] == pytest.approx(0.5)
        assert m["win_rate"] == pytest.approx(2 / 3)
        assert m["n"] == 3

    def test_position_fraction_dampens(self):
        full = equity_metrics([0.5, -0.5], f=1.0)
        tenth = equity_metrics([0.5, -0.5], f=0.1)
        assert abs(tenth["total_return"]) < abs(full["total_return"])
        assert tenth["max_drawdown"] < full["max_drawdown"]

    def test_none_returns_ignored_and_empty_safe(self):
        assert equity_metrics([None, None])["n"] == 0
        assert equity_metrics([])["total_return"] is None

    def test_sharpe_matches_numpy(self):
        r = [0.1, -0.05, 0.2, 0.03]
        m = equity_metrics(r)
        arr = np.array(r)
        assert m["per_trade_sharpe"] == pytest.approx(arr.mean() / arr.std(ddof=1))


class TestChooseDte:
    def _stats(self, sharpe, n=20, fail=0.1):
        return {"per_trade_sharpe": sharpe, "n": n, "fill_fail_rate": fail}

    def test_best_sharpe_wins(self):
        per = {10: self._stats(0.1), 30: self._stats(0.5), 45: self._stats(0.3)}
        assert choose_dte(per) == 30

    def test_bad_fill_rate_disqualifies(self):
        per = {10: self._stats(0.9, fail=0.8), 30: self._stats(0.2)}
        assert choose_dte(per) == 30

    def test_too_few_trades_disqualifies(self):
        per = {10: self._stats(0.9, n=config.MIN_KEPT_TRADES - 1),
               30: self._stats(0.2)}
        assert choose_dte(per) == 30

    def test_fallback_most_executed_when_none_eligible(self):
        per = {10: self._stats(0.9, n=3), 30: self._stats(0.5, n=5)}
        assert choose_dte(per) == 30

    def test_none_when_nothing_executed(self):
        per = {10: self._stats(None, n=0), 30: self._stats(None, n=0)}
        assert choose_dte(per) is None
