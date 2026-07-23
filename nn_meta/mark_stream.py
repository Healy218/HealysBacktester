"""Per-contract 15-minute mark stream: schema, IO, and the bridge into the
v4 mark-to-market ledger.

The v31 label builder does not yet persist intratrade option marks, so this
module defines the canonical sidecar format and a deterministic key so a mark
stream produced later can be attached to meta-dataset rows without a shared
``trade_id`` column.  Until a real stream exists it is exercised with synthetic
fixtures; the ledger in :mod:`nn_meta.v4_accounting` fails closed when marks are
absent or incomplete, so a report is only marked-to-market when a stream is
actually supplied.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from nn_meta.v4_accounting import AccountingDataError

MARK_STREAM_COLUMNS = ("trade_id", "mark_ts", "gross_return")
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
    Neither is present on the committed v31 dataset — producing them requires
    re-running the label builder over the raw 15-minute option bars, not a code
    change here, and the ledger deliberately refuses to synthesize marks from
    the final ``net_return``.
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
    """Normalize a mark stream and fail closed on a malformed one."""
    missing = set(MARK_STREAM_COLUMNS) - set(marks.columns)
    if missing:
        raise AccountingDataError(f"mark stream missing columns: {sorted(missing)}")
    out = marks.loc[:, list(MARK_STREAM_COLUMNS)].copy()
    out["mark_ts"] = pd.to_datetime(out["mark_ts"])
    out["gross_return"] = out["gross_return"].astype(float)
    if not np.isfinite(out["gross_return"].to_numpy()).all():
        raise AccountingDataError("mark stream gross_return must be finite")
    if out.duplicated(["trade_id", "mark_ts"]).any():
        raise AccountingDataError("mark stream has duplicate (trade_id, mark_ts)")
    return out.sort_values(["trade_id", "mark_ts"]).reset_index(drop=True)


def load_mark_stream(path: str | Path) -> pd.DataFrame:
    """Read and validate a persisted mark stream."""
    return validate_mark_stream(pd.read_parquet(path))


def write_mark_stream(marks: pd.DataFrame, path: str | Path) -> Path:
    """Validate and persist a mark stream to ``path``."""
    out = validate_mark_stream(marks)
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(dest, index=False)
    return dest


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
    marks = validate_mark_stream(mark_stream)
    marks = marks[marks["trade_id"].isin(set(tid))].reset_index(drop=True)
    return trades, marks
