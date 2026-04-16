# sentiment/sentiment_filter.py
"""Optional sentiment overlay that gates entries on existing strategies."""

import pandas as pd
from utils.logging_utils import setup_logging

logger = setup_logging(log_file="logs/backtester.log")


def apply_sentiment_filter(
    entries_df: pd.DataFrame,
    sentiment_series: pd.Series,
    min_sentiment: float = 0.1,
) -> pd.DataFrame:
    """
    Masks out entries where smoothed sentiment is below min_sentiment.

    Args:
        entries_df: Boolean entry signals (any shape/MultiIndex).
        sentiment_series: Time-indexed sentiment scores, aligned to price data.
        min_sentiment: Minimum sentiment to allow a long entry.

    Returns:
        Filtered entries_df with same shape — entries below threshold become False.
    """
    # Align sentiment to entries index
    sentiment_aligned = sentiment_series.reindex(entries_df.index, method="ffill").fillna(0.0)

    # Build mask: True where sentiment is bullish enough
    mask = sentiment_aligned >= min_sentiment

    filtered = entries_df.where(mask.values[:, None], other=False)

    n_before = entries_df.sum().sum()
    n_after = filtered.sum().sum()
    logger.info(
        f"[Sentiment Filter] Entries: {int(n_before)} -> {int(n_after)} "
        f"(filtered {int(n_before - n_after)} sub-threshold entries)"
    )
    return filtered
