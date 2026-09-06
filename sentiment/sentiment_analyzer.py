# sentiment/sentiment_analyzer.py
"""Score news headlines and aggregate into time-aligned sentiment signals."""

from typing import List, Tuple
import numpy as np
import pandas as pd
from utils.logging_utils import setup_logging

logger = setup_logging(log_file="logs/backtester.log")

# Lazy-load VADER to avoid import overhead when not using sentiment
_vader = None


def _get_vader():
    """Lazy-initialize VADER sentiment analyzer."""
    global _vader
    if _vader is None:
        import nltk
        from nltk.sentiment.vader import SentimentIntensityAnalyzer
        try:
            _vader = SentimentIntensityAnalyzer()
        except LookupError:
            nltk.download('vader_lexicon', quiet=True)
            _vader = SentimentIntensityAnalyzer()
    return _vader


def analyze_sentiment(headlines: List[str]) -> np.ndarray:
    """
    Score a list of headlines using VADER.
    Returns array of compound scores in [-1, 1].
    """
    sia = _get_vader()
    scores = np.array([sia.polarity_scores(h)["compound"] for h in headlines])
    return scores


def aggregate_sentiment(
    news_df: pd.DataFrame,
    freq: str = "1D",
) -> pd.Series:
    """
    Score headlines in news_df and aggregate to a time-aligned sentiment Series.

    Args:
        news_df: DataFrame with 'datetime' and 'headline' columns
                 (as returned by sentiment_data_loader).
        freq: Resampling frequency to match price data ('1D', '1h', '5min', etc.).

    Returns:
        pd.Series with DatetimeIndex and mean compound sentiment per period.
        Periods with no news get score 0.0 (neutral).
    """
    if news_df.empty:
        logger.warning("[Sentiment] Empty news DataFrame — returning empty Series")
        return pd.Series(dtype=float)

    df = news_df.copy()

    # Use pre-computed scores from Alpha Vantage if available, otherwise VADER
    if "sentiment_score" in df.columns:
        df["score"] = df["sentiment_score"].astype(float)
        logger.info("[Sentiment] Using provider-supplied sentiment scores")
    else:
        df["score"] = analyze_sentiment(df["headline"].tolist())
        logger.info("[Sentiment] Scored headlines with VADER")

    df = df.set_index("datetime")
    df.index = pd.to_datetime(df.index)

    # Resample: mean sentiment per period, fill gaps with 0 (neutral)
    sentiment = df["score"].resample(freq, closed="right", label="right").mean().fillna(0.0)
    sentiment.name = "sentiment"

    logger.info(
        f"[Sentiment] Aggregated {len(news_df)} headlines -> "
        f"{len(sentiment)} periods ({freq}), "
        f"mean={sentiment.mean():.3f}"
    )
    return sentiment
