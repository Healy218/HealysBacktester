# fa/archive.py — append-only parquet archive (FA_SPEC.md Stage 0).
"""One file per source per month: ARCHIVE/<source>/<yyyy-mm>.parquet.

Rows are only ever appended; dedupe happens on a per-source key so collectors
can overlap freely (reruns, crash-retries, fetch-both-days) without double
rows. Nothing here mutates or deletes — the archive is the point-in-time
record everything downstream trusts.
"""
from __future__ import annotations

import pandas as pd

from fa import config
from nn_meta.live.state import serialized
import os
import tempfile


@serialized(lambda source, rows, key: config.ARCHIVE / source / ".archive.lock")
def _append(source: str, rows: pd.DataFrame, key: list[str]) -> int:
    """Append `rows` to the archive for `source`, deduped on `key` columns.

    Rows must carry a `ts_utc` column (capture time); it decides the monthly
    partition. Returns the number of genuinely new rows written.
    """
    if rows.empty:
        return 0
    rows = rows.copy()
    rows["ts_utc"] = pd.to_datetime(rows["ts_utc"], utc=True)
    # Historical files may already contain cross-month duplicates. Exclude all
    # known identities before partitioning new captures; never rewrite history.
    paths = sorted((config.ARCHIVE / source).glob("*.parquet"))
    if paths:
        known = pd.concat([pd.read_parquet(p, columns=key) for p in paths], ignore_index=True)
        rows = rows.merge(known.drop_duplicates().assign(_known=True), on=key, how="left")
        rows = rows[rows["_known"].isna()].drop(columns="_known")
    rows = rows.sort_values("ts_utc").drop_duplicates(subset=key, keep="first")
    added = 0
    for month, chunk in rows.groupby(rows["ts_utc"].dt.strftime("%Y-%m")):
        path = config.ARCHIVE / source / f"{month}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            old = pd.read_parquet(path)
            merged = pd.concat([old, chunk], ignore_index=True)
            merged = merged.drop_duplicates(subset=key, keep="first")
            added += len(merged) - len(old)
        else:
            merged = chunk.drop_duplicates(subset=key, keep="first")
            added += len(merged)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        os.close(fd)
        try:
            merged.to_parquet(tmp, index=False)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    return added


def append(source: str, rows: pd.DataFrame, key: list[str]) -> int:
    """Append first captures atomically; an empty input does not touch disk."""
    return 0 if rows.empty else _append(source, rows, key)
