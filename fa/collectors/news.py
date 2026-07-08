# fa/collectors/news.py — Stage 0 collector: market-wide news + sentiment.
"""MARKET-WIDE feeds, deliberately not universe-restricted — discovery has to
be able to surface tickers we don't already trade. (The per-ticker loaders in
sentiment/sentiment_data_loader.py serve Stage 2 scoring, not this collector.)

- Finnhub /news?category=general: every run (one call; their limit is 60/min).
- AlphaVantage NEWS_SENTIMENT (no tickers param = latest market feed, includes
  per-ticker sentiment tags): only during config-listed UTC hours — the free
  tier is 25 req/day, so we take 2.
Dedupe key: (provider, url).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pandas as pd
import requests

from fa import archive

_TIMEOUT = 30
AV_HOURS_UTC = (14, 20)          # 2 AlphaVantage calls/day of the 25/day cap


def _finnhub_rows(ts: pd.Timestamp) -> list[dict]:
    key = os.environ.get("FINNHUB_API_KEY", "")
    if not key:
        return []
    r = requests.get("https://finnhub.io/api/v1/news",
                     params={"category": "general", "token": key},
                     timeout=_TIMEOUT)
    r.raise_for_status()
    return [{
        "ts_utc": ts, "provider": "finnhub",
        "published": pd.Timestamp(a.get("datetime", 0), unit="s", tz="UTC"),
        "headline": a.get("headline", ""), "source": a.get("source", ""),
        "url": a.get("url", ""), "tickers": a.get("related", ""),
        "sentiment": None,
    } for a in r.json()]


def _alphavantage_rows(ts: pd.Timestamp) -> list[dict]:
    key = os.environ.get("ALPHAVANTAGE_KEY", "")
    if not key or ts.hour not in AV_HOURS_UTC:
        return []
    r = requests.get("https://www.alphavantage.co/query",
                     params={"function": "NEWS_SENTIMENT", "limit": "1000",
                             "apikey": key},
                     timeout=_TIMEOUT)
    r.raise_for_status()
    rows = []
    for a in r.json().get("feed", []):
        try:
            pub = datetime.strptime(a.get("time_published", ""),
                                    "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        rows.append({
            "ts_utc": ts, "provider": "alphavantage",
            "published": pd.Timestamp(pub),
            "headline": a.get("title", ""), "source": a.get("source", ""),
            "url": a.get("url", ""),
            "tickers": ",".join(t.get("ticker", "")
                                for t in a.get("ticker_sentiment", [])),
            "sentiment": float(a.get("overall_sentiment_score", 0) or 0),
        })
    return rows


def collect() -> int:
    ts = pd.Timestamp.now(tz="UTC")
    rows = _finnhub_rows(ts) + _alphavantage_rows(ts)
    return archive.append("news", pd.DataFrame(rows), key=["provider", "url"])
