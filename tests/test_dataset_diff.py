# tests/test_dataset_diff.py
"""Row alignment for build-vs-build comparison — the part that silently lies
if you get it wrong. See nn_meta/dataset_diff.py for the 2026-08-19 incident
these tests pin down."""
import pandas as pd
import pytest

from nn_meta.dataset_diff import KEY, align, diff_columns


def _rows(n=3, **over):
    """n trades sharing a signal but sitting in different DTE buckets."""
    base = {
        "symbol": ["SPY"] * n,
        "strategy": ["macd"] * n,
        "entry_ts": [pd.Timestamp("2026-02-02 15:00", tz="UTC")] * n,
        "direction": ["long"] * n,
        "right": ["C"] * n,
        "dte": [1, 5, 30][:n],
        "trade_idx": list(range(n)),
        "contract": [f"SPY26020{i}C00500000" for i in range(n)],
        "executed": [1] * n,
        "net_return": [0.10, 0.20, 0.30][:n],
    }
    base.update(over)
    return pd.DataFrame(base)


class TestAlign:
    def test_identical_builds_show_no_differences(self):
        a, b = _rows(), _rows()
        A, B, only_a, only_b = align(a, b)
        assert (len(A), only_a, only_b) == (3, 0, 0)
        assert diff_columns(A, B) == []

    def test_dte_is_part_of_the_key(self):
        """Without dte+trade_idx these rows collapse to one key and mis-pair."""
        a = _rows()
        assert "dte" in KEY and "trade_idx" in KEY
        assert a[["symbol", "strategy", "entry_ts", "direction",
                  "right"]].drop_duplicates().shape[0] == 1   # same signal
        A, B, _, _ = align(a, _rows())
        assert len(A) == 3           # still three distinct rows

    def test_changed_contract_is_reported_not_hidden(self):
        """Keying on contract would mis-pair exactly these rows."""
        moved = ["SPY260200C00510000",      # only this one changed strike
                 "SPY260201C00500000", "SPY260202C00500000"]
        A, B, _, _ = align(_rows(), _rows(contract=moved))
        assert diff_columns(A, B) == [("contract", 1)]

    def test_duplicate_keys_refuse_rather_than_mis_pair(self):
        dup = pd.concat([_rows(1), _rows(1)], ignore_index=True)
        with pytest.raises(ValueError, match="duplicated key"):
            align(dup, _rows(1))

    def test_missing_key_column_is_an_error(self):
        with pytest.raises(KeyError, match="missing key column"):
            align(_rows().drop(columns=["dte"]), _rows())

    def test_extra_rows_are_counted_not_compared(self):
        """A rebuild gains entry-days the frozen spec later drops."""
        extra = _rows(2)
        extra["entry_ts"] = [pd.Timestamp("2026-03-30 15:00", tz="UTC")] * 2
        b = pd.concat([_rows(), extra], ignore_index=True)
        A, B, only_a, only_b = align(_rows(), b)
        assert (len(A), only_a, only_b) == (3, 0, 2)
        assert diff_columns(A, B) == []

    def test_float_noise_is_not_a_difference(self):
        b = _rows(net_return=[0.10 + 1e-12, 0.20, 0.30])
        A, B, _, _ = align(_rows(), b)
        assert diff_columns(A, B) == []

    def test_differences_sort_worst_first(self):
        b = _rows(executed=[0, 0, 1], net_return=[0.99, 0.20, 0.30])
        A, B, _, _ = align(_rows(), b)
        assert [c for c, _ in diff_columns(A, B)] == ["executed", "net_return"]
