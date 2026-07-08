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


def append(source: str, rows: pd.DataFrame, key: list[str]) -> int:
    """Append `rows` to the archive for `source`, deduped on `key` columns.

    Rows must carry a `ts_utc` column (capture time); it decides the monthly
    partition. Returns the number of genuinely new rows written.
    """
    if rows.empty:
        return 0
    rows = rows.copy()
    rows["ts_utc"] = pd.to_datetime(rows["ts_utc"], utc=True)
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
        merged.to_parquet(path, index=False)
    return added
