# tests/test_execution.py
"""options/execution.py: execute_variant + execute_trade_returns against a
synthetic provider with deterministic prices (hand-computable returns)."""
import numpy as np
import pandas as pd
import pytest

from options.data.provider import OptionsDataProvider, OptionContract, build_occ_symbol
from options.execution import Execution, execute_trade_returns


def _rth_index(day: str, n: int = 26) -> pd.DatetimeIndex:
    """n 15-minute bars starting 14:30 UTC (09:30 ET, no-DST approximation)."""
    return pd.date_range(f"{day} 14:30", periods=n, freq="15min")


class SyntheticProvider(OptionsDataProvider):
    """One call + one put per weekly Friday expiration; linear price ramp.

    Contract bars: Open = Close = 1.0 + 0.01 * bar_position within the
    contract's life, so fills are exactly predictable.
    """

    def __init__(self, days: list[str], expirations: list[str], strike: float = 100.0):
        self._days = days
        self._exps = [pd.Timestamp(e).date() for e in expirations]
        self._strike = strike

    def get_underlying_bars(self, symbol, start, end, interval):
        raise NotImplementedError

    def get_chain(self, underlying, *, right=None, expiration_gte=None,
                  expiration_lte=None, strike_gte=None, strike_lte=None, as_of=None):
        out = []
        for exp in self._exps:
            if expiration_gte and exp < expiration_gte:
                continue
            if expiration_lte and exp > expiration_lte:
                continue
            for r in ("C", "P"):
                if right and r != right:
                    continue
                out.append(OptionContract(
                    symbol=build_occ_symbol(underlying, exp, r, self._strike),
                    underlying=underlying, expiration=exp,
                    strike=self._strike, right=r))
        return out

    def get_contract_bars(self, occ_symbol, start, end, interval):
        # Bars for every trading day up to (and including) expiration day.
        from options.data.provider import parse_occ_symbol
        _, exp, _, _ = parse_occ_symbol(occ_symbol.removeprefix("O:"))
        idx_parts = [_rth_index(d) for d in self._days
                     if pd.Timestamp(d).date() <= exp]
        if not idx_parts:
            return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
        idx = idx_parts[0].append(idx_parts[1:]) if len(idx_parts) > 1 else idx_parts[0]
        # Ramp positions are anchored to the contract's FULL life so prices do
        # not depend on the requested window; slice afterwards.
        px = 1.0 + 0.01 * np.arange(len(idx))
        df = pd.DataFrame({"Open": px, "High": px, "Low": px, "Close": px,
                           "Volume": 100}, index=idx)
        lo = pd.Timestamp(start)
        hi = pd.Timestamp(end) + pd.Timedelta(days=1)
        return df[(df.index >= lo) & (df.index < hi)]


DAYS = ["2025-06-02", "2025-06-03", "2025-06-04", "2025-06-05", "2025-06-06",
        "2025-06-09", "2025-06-10", "2025-06-11", "2025-06-12", "2025-06-13"]


def _underlying():
    idx = _rth_index(DAYS[0])
    for d in DAYS[1:]:
        idx = idx.append(_rth_index(d))
    close = pd.Series(100.0, index=idx)
    return close, idx


def _ex(provider, end="2025-06-30", cfg=None):
    return Execution("SPY", "15m", end, provider, cfg or {})


