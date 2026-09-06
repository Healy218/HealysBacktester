"""Mark-stream schema, deterministic keying, IO, and the ledger bridge."""
import pandas as pd
import pytest

from nn_meta.mark_stream import (execution_frames, load_mark_stream,
                                 marks_from_blotter, marks_from_legs,
                                 mark_stream_path, option_b_blockers,
                                 stable_trade_id, validate_mark_stream,
                                 write_mark_stream, write_mark_stream_shards)
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
        "cost_entries": [1]*5, "cost_exits": [0,0,1,0,1],
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
    assert list(loaded.columns) == ["trade_id", "mark_ts", "gross_return", "cost_entries", "cost_exits"]
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


# ── emission from the executor blotter ───────────────────────────────────────

def _leg(trade_idx, contract, entry_open, closes, start, exit_close=None):
    """One blotter leg with the intratrade bars collect_marks attaches."""
    ts = pd.date_range(start, periods=len(closes), freq="15min")
    return {
        "trade_idx": trade_idx, "contract": contract, "right": "C",
        "strike": 500.0, "expiration": "2025-01-17",
        "entry": str(ts[0]), "exit": str(ts[-1]),
        "entry_open": entry_open,
        "exit_close": exit_close if exit_close is not None else closes[-1],
        "bar_ts": ts.to_numpy(), "bar_close_ts": (ts + pd.Timedelta("15min")).to_numpy(), "bar_close": closes,
    }


def test_marks_from_legs_marks_at_close_against_entry_open():
    leg = _leg(0, "SPY250117C00500000", 2.00, [2.20, 1.80, 2.50],
               "2025-01-02 14:45")
    m = marks_from_legs([leg])
    assert list(m.columns) == ["mark_ts", "gross_return", "cost_entries", "cost_exits"]
    # entry is at bar OPEN, marks at bar CLOSE — the first mark is not zero
    assert m["gross_return"].tolist() == pytest.approx([0., 0.10, -0.10, 0.25])


def test_marks_from_legs_chains_across_rolls():
    # leg 1: 2.00 -> 3.00 (+50%), leg 2 entered at 4.00, marked at 5.00 (+25%)
    first = _leg(0, "SPY250110C00500000", 2.00, [2.50, 3.00], "2025-01-02 14:45")
    second = _leg(0, "SPY250117C00500000", 4.00, [5.00], "2025-01-10 14:45")
    m = marks_from_legs([first, second])
    # final mark compounds both legs: 1.5 * 1.25 - 1 = 0.875
    assert m["gross_return"].iloc[-1] == pytest.approx(0.875)
    # and the pre-roll marks are the first leg's own growth
    assert m["gross_return"].iloc[1] == pytest.approx(0.25)


def test_final_mark_equals_the_executors_gross_return():
    """The invariant that makes the ledger reconcilable against the label."""
    first = _leg(0, "A", 2.00, [2.50, 3.00], "2025-01-02 14:45")
    second = _leg(0, "B", 4.00, [5.00], "2025-01-10 14:45")
    gross_growth = 1.0
    for leg in (first, second):
        gross_growth *= leg["exit_close"] / leg["entry_open"]
    m = marks_from_legs([first, second])
    assert m["gross_return"].iloc[-1] == pytest.approx(gross_growth - 1.0)


def test_marks_from_legs_dedupes_roll_boundary_timestamp():
    first = _leg(0, "A", 2.00, [2.00, 3.00], "2025-01-02 14:45")
    # new leg's first bar shares the old leg's last timestamp
    second = _leg(0, "B", 4.00, [4.40], "2025-01-02 15:15")
    m = marks_from_legs([first, second])
    assert not m["mark_ts"].duplicated().any()
    # the open leg wins: 1.5 * 1.10 - 1
    assert m["gross_return"].iloc[-1] == pytest.approx(0.65)


def test_marks_from_legs_rejects_legs_without_bars():
    leg = _leg(0, "A", 2.00, [2.20], "2025-01-02 14:45")
    del leg["bar_close"]
    with pytest.raises(AccountingDataError, match="collect_marks"):
        marks_from_legs([leg])


def test_marks_from_blotter_keys_and_skips_unknown_trades():
    rows = _rows()
    tid = stable_trade_id(rows).tolist()
    blotter = {
        1: [_leg(1, "A", 2.00, [2.20], "2025-01-02 14:45")],
        2: [_leg(2, "B", 2.00, [1.80], "2025-01-03 14:45")],
        7: [_leg(7, "C", 2.00, [9.90], "2025-01-05 14:45")],   # dropped row
    }
    marks = marks_from_blotter(blotter, {1: tid[0], 2: tid[1]})
    assert set(marks["trade_id"]) == {tid[0], tid[1]}
    assert len(marks) == 4


