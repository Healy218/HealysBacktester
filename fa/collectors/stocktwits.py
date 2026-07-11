# fa/collectors/stocktwits.py — Stage 0 collector: trending + sentiment tags.
"""Two archives per run (Cloudflare 403s datacenter IPs — HOME BOX ONLY,
which then pushes to the server):

- "stocktwits": the trending-list snapshot (rank, watchlist_count) → attention.
- "stocktwits_sentiment": per-symbol Bullish/Bearish MESSAGE-TAG counts from
  the symbol stream → the clean directional signal reddit keywords only fake.
  Collected for the trending equities ∪ our core scanner universe, capped to
  stay well under StockTwits' ~200 req/hr unauth budget.

No analysis here — Stage 2 turns the snapshot series into velocity + net lean.
"""
from __future__ import annotations

import time

import pandas as pd
import requests

from fa import archive
from nn_meta.config import UNDERLYINGS as CORE_UNIVERSE

_TREND_URL = "https://api.stocktwits.com/api/2/trending/symbols.json"
_STREAM_URL = "https://api.stocktwits.com/api/2/streams/symbol/{sym}.json"
_TIMEOUT = 30
_HEADERS = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/126.0 Safari/537.36"),
            "Accept": "application/json"}
MAX_SENTIMENT_SYMBOLS = 60          # ~60 stream calls/run << 200/hr budget


def _is_equity(sym: str) -> bool:
    """Drop crypto (.X), forex pairs, and index/futures — options only."""
    return sym.isalpha() and 1 <= len(sym) <= 5


def _trending(session) -> list[dict]:
    r = session.get(_TREND_URL, headers=_HEADERS, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json().get("symbols", [])


def _sentiment(session, sym: str) -> dict | None:
    try:
        r = session.get(_STREAM_URL.format(sym=sym), headers=_HEADERS,
                        timeout=_TIMEOUT)
        if not r.ok:
            return None
        msgs = r.json().get("messages", [])
    except requests.RequestException:
        return None
    bull = bear = 0
    for m in msgs:
        basic = (m.get("entities", {}).get("sentiment") or {}).get("basic")
        bull += basic == "Bullish"
        bear += basic == "Bearish"
    return {"bull": bull, "bear": bear, "n_msgs": len(msgs)}


def collect() -> int:
    session = requests.Session()
    ts = pd.Timestamp.now(tz="UTC")

    trend = _trending(session)
    snap = [{"ts_utc": ts, "rank": i + 1, "symbol": s.get("symbol", ""),
             "title": s.get("title", ""),
             "watchlist_count": s.get("watchlist_count")}
            for i, s in enumerate(trend)]
    n = archive.append("stocktwits", pd.DataFrame(snap),
                       key=["ts_utc", "symbol"])

    # sentiment for: trending equities first, then core universe, capped
    trending_eq = [s["symbol"] for s in trend if _is_equity(s.get("symbol", ""))]
    watch = list(dict.fromkeys(trending_eq + list(CORE_UNIVERSE)))[:MAX_SENTIMENT_SYMBOLS]
    rows = []
    for sym in watch:
        s = _sentiment(session, sym)
        if s and s["n_msgs"]:
            rows.append({"ts_utc": ts, "symbol": sym, **s})
        time.sleep(0.4)                 # polite pacing under the rate budget
    n += archive.append("stocktwits_sentiment", pd.DataFrame(rows),
                        key=["ts_utc", "symbol"])
    return n
