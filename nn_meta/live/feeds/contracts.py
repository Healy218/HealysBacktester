"""Resolve an alert's advisory "~ATM, ~N DTE" contract to a listed OCC symbol.

The experts alert on an underlying + right + spot + target DTE; nothing in the
alert path ever chose a real contract, so the OPRA quote stream had nothing to
subscribe to (2026-09-08 review, fix 1). This picks, from the pool's cached
contract listing (``config.CONTRACTS_PARQUET``: ticker, underlying, strike,
expiration, type), the expiration nearest the target date that is still at
least ``min_dte`` out, then the strike nearest spot.

Read-only and cached per process; returns None when the listing is missing or
has nothing usable — callers treat that as "no streamed quote for this one".
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd

from nn_meta import config

_COLS = ["ticker", "underlying", "strike", "expiration", "type"]


@lru_cache(maxsize=4)
def _listing(path: str, mtime_ns: int) -> pd.DataFrame:
    df = pd.read_parquet(path, columns=_COLS)
    df["expiration"] = pd.to_datetime(df["expiration"]).dt.normalize()
    df["type"] = df["type"].astype(str).str.lower().str[0]     # call/put → c/p
    return df


def load_listing(path: Optional[Path] = None) -> Optional[pd.DataFrame]:
    p = Path(path) if path is not None else config.CONTRACTS_PARQUET
    if not p.exists():
        return None
    return _listing(str(p), p.stat().st_mtime_ns)


def resolve_occ(symbol: str, right: str, spot: float, dte: int, now=None, *,
                listing: Optional[pd.DataFrame] = None, min_dte: int = 1) -> Optional[str]:
    """OCC symbol (no ``O:`` prefix) of the listed contract closest to the
    alert's ~ATM strike and ~``dte`` expiry, or None."""
    now = now or datetime.now(timezone.utc)
    today = pd.Timestamp(now).tz_convert("UTC").normalize().tz_localize(None) \
        if pd.Timestamp(now).tzinfo else pd.Timestamp(now).normalize()
    df = listing if listing is not None else load_listing()
    if df is None or df.empty:
        return None
    r = str(right).upper()[:1].lower()
    cand = df[(df["underlying"] == str(symbol).upper()) & (df["type"] == r)
              & (df["expiration"] >= today + timedelta(days=min_dte))]
    if cand.empty:
        return None
    target = today + timedelta(days=int(dte))
    gap = (cand["expiration"] - target).abs()
    cand = cand[gap == gap.min()]
    cand = cand.iloc[(cand["strike"] - float(spot)).abs().argsort()]
    ticker = str(cand.iloc[0]["ticker"])
    return ticker.removeprefix("O:").upper()