def test_emitted_marks_flow_into_the_ledger():
    """End to end: blotter → mark stream → execution_frames → ledger."""
    rows = _rows()
    tid = stable_trade_id(rows).tolist()
    blotter = {
        1: [_leg(1, "A", 2.00, [2.20, 2.40], "2025-01-02 14:45")],
        2: [_leg(2, "B", 2.00, [1.90, 1.80], "2025-01-03 14:45")],
    }
    marks = marks_from_blotter(blotter, {1: tid[0], 2: tid[1]})
    rows = rows.copy()
    # point the rows at the emitted marks' own fill window
    rows["fill_entry_ts"] = [pd.Timestamp("2025-01-02 14:45"),
                             pd.Timestamp("2025-01-03 14:45")]
    rows["fill_exit_ts"] = [pd.Timestamp("2025-01-02 15:15"),
                            pd.Timestamp("2025-01-03 15:15")]
    rows["gross_return"] = [0.20, -0.10]
    trades, filtered = execution_frames(rows, marks)
    assert len(trades) == 2 and len(filtered) == 6
    assert option_b_blockers(rows.columns, mark_stream_exists=True) == []


# ── sharded assembly (the full stream does not fit in memory) ────────────────

def _shards(tmp_path, rows):
    """One mark shard per symbol, as build_rows writes them."""
    tid = stable_trade_id(rows).tolist()
    paths = []
    for i, sym in enumerate(rows["symbol"]):
        p = tmp_path / f"{sym}.parquet"
        pd.DataFrame({
            "trade_id": [tid[i], tid[i]],
            "mark_ts": pd.to_datetime([f"2025-01-0{2 + i} 14:45",
                                       f"2025-01-0{3 + i} 14:30"]),
            "gross_return": [0.0, 0.20 if i == 0 else -0.10],
            "cost_entries": [1,1], "cost_exits": [0,1],
        }).to_parquet(p, index=False)
        paths.append(p)
    return paths, tid


def test_trade_id_is_categorical_after_validation():
    """The dictionary key is what keeps an 88M-row stream off the ~9 GB path."""
    marks = validate_mark_stream(_marks_for(_rows()))
    assert isinstance(marks["trade_id"].dtype, pd.CategoricalDtype)
    # categories are pinned lexically, so the sort matches plain strings
    assert marks["trade_id"].astype(str).is_monotonic_increasing
    # …including when the categories arrive in first-appearance order, as they
    # do from a parquet dictionary — otherwise the sort is assembly-dependent
    shuffled = _marks_for(_rows()).iloc[::-1].copy()
    shuffled["trade_id"] = pd.Categorical(
        shuffled["trade_id"], categories=shuffled["trade_id"].unique())
    assert validate_mark_stream(shuffled)["trade_id"].astype(str) \
        .is_monotonic_increasing


def test_write_shards_matches_a_single_frame_write(tmp_path):
    rows = _rows()
    paths, _ = _shards(tmp_path, rows)
    dest, n_rows, n_trades = write_mark_stream_shards(
        paths, mark_stream_path(tmp_path / "meta_dataset.parquet"))
    assert (n_rows, n_trades) == (4, 2)
    streamed = load_mark_stream(dest)
    one_shot = validate_mark_stream(
        pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True))
    pd.testing.assert_frame_equal(streamed, one_shot)


def test_write_shards_drops_purged_trades(tmp_path):
    rows = _rows()
    paths, tid = _shards(tmp_path, rows)
    dest, n_rows, n_trades = write_mark_stream_shards(
        paths, mark_stream_path(tmp_path / "meta_dataset.parquet"),
        keep_ids=[tid[0]])                       # second symbol purged by split
    assert (n_rows, n_trades) == (2, 1)
    assert set(load_mark_stream(dest)["trade_id"]) == {tid[0]}


def test_write_shards_writes_an_empty_stream_when_nothing_survives(tmp_path):
    rows = _rows()
    paths, _ = _shards(tmp_path, rows)
    dest, n_rows, n_trades = write_mark_stream_shards(
        paths, mark_stream_path(tmp_path / "meta_dataset.parquet"),
        keep_ids=["no-such-trade"])
    assert (n_rows, n_trades) == (0, 0)
    assert dest.exists() and load_mark_stream(dest).empty


def test_write_shards_leaves_no_partial_sidecar_on_failure(tmp_path):
    rows = _rows()
    paths, _ = _shards(tmp_path, rows)
    bad = tmp_path / "ZZZ.parquet"
    pd.DataFrame({"trade_id": ["z"], "mark_ts": [pd.Timestamp("2025-01-02")],
                  "gross_return": [float("inf")]}).to_parquet(bad, index=False)
    dest = mark_stream_path(tmp_path / "meta_dataset.parquet")
    with pytest.raises(AccountingDataError, match="finite"):
        write_mark_stream_shards(paths + [bad], dest)
    assert not dest.exists()                     # tmp is never promoted
