# tests/test_option_log.py
"""Dashboard option trade-log helpers: settlement classification + table build."""
import main


def _fill(trade_idx, entry, exit_, expiration, entry_open=2.0, exit_close=3.0,
          right="C", strike=600.0):
    return {"trade_idx": trade_idx, "contract": f"OCC{trade_idx}", "right": right,
            "strike": strike, "expiration": expiration, "entry": entry,
            "exit": exit_, "entry_open": entry_open, "exit_close": exit_close}


class TestSettlement:
    def test_rolled_then_signal_exit(self):
        blotter = [
            _fill(0, "2025-01-10 15:00", "2025-01-31 15:00", "2025-02-21"),
            _fill(0, "2025-01-31 15:00", "2025-02-10 15:00", "2025-03-21"),
        ]
        tbl = main._make_option_log_table(blotter)
        assert [r["Settlement"] for r in tbl.data] == ["rolled", "signal exit"]

    def test_single_fill_held_to_expiration(self):
        blotter = [_fill(1, "2025-02-01 15:00", "2025-02-21 15:00", "2025-02-21",
                         entry_open=4.0, exit_close=0.5, right="P")]
        tbl = main._make_option_log_table(blotter)
        assert tbl.data[0]["Settlement"] == "expired"
        assert tbl.data[0]["Right"] == "Put"

    def test_pnl_and_return_math(self):
        tbl = main._make_option_log_table(
            [_fill(0, "2025-01-10 15:00", "2025-01-20 15:00", "2025-02-21",
                   entry_open=2.0, exit_close=3.0)])
        row = tbl.data[0]
        assert row["Return %"] == "50.00%"
        assert row["P&L $"] == "100.00"          # (3.0 - 2.0) * 100

    def test_empty_blotter_returns_hint(self):
        assert main._make_option_log_table([]) is main._OPTLOG_HINT
        assert main._make_option_log_table(None) is main._OPTLOG_HINT


class TestUpdateCallback:
    # table rows carry store_idx → store position (identity map in these tests)
    def _table(self, top5):
        return [{"store_idx": i, **r} for i, r in enumerate(top5)]

    def test_no_selection_returns_hint(self):
        assert main.update_option_log([], None, None) is main._OPTLOG_HINT

    def test_missing_blotter_returns_hint(self, monkeypatch):
        monkeypatch.setitem(main._last_run, "by_symbol",
                            {"SPY": {"option_blotter": None}})
        top5 = [{"symbol": "SPY", "variant": "5 DTE"}]
        assert main.update_option_log([0], top5, self._table(top5)) is main._OPTLOG_HINT

    def test_renders_variant_blotter(self, monkeypatch):
        blotter = {"5 DTE": [_fill(0, "2025-01-10 15:00", "2025-01-20 15:00",
                                   "2025-02-21")]}
        monkeypatch.setitem(main._last_run, "by_symbol",
                            {"SPY": {"option_blotter": blotter}})
        top5 = [{"symbol": "SPY", "variant": "5 DTE"}]
        tbl = main.update_option_log([0], top5, self._table(top5))
        assert hasattr(tbl, "data") and len(tbl.data) == 1
