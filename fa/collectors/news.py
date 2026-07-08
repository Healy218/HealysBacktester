# fa/collectors/news.py — Stage 0 collector: news + provider sentiment.
"""Finnhub + AlphaVantage news sentiment (keys already in .env; see the
existing loaders in sentiment/sentiment_data_loader.py — reuse, don't rewrite).
Archive rows: ts_utc, provider, symbol, headline, url, provider_sentiment."""


def collect() -> int:
    raise NotImplementedError("FA Stage 0 — see FA_SPEC.md")
