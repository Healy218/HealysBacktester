# fa/collectors/stocktwits.py — Stage 0 collector: trending snapshots.
"""Snapshot the StockTwits trending list (free public endpoint). Each run
archives one timestamped snapshot; the time series of snapshots is what
Stage 2 turns into attention velocity. No analysis here."""
from __future__ import annotations

import pandas as pd
import requests

from fa import archive

_URL = "https://api.stocktwits.com/api/2/trending/symbols.json"
_TIMEOUT = 30


def collect() -> int:
    r = requests.get(_URL, timeout=_TIMEOUT,
                     headers={"User-Agent": "HealysBacktester-research"})
    r.raise_for_status()
    ts = pd.Timestamp.now(tz="UTC")
    rows = [{
        "ts_utc": ts,
        "rank": i + 1,
        "symbol": s.get("symbol", ""),
        "title": s.get("title", ""),
        "watchlist_count": s.get("watchlist_count"),
    } for i, s in enumerate(r.json().get("symbols", []))]
    return archive.append("stocktwits", pd.DataFrame(rows),
                          key=["ts_utc", "symbol"])
