# fa/collectors/stocktwits.py — Stage 0 collector: trending snapshots.
"""Snapshot the StockTwits trending list + per-ticker message volume and
bull/bear tags (free public endpoints). Archive rows: ts_utc, rank, symbol,
watchlist_count, message_volume, sentiment_tag."""


def collect() -> int:
    raise NotImplementedError("FA Stage 0 — see FA_SPEC.md")
