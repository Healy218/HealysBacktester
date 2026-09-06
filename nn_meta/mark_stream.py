"""Per-contract 15-minute mark stream: schema, IO, and the bridge into the
v4 mark-to-market ledger.

This module defines the canonical sidecar format and a deterministic key, so a
mark stream attaches to meta-dataset rows without a shared ``trade_id`` column.
:func:`marks_from_blotter` builds one from an executor run
(``build_meta_dataset --marks``); the ledger in :mod:`nn_meta.v4_accounting`
still fails closed when marks are absent or incomplete, so a report is only
marked-to-market when a stream is actually supplied.

Note the committed v31 ``meta_dataset.parquet`` predates both this and the
execution-provenance columns, so Option B stays blocked until the dataset is
rebuilt — that is a compute job now, not a code gap.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from nn_meta.v4_accounting import AccountingDataError

MARK_STREAM_COLUMNS = ("trade_id", "mark_ts", "gross_return")
COST_COLUMNS = ("cost_entries", "cost_exits")
PERSISTED_COLUMNS = (*MARK_STREAM_COLUMNS, *COST_COLUMNS)
# On-disk schema.  ``trade_id`` is a plain string so any reader works; parquet
# dictionary-encodes it per row group, and our own loader reads it back
# dictionary-encoded (see load_mark_stream) to keep a full stream in memory.
_ARROW_SCHEMA = pa.schema([("trade_id", pa.string()),
                           ("mark_ts", pa.timestamp("ns")),
                           ("gross_return", pa.float64()),
                           ("cost_entries", pa.int16()), ("cost_exits", pa.int16())])
# Identity columns that make a meta-dataset row unique.  A mark stream keyed by
# the hash of these can be joined to dataset rows regardless of row order.
KEY_COLUMNS = ("symbol", "strategy", "trade_idx", "dte", "entry_ts")
# Per-row execution-provenance columns the ledger needs (see execution_frames).
# The v31 label builder does not yet emit these, which is one half of why
# Option B (mark-to-market selection) cannot run on the committed dataset.
EXECUTION_PROVENANCE_COLUMNS = ("fill_entry_ts", "fill_exit_ts", "gross_return")


def option_b_blockers(dataset_columns, *, mark_stream_exists: bool) -> list[str]:
    """Human-readable reasons Option B (mark-to-market accounting) cannot run.

    Empty list == ready. Both halves must hold: the dataset rows must carry the
    execution-provenance columns AND a per-contract mark stream must exist.
    Neither is present on the committed v31 dataset, which predates both; both
    are produced by ``build_meta_dataset --marks``, so clearing this is a
    dataset rebuild.  The ledger still refuses to synthesize marks from the
    final ``net_return``.
    """
    cols = set(dataset_columns)
    blockers = []
    missing = [c for c in EXECUTION_PROVENANCE_COLUMNS if c not in cols]
    if missing:
        blockers.append(
            f"dataset lacks execution-provenance columns {missing} — rebuild the "
            "meta dataset with fill timestamps + gross_return")
    if not mark_stream_exists:
        blockers.append(
            "no per-contract 15m mark stream — emit one from the label builder "
            "(raw option bars) and pass it via --marks")
    return blockers


def marks_from_legs(legs: list[dict]) -> pd.DataFrame:
    """Per-bar gross return for one trade, chained across its roll legs.

    ``legs`` are one trade's blotter entries in fill order, each carrying the
    ``bar_ts``/``bar_close`` arrays that :func:`options.execution.execute_variant`
    attaches under ``collect_marks``.  A rolled trade holds one contract at a
    time, so the position's growth at a bar in leg *k* is every completed leg's
    growth times the open leg's mark against its own entry::

        gross_return(t) = Π_{j<k} (exit_close_j / entry_open_j)
                          · (close_t / entry_open_k) − 1

    Each leg emits a separate OPEN event followed by actual CLOSE timestamps.
    The first event has zero gross return; the first close retains the entry
    bar's move. Costs remain scenario-independent: cumulative entry/exit
    counters let the ledger charge every roll at the chosen scenario.

    Returns mark_ts, gross_return, cost_entries, cost_exits; the caller attaches
    trade_id. Legacy sidecars without fill-event counters must be rebuilt.
    """
    frames = []
    completed_growth = 1.0
    for i, leg in enumerate(legs):
        if "bar_close" not in leg or "bar_ts" not in leg:
            raise AccountingDataError(
                "blotter leg has no bars — execute with collect_marks=True")
        if "bar_close_ts" not in leg:
            raise AccountingDataError("legacy blotter lacks close-time provenance; rebuild marks")
        entry_open = float(leg["entry_open"])
        if not np.isfinite(entry_open) or entry_open <= 0:
            raise AccountingDataError(
                f"leg {leg.get('contract')} has non-positive entry_open {entry_open}")
        closes = np.asarray(leg["bar_close"], dtype=float)
        times = pd.to_datetime(leg["bar_close_ts"])
        starts = pd.to_datetime(leg["bar_ts"])
        if len(times) != len(closes) or len(times) == 0 or not (times > starts).all():
            raise AccountingDataError("bar close timestamps must follow bar opens")
        # The entry-open event is separate from its first close. Counters
        # preserve every roll haircut without baking a cost scenario into marks.
        frames.append(pd.DataFrame({"mark_ts": [starts[0]],
                                    "gross_return": [completed_growth - 1],
                                    "cost_entries": [i + 1], "cost_exits": [i]}))
        exits = np.full(len(closes), i, dtype=int)
        exits[-1] = i + 1
        frames.append(pd.DataFrame({"mark_ts": times,
                                    "gross_return": completed_growth * closes / entry_open - 1,
                                    "cost_entries": i + 1, "cost_exits": exits}))
        completed_growth *= float(leg["exit_close"]) / entry_open
    if not frames:
        return pd.DataFrame(columns=["mark_ts", "gross_return", *COST_COLUMNS])
    out = pd.concat(frames, ignore_index=True)
    # Roll boundaries can repeat a timestamp (old leg's last bar, new leg's
    # first); the open leg's mark is the live one, so the later wins.
    out = out.drop_duplicates("mark_ts", keep="last")
    return out.sort_values("mark_ts").reset_index(drop=True)


def marks_from_blotter(blotter: dict[int, list[dict]],
                       trade_ids: dict[int, str]) -> pd.DataFrame:
    """Assemble a full mark stream from one executor run.

    ``blotter`` is ``meta["blotter"]`` (trade_idx → legs); ``trade_ids`` maps
    trade_idx → the :func:`stable_trade_id` of the dataset row it produced.
    Trades absent from ``trade_ids`` are skipped — an unlabeled or dropped row
    has no ledger entry to reconcile against.
    """
    frames = []
    for trade_idx, legs in blotter.items():
        tid = trade_ids.get(int(trade_idx))
        if tid is None:
            continue
        m = marks_from_legs(legs)
        if m.empty:
            continue
        m.insert(0, "trade_id", tid)
        frames.append(m)
    if not frames:
        return pd.DataFrame({c: [] for c in PERSISTED_COLUMNS})
    return validate_mark_stream(pd.concat(frames, ignore_index=True))


def mark_stream_path(dataset_path: str | Path) -> Path:
    """Canonical sidecar path for the mark stream beside a meta dataset."""
    p = Path(dataset_path)
    return p.with_suffix(".marks.parquet")


def stable_trade_id(rows: pd.DataFrame) -> pd.Series:
    """Deterministic per-row trade id built from the identity columns.

    The meta dataset has no ``trade_id``; a mark stream keyed by this id can be
    joined to dataset rows regardless of order.  ``entry_ts`` is folded in as
    integer nanoseconds so equal (symbol, strategy, trade_idx, dte) rows on
    different bars remain distinct.
    """
    missing = set(KEY_COLUMNS) - set(rows.columns)
    if missing:
        raise AccountingDataError(f"cannot key marks: rows missing {sorted(missing)}")
    entry_ns = pd.to_datetime(rows["entry_ts"]).astype("int64").astype(str)
    parts = (rows["symbol"].astype(str) + "|" + rows["strategy"].astype(str) + "|"
             + rows["trade_idx"].astype("int64").astype(str) + "|"
             + rows["dte"].astype("int64").astype(str) + "|" + entry_ns)
    return pd.Series(parts.to_numpy(), index=rows.index, name="trade_id")


def validate_mark_stream(marks: pd.DataFrame) -> pd.DataFrame:
    """Normalize a mark stream and fail closed on a malformed one.

    ``trade_id`` is held as a categorical: the stream has ~180 marks per trade,
    so at v31 scale (~88M rows over ~490k trades) the string ids alone are ~7.5
    GB as objects versus ~0.4 GB as dictionary codes.  Its categories are pinned
    in lexical order, because a categorical sorts by category order and parquet
    hands dictionaries back in first-appearance order — without this the sort
    below would depend on how the stream happened to be assembled.
    """
    missing = set(MARK_STREAM_COLUMNS) - set(marks.columns)
    if missing:
        raise AccountingDataError(f"mark stream missing columns: {sorted(missing)}")
    cost_cols = [c for c in COST_COLUMNS if c in marks]
    if cost_cols and len(cost_cols) != len(COST_COLUMNS):
        raise AccountingDataError("incomplete cost-event provenance")
    out = marks.loc[:, [*MARK_STREAM_COLUMNS, *cost_cols]].copy()
    tid = out["trade_id"]
    if not isinstance(tid.dtype, pd.CategoricalDtype):
        tid = tid.astype("category")
    if not tid.cat.categories.is_monotonic_increasing:
        tid = tid.cat.reorder_categories(sorted(tid.cat.categories))
    out["trade_id"] = tid
    out["mark_ts"] = pd.to_datetime(out["mark_ts"])
    out["gross_return"] = out["gross_return"].astype(float)
    if not np.isfinite(out["gross_return"].to_numpy()).all():
        raise AccountingDataError("mark stream gross_return must be finite")
    for col in cost_cols:
        values = pd.to_numeric(out[col], errors="coerce")
        if values.isna().any() or (values < 0).any() or (values > 32767).any() or (values != np.floor(values)).any():
            raise AccountingDataError("invalid cumulative fill cost counter")
        out[col] = values.astype("int16")
    if out.duplicated(["trade_id", "mark_ts"]).any():
        raise AccountingDataError("mark stream has duplicate (trade_id, mark_ts)")
    return out.sort_values(["trade_id", "mark_ts"]).reset_index(drop=True)


def load_mark_stream(path: str | Path) -> pd.DataFrame:
    """Read and validate a persisted mark stream.

    ``trade_id`` is read back dictionary-encoded rather than as loose strings,
    which is what keeps a full-stream load off the ~9 GB path.
    """
    table = pq.read_table(path, read_dictionary=["trade_id"])
    if not set(COST_COLUMNS).issubset(table.column_names):
        raise AccountingDataError("legacy mark stream lacks fill-event provenance; rebuild dataset and marks")
    return validate_mark_stream(table.to_pandas())


def write_mark_stream(marks: pd.DataFrame, path: str | Path) -> Path:
    """Validate and persist an in-memory mark stream to ``path``.

    For a full-universe stream use :func:`write_mark_stream_shards` instead —
    this one holds the whole frame at once.
    """
    out = validate_mark_stream(marks)
    if not set(COST_COLUMNS).issubset(out):
        raise AccountingDataError("cannot persist legacy marks without fill-event provenance")
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(dest, index=False)
    return dest


def write_mark_stream_shards(shard_paths, path: str | Path, *,
                             keep_ids=None) -> tuple[Path, int, int]:
    """Concatenate per-symbol mark shards into one sidecar, a shard at a time.

    The full v31 stream is ~88M rows; concatenating every shard into one frame
    before writing peaks near 9 GB — more than the build box has, and it would
    fail at the very end of a multi-hour build.  Each shard is instead
    validated, filtered to ``keep_ids`` and appended as its own parquet row
    group, so peak memory is one symbol (~90 MB) and each row group carries its
    own string dictionary.

    ``keep_ids`` (typically :func:`stable_trade_id` over the assembled dataset)
    drops marks for rows the split purge removed.  Returns
    ``(dest, n_rows, n_trades)``.
    """
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp")
    keep = None if keep_ids is None else set(keep_ids)
    writer = None
    n_rows, seen = 0, set()
    try:
        for shard in shard_paths:
            df = pd.read_parquet(shard)
            if df.empty:
                continue
            df = validate_mark_stream(df)
            if keep is not None:
                df = df[df["trade_id"].isin(keep)]
                if df.empty:
                    continue
            seen.update(df["trade_id"].unique().tolist())
            if writer is None:
                writer = pq.ParquetWriter(tmp, _ARROW_SCHEMA)
            writer.write_table(
                pa.Table.from_pandas(df, preserve_index=False).cast(_ARROW_SCHEMA))
            n_rows += len(df)
    finally:
        if writer is not None:
            writer.close()
    if writer is None:                    # no shard survived — still write a stream
        tmp.unlink(missing_ok=True)
        return write_mark_stream(
            pd.DataFrame({c: [] for c in PERSISTED_COLUMNS}), dest), 0, 0
    tmp.replace(dest)                     # atomic: no half-written sidecar
    return dest, n_rows, len(seen)


def execution_frames(selected: pd.DataFrame, mark_stream: pd.DataFrame, *,
                     return_col: str = "gross_return"
                     ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Convert selected meta-dataset rows plus a mark stream into the trades and
    marks frames the mark-to-market ledger consumes.

    ``signal_ts`` is the signal-close bar (``entry_ts``); the fill occurs on the
    next bar (``fill_entry_ts``), so the causal ``fill_entry_ts > signal_ts``
    contract holds.  A trade's ``gross_return`` uses the persisted execution
    return, not the final ``net_return`` (which already embeds costs the ledger
    re-applies).  Marks are filtered to the selected trades; the ledger then
    asserts each has an entry and exit mark.
    """
    for col in ("fill_entry_ts", "fill_exit_ts", return_col):
        if col not in selected.columns:
            raise AccountingDataError(f"selected rows missing execution column '{col}'")
    tid = stable_trade_id(selected)
    if tid.duplicated().any():
        raise AccountingDataError("selected rows are not unique under the mark key")
    trades = pd.DataFrame({
        "trade_id": tid.to_numpy(),
        "symbol": selected["symbol"].to_numpy(),
        "signal_ts": pd.to_datetime(selected["entry_ts"]).to_numpy(),
        "fill_entry_ts": pd.to_datetime(selected["fill_entry_ts"]).to_numpy(),
        "fill_exit_ts": pd.to_datetime(selected["fill_exit_ts"]).to_numpy(),
        "gross_return": selected[return_col].astype(float).to_numpy(),
    })
    if "size_fraction" in selected.columns:      # v4 EV sizing rides along
        trades["size_fraction"] = selected["size_fraction"].astype(float).to_numpy()
    if "n_fills" in selected:
        trades["n_fills"] = selected["n_fills"].to_numpy()
    # load_mark_stream validated the full universe once. Copy/sort only the
    # selected subset here; a policy grid must not repeatedly sort 88M rows.
    marks = validate_mark_stream(mark_stream.loc[mark_stream["trade_id"].isin(set(tid))])
    # Drop the unselected ids from the dictionary too — otherwise every grouped
    # operation downstream still carries the whole universe's categories.
    marks["trade_id"] = marks["trade_id"].cat.remove_unused_categories()
    if "spx0_short" in selected:
        from nn_meta.spx0.costs import ledger_cost_paths
        marks, entry_turnover = ledger_cost_paths(selected, marks)
        trades = trades.join(entry_turnover, on="trade_id")
        trades["cost_model"] = "index_dollar"
    return trades, marks
