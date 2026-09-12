"""Purged temporal splits for labels with a future exit timestamp.

Entries alone are not sufficient to split option-trade labels: a row opened
in one period can realize its return in the next.  These helpers assign rows
only when both the decision and the final label remain inside the intended
information set.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FoldWindow:
    """One expanding fold with a train, validation, and OOS test interval."""

    train_start: pd.Timestamp
    val_start: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def _date(value: str | pd.Timestamp) -> pd.Timestamp:
    return pd.Timestamp(value).normalize()


def assign_purged_splits(rows: pd.DataFrame, *, train_start: str | pd.Timestamp,
                         val_start: str | pd.Timestamp,
                         test_start: str | pd.Timestamp,
                         test_end: str | pd.Timestamp,
                         embargo: str | pd.Timedelta = "0D") -> pd.Series:
    """Assign train/val/test while purging rows whose labels cross a boundary.

    ``entry_ts`` is the decision time and ``exit_ts`` is when the realized
    return becomes known.  An embargo removes labels ending immediately before
    the next split, reducing serial-dependence bleed at the boundary.
    """
    required = {"entry_ts", "exit_ts"}
    missing = required - set(rows.columns)
    if missing:
        raise ValueError(f"rows missing required timestamp columns: {sorted(missing)}")

    entry = pd.to_datetime(rows["entry_ts"]).dt.normalize()
    exit_ = pd.to_datetime(rows["exit_ts"]).dt.normalize()
    train_start, val_start = _date(train_start), _date(val_start)
    test_start, test_end = _date(test_start), _date(test_end)
    embargo = pd.Timedelta(embargo)
    if not train_start < val_start < test_start <= test_end:
        raise ValueError("expected train_start < val_start < test_start <= test_end")

    result = pd.Series("purged", index=rows.index, dtype="object")
    result.loc[
        (entry >= train_start) & (entry < val_start)
        & (exit_ < val_start - embargo)
    ] = "train"
    result.loc[
        (entry >= val_start) & (entry < test_start)
        & (exit_ < test_start - embargo)
    ] = "val"
    result.loc[
        (entry >= test_start) & (entry <= test_end)
        & (exit_ <= test_end)
    ] = "test"
    return result


def expanding_folds(entry_timestamps: pd.Series, *, n_folds: int = 3,
                    min_train_fraction: float = 0.5,
                    val_fraction: float = 0.2) -> list[FoldWindow]:
    """Build expanding calendar-day folds with a fold-local validation tail."""
    if not 0 < min_train_fraction < 1 or not 0 < val_fraction < 1:
        raise ValueError("min_train_fraction and val_fraction must be in (0, 1)")
    days = pd.DatetimeIndex(pd.to_datetime(entry_timestamps).to_numpy()) \
        .normalize().unique().sort_values()
    if len(days) < 4 or n_folds < 1:
        return []
    first_oos = int(len(days) * min_train_fraction)
    oos_size = max(1, (len(days) - first_oos) // n_folds)
    folds: list[FoldWindow] = []
    for i in range(n_folds):
        test_start_i = first_oos + i * oos_size
        test_end_i = (len(days) if i == n_folds - 1
                      else min(test_start_i + oos_size, len(days))) - 1
        if test_start_i >= len(days) or test_end_i < test_start_i:
            break
        val_start_i = max(1, int(test_start_i * (1 - val_fraction)))
        if val_start_i >= test_start_i:
            break
        folds.append(FoldWindow(
            train_start=days[0],
            val_start=days[val_start_i],
            test_start=days[test_start_i],
            test_end=days[test_end_i],
        ))
    return folds


def split_summary(rows: pd.DataFrame, split: pd.Series) -> pd.DataFrame:
    """Small audit table retained with every v4 experiment artifact."""
    data = rows[['entry_ts', 'exit_ts']].assign(split=split)
    return data.groupby("split", dropna=False).agg(
        rows=("split", "size"),
        first_entry=("entry_ts", "min"),
        last_entry=("entry_ts", "max"),
        first_exit=("exit_ts", "min"),
        last_exit=("exit_ts", "max"),
    ).reset_index()


def post_freeze_folds(entry_timestamps, *, frozen_until, n_folds=3, validation_days=40):
    """Predeclared expanding folds with all validation strictly after freeze.

    Reserve the first 40 observed post-freeze sessions for validation, then
    partition the remaining sessions into disjoint tests. Each later fold
    expands training and uses the preceding 40 sessions for validation.
    Exit-time purge and embargo are still applied by the evaluator.
    """
    if n_folds < 1 or validation_days < 1:
        raise ValueError('Positive fold and validation lengths required')
    days = pd.DatetimeIndex(pd.to_datetime(entry_timestamps)).normalize().unique().sort_values()
    after = days[days > _date(frozen_until)]
    if len(after) < validation_days + n_folds * 20:
        raise ValueError('Need at least 20 observed test sessions per post-freeze fold')
    tests = np.array_split(np.arange(validation_days, len(after)), n_folds)
    return [FoldWindow(days[0], after[int(t[0])-validation_days], after[int(t[0])], after[int(t[-1])])
            for t in tests]
