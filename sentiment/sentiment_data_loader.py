# sentiment/sentiment_data_loader.py
"""Fetch and cache news/sentiment data from multiple providers."""

import os
import time
import hashlib
import requests
import pandas as pd
from datetime import datetime
from utils.logging_utils import setup_logging

logger = setup_logging(log_file="logs/backtester.log")

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cache", "sentiment")
_FINNHUB_RATE_LIMIT = 60  # calls per minute
_last_finnhub_call = 0.0


def _cache_path(ticker: str, start: str, end: str, provider: str) -> str:
    """Deterministic cache file path for a given query."""
    key = f"{ticker}_{start}_{end}_{provider}"
    h = hashlib.md5(key.encode()).hexdigest()[:12]
    return os.path.join(CACHE_DIR, f"{ticker}_{provider}_{h}.csv")


def _rate_limit_finnhub():
    """Enforce Finnhub's 60 calls/min rate limit."""
    global _last_finnhub_call
    elapsed = time.time() - _last_finnhub_call
    min_interval = 60.0 / _FINNHUB_RATE_LIMIT
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    _last_finnhub_call = time.time()


def load_finnhub_news(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Fetch company news from Finnhub /company-news endpoint.

    Returns DataFrame with columns: datetime, headline, summary, source, url.
    Requires FINNHUB_API_KEY in environment (via .env).
    """
    api_key = os.environ.get("FINNHUB_API_KEY")
    if not api_key:
        raise ValueError(
            "FINNHUB_API_KEY not found in environment. "
            "Add it to your .env file: FINNHUB_API_KEY=your_key_here"
        )

    _rate_limit_finnhub()

    url = "https://finnhub.io/api/v1/company-news"
    params = {
        "symbol": ticker.upper(),
        "from": start_date,
        "to": end_date,
        "token": api_key,
    }

    logger.info(f"[Sentiment] Fetching Finnhub news for {ticker} ({start_date} -> {end_date})")
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    articles = resp.json()

    if not articles:
        logger.warning(f"[Sentiment] No news articles found for {ticker}")
        return pd.DataFrame(columns=["datetime", "headline", "summary", "source", "url"])

    rows = []
    for a in articles:
        rows.append({
            "datetime": datetime.fromtimestamp(a.get("datetime", 0)),
            "headline": a.get("headline", ""),
            "summary": a.get("summary", ""),
            "source": a.get("source", ""),
            "url": a.get("url", ""),
        })

    df = pd.DataFrame(rows)
    df = df.sort_values("datetime").reset_index(drop=True)
    logger.info(f"[Sentiment] Got {len(df)} articles for {ticker}")
    return df


def load_sentiment(
    ticker: str,
    start_date: str,
    end_date: str,
    provider: str = "finnhub",
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Dispatcher: loads news data from the specified provider.
    Caches results to CSV to avoid repeated API calls.

    To add a new provider, implement a load_<provider>_news() function
    and add it to the _PROVIDERS dict.
    """
    _PROVIDERS = {
        "finnhub": load_finnhub_news,
    }

    if provider not in _PROVIDERS:
        raise ValueError(f"Unknown sentiment provider '{provider}'. Available: {list(_PROVIDERS.keys())}")

    # Check cache
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = _cache_path(ticker, start_date, end_date, provider)

    if use_cache and os.path.exists(cache_file):
        logger.info(f"[Sentiment] Loading cached data from {cache_file}")
        df = pd.read_csv(cache_file, parse_dates=["datetime"])
        return df

    # Fetch fresh
    df = _PROVIDERS[provider](ticker, start_date, end_date)

    # Cache
    if not df.empty:
        df.to_csv(cache_file, index=False)
        logger.info(f"[Sentiment] Cached {len(df)} articles to {cache_file}")

    return df