class TestExecuteTradeReturns:
    def test_single_fill_no_roll_return_math(self):
        # Expiration well beyond the trade exit → one fill, no roll.
        prov = SyntheticProvider(DAYS, ["2025-06-13"])
        close, idx = _underlying()
        # trade: signal at first bar of 6/03 (life bar 26). Honest fills enter
        # at the NEXT bar (27, px 1.27); exit at last bar of 6/04 (bar 77).
        trades = [(idx[26], idx[26 * 3 - 1], 0)]
        recs, meta = execute_trade_returns(_ex(prov), trades, close, idx, 10,
                                           fees=0.0, slippage=0.0)
        assert meta == {"n_signals": 1, "n_executed": 1, "n_fills": 1,
                        "n_rolls": 0, "capped": False, "fill_fail_rate": 0.0}
        r = recs[0]
        assert r["entry_premium"] == pytest.approx(1.27)
        assert r["net_return"] == pytest.approx(1.77 / 1.27 - 1)
        assert r["right"] == "C" and r["executed"]
        assert r["fill_lag_s"] == pytest.approx(15 * 60.0)   # next 15m bar

    def test_legacy_same_bar_fill_via_config(self):
        prov = SyntheticProvider(DAYS, ["2025-06-13"])
        close, idx = _underlying()
        trades = [(idx[26], idx[26 * 3 - 1], 0)]
        ex = _ex(prov, cfg={"FILL_SAME_BAR": True})
        recs, _ = execute_trade_returns(ex, trades, close, idx, 10,
                                        fees=0.0, slippage=0.0)
        r = recs[0]
        assert r["entry_premium"] == pytest.approx(1.26)     # signal bar's open
        assert r["fill_lag_s"] == 0.0

    def test_costs_haircut_both_sides(self):
        prov = SyntheticProvider(DAYS, ["2025-06-13"])
        close, idx = _underlying()
        trades = [(idx[26], idx[26 * 3 - 1], 0)]
        recs, _ = execute_trade_returns(_ex(prov), trades, close, idx, 10,
                                        fees=0.001, slippage=0.0005)
        c = 0.0015
        expected = (1.77 * (1 - c)) / (1.27 * (1 + c)) - 1
        assert recs[0]["net_return"] == pytest.approx(expected)

    def test_short_trade_buys_put(self):
        prov = SyntheticProvider(DAYS, ["2025-06-13"])
        close, idx = _underlying()
        trades = [(idx[26], idx[26 * 3 - 1], 1)]      # direction 1 = short
        recs, _ = execute_trade_returns(_ex(prov), trades, close, idx, 10,
                                        fees=0.0, slippage=0.0)
        assert recs[0]["right"] == "P"
        assert "P" in recs[0]["contract"]

    def test_roll_compounds_fills(self):
        # Contract expires 6/05 while the trade runs to 6/12 → roll to 6/13 exp.
        prov = SyntheticProvider(DAYS, ["2025-06-05", "2025-06-13"])
        close, idx = _underlying()
        trades = [(idx[26], idx[26 * 8 - 1], 0)]      # 6/03 → 6/10 last bar... long life
        recs, meta = execute_trade_returns(_ex(prov), trades, close, idx, 2,
                                           fees=0.0, slippage=0.0)
        r = recs[0]
        assert r["executed"] and r["n_fills"] >= 2 and r["n_rolls"] == r["n_fills"] - 1
        assert meta["n_rolls"] >= 1
        # compounding: net_return equals product of per-fill growths - 1;
        # positive because every synthetic contract ramps upward
        assert r["net_return"] > 0

    def test_unfillable_trade_reported_not_dropped(self):
        # Provider has NO expirations → no chain → no fills.
        prov = SyntheticProvider(DAYS, [])
        close, idx = _underlying()
        trades = [(idx[0], idx[51], 0)]
        recs, meta = execute_trade_returns(_ex(prov), trades, close, idx, 10)
        assert len(recs) == 1
        assert recs[0]["executed"] is False and recs[0]["net_return"] is None
        assert meta["fill_fail_rate"] == 1.0

    def test_fill_lag_when_bars_start_late(self):
        # Contract only prints from 6/04 but the signal fires 6/03 → late fill.
        prov = SyntheticProvider(DAYS[2:], ["2025-06-13"])   # bars start 6/04
        close, idx = _underlying()
        trades = [(idx[26], idx[26 * 4 - 1], 0)]             # signal 6/03 09:30 ET
        recs, _ = execute_trade_returns(_ex(prov), trades, close, idx, 10,
                                        fees=0.0, slippage=0.0)
        r = recs[0]
        assert r["executed"]
        assert r["fill_entry_ts"] == pd.Timestamp("2025-06-04 14:30")
        assert r["fill_lag_s"] == pytest.approx(24 * 3600.0)
