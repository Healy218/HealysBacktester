"""Mark-stream schema, deterministic keying, IO, and the ledger bridge."""
import pandas as pd
import pytest

from nn_meta.mark_stream import (execution_frames, load_mark_stream,
                                 mark_stream_path, option_b_blockers,
                                 stable_trade_id, validate_mark_stream,
                                 write_mark_stream)
from nn_meta.v4_accounting import (AccountingDataError, CostScenario,
                                   mark_to_market_portfolio)


def _rows():
    return pd.DataFrame({
        "symbol": ["SPY", "QQQ"], "strategy": ["rsi", "rsi"],
        "trade_idx": [1, 2], "dte": [5, 5],
        "entry_ts": pd.to_datetime(["2025-01-02 14:30", "2025-01-03 14:30"]),
        "fill_entry_ts": pd.to_datetime(["2025-01-02 14:45", "2025-01-03 14:45"]),
        "exit_ts": pd.to_datetime(["2025-01-03 14:30", "2025-01-04 14:30"]),
        "fill_exit_ts": pd.to_datetime(["2025-01-03 14:30", "2025-01-04 14:30"]),
        "net_return": [0.18, -0.12], "gross_return": [0.20, -0.10],
    })


def _marks_for(rows):
    tid = stable_trade_id(rows).tolist()
    return pd.DataFrame({
        "trade_id": [tid[0], tid[0], tid[0], tid[1], tid[1]],
        "mark_ts": pd.to_datetime(["2025-01-02 14:45", "2025-01-03 12:00",
                                    "2025-01-03 14:30", "2025-01-03 14:45",
                                    "2025-01-04 14:30"]),
        "gross_return": [0.0, -0.10, 0.20, 0.0, -0.10],
    })


def test_stable_trade_id_is_order_independent():
    rows = _rows()
    ids = stable_trade_id(rows)
    shuffled = rows.iloc[::-1]
    ids_shuffled = stable_trade_id(shuffled)
    # The id for a given underlying row is identical regardless of frame order.
    assert ids.loc[0] == ids_shuffled.loc[0]
    assert ids.nunique() == len(rows)


def test_stable_trade_id_separates_same_contract_on_different_bars():
    rows = _rows()
    rows.loc[1, ["symbol", "strategy", "trade_idx", "dte"]] = ["SPY", "rsi", 1, 5]
    # Same contract identity, different entry bar -> still distinct ids.
    assert stable_trade_id(rows).nunique() == 2


def test_roundtrip_write_load(tmp_path):
    marks = _marks_for(_rows())
    path = mark_stream_path(tmp_path / "meta_dataset.parquet")
    assert path.name == "meta_dataset.marks.parquet"
    write_mark_stream(marks, path)
    loaded = load_mark_stream(path)
    assert list(loaded.columns) == ["trade_id", "mark_ts", "gross_return"]
    assert len(loaded) == len(marks)


def test_validate_rejects_missing_columns():
    with pytest.raises(AccountingDataError, match="missing columns"):
        validate_mark_stream(pd.DataFrame({"trade_id": ["x"], "mark_ts": [pd.Timestamp.now()]}))


def test_validate_rejects_nonfinite_and_duplicates():
    marks = _marks_for(_rows())
    bad = marks.copy()
    bad.loc[0, "gross_return"] = float("nan")
    with pytest.raises(AccountingDataError, match="finite"):
        validate_mark_stream(bad)
    dup = pd.concat([marks, marks.iloc[[0]]], ignore_index=True)
    with pytest.raises(AccountingDataError, match="duplicate"):
        validate_mark_stream(dup)


def test_execution_frames_feed_the_ledger():
    rows = _rows()
    trades, marks = execution_frames(rows, _marks_for(rows))
    assert set(trades.columns) >= {"trade_id", "symbol", "signal_ts",
                                   "fill_entry_ts", "fill_exit_ts", "gross_return"}
    metrics, curve = mark_to_market_portfolio(
        trades, marks, max_concurrent=2, position_fraction=0.5,
        costs=CostScenario(name="zero", fee=0, slippage=0))
    # Matches the accounting fixture: SPY dips before recovering, QQQ loses.
    assert metrics["total_return"] == pytest.approx(0.045)
    assert metrics["max_drawdown"] > 0.04


def test_execution_frames_requires_execution_columns():
    rows = _rows().drop(columns=["fill_exit_ts"])
    with pytest.raises(AccountingDataError, match="fill_exit_ts"):
        execution_frames(rows, _marks_for(_rows()))


def test_option_b_blockers_lists_both_gaps_on_committed_dataset():
    cols = ["symbol", "strategy", "trade_idx", "dte", "entry_ts", "exit_ts",
            "net_return", "executed"]                       # no provenance cols
    blockers = option_b_blockers(cols, mark_stream_exists=False)
    assert len(blockers) == 2
    assert any("execution-provenance" in b for b in blockers)
    assert any("mark stream" in b for b in blockers)


def test_option_b_blockers_empty_when_ready():
    cols = ["fill_entry_ts", "fill_exit_ts", "gross_return", "entry_ts"]
    assert option_b_blockers(cols, mark_stream_exists=True) == []


def test_option_b_blockers_flags_only_missing_stream_when_cols_present():
    cols = ["fill_entry_ts", "fill_exit_ts", "gross_return"]
    blockers = option_b_blockers(cols, mark_stream_exists=False)
    assert len(blockers) == 1 and "mark stream" in blockers[0]
