# utils/date_utils.py
"""Date and timezone helpers for the backtesting pipeline."""

from datetime import date, timedelta
from typing import Optional, Tuple
import pandas as pd


def generate_date_range(days_back: int = 365, end_date: Optional[date] = None) -> Tuple[str, str]:
    """Returns (start_iso, end_iso) for a lookback window ending today (or end_date)."""
    end = end_date or date.today()
    start = end - timedelta(days=days_back)
    return start.isoformat(), end.isoformat()


def ensure_tz_naive(df: pd.DataFrame) -> pd.DataFrame:
    """Strips timezone from a DataFrame's DatetimeIndex (no-op if already naive)."""
    if hasattr(df.index, 'tz') and df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df


def ensure_tz_aware(df: pd.DataFrame, tz: str = 'UTC') -> pd.DataFrame:
    """Adds timezone to a tz-naive DatetimeIndex (no-op if already aware)."""
    if hasattr(df.index, 'tz') and df.index.tz is None:
        df.index = df.index.tz_localize(tz)
    return df
