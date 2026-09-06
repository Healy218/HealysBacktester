"""Weekly-expiry DTE variants (user notes 2026-09-05, TODO item 5).

Most names list options monthly or on Fridays; the September 5 archive audit
identified 15 names with Monday/Wednesday/Friday expirations — three
per week. ``DTE_GRID`` (1/5/10/30/45) never targets the 2nd or 3rd expiry
of the week on those names. For pools with weekly variants enabled, such
symbols get ``DTE_GRID_WEEKLY`` appended to their DTE grid at freeze AND
build time; the ``dte`` column keeps them distinct exactly like every other
DTE, so rank/EV dedupe, fold selection and the ledger work unchanged.
``Execution.select`` already picks the listed expiry nearest a target DTE.

The weekly set is decided ONCE at freeze (from the universe listing) and
written into the spec (``spec["weekly_symbols"]``) so the build reads the
same list — point-in-time, frozen, no retroactive edits.
"""
from __future__ import annotations
from pathlib import Path

import pandas as pd

from nn_meta import config

MWF = {0, 2, 4}                         # Monday, Wednesday, Friday


def weekly_expiry_symbols(universe_parquet: Path | str = config.UNIVERSE_PARQUET,
                          *, since: str | pd.Timestamp | None = None,
                          min_per_week: float = 3.0) -> list[str]:
    """Symbols whose listed expirations include Monday, Wednesday AND Friday
    and have a median of ≥ ``min_per_week`` distinct expirations per calendar
    week over the window (default: the 180 days ending on the last listing
    date in the universe)."""
    df = pd.read_parquet(universe_parquet,
                         columns=["underlying", "expiration", "life_start"])
    df["expiration"] = pd.to_datetime(df["expiration"])
    # Anchor on the last day contracts were SEEN LISTED, not the farthest
    # expiration: the universe carries LEAPs years out (2028 on the v5
    # archive), and weeklies are only listed a few weeks ahead, so a window
    # hung off max(expiration) contains almost nothing (found 2026-09-05:
    # 0 weekly names instead of 25).
    until = pd.to_datetime(df["life_start"]).max()
    if since is None:
        since = until - pd.Timedelta(days=180)
    df = df[(df["expiration"] >= pd.Timestamp(since)) & (df["expiration"] <= until)]
    if df.empty:
        return []
    wd = df.assign(wd=df["expiration"].dt.weekday).groupby("underlying")["wd"] \
           .agg(lambda s: MWF <= set(s.unique()))
    cands = wd[wd].index
    per_week = (df[df["underlying"].isin(cands)]
                .assign(w=df["expiration"].dt.to_period("W"))
                .groupby(["underlying", "w"])["expiration"].nunique()
                .groupby("underlying").median())
    return sorted(per_week[per_week >= min_per_week].index)


def dte_grid_for(symbol: str, spec: dict | None) -> list[int]:
    """The DTE grid to freeze/build ``symbol`` at: the base grid, plus the
    weekly grid when the pool enables it and the spec lists the symbol."""
    grid = list(config.DTE_GRID)
    if config.WEEKLY_DTE_ENABLED and spec is not None \
            and symbol in set(spec.get("weekly_symbols") or []):
        grid = sorted(set(grid) | set(config.DTE_GRID_WEEKLY))
    return grid
