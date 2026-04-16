# data/alpaca_loader.py
"""
Alpaca Markets data loader.

Requires a free Alpaca paper trading account (https://alpaca.markets).
Set ALPACA_API_KEY and ALPACA_API_SECRET in your .env file or environment.

Advantages over yfinance:
  - No rate limiting on historical pulls
  - Up to 5 years of minute-bar history (SIP feed, free tier)
  - Real-time streaming available via separate websocket client
  - Splits/dividend-adjusted data via adjustment='all'
"""

import os
import pandas as pd
from utils.logging_utils import setup_logging
from utils.error_handling import DataError

logger = setup_logging(log_file="logs/backtester.log")

# Alpaca TimeFrame mapping from our standard interval strings
# Populated lazily so the import doesn't fail if alpaca-py isn't installed.
_TF_MAP = None


def _get_timeframe(interval: str):
    """Returns the alpaca-py TimeFrame object for a given interval string."""
    global _TF_MAP
    if _TF_MAP is None:
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
        _TF_MAP = {
            "1m":  TimeFrame(1,  TimeFrameUnit.Minute),
            "2m":  TimeFrame(2,  TimeFrameUnit.Minute),
            "5m":  TimeFrame(5,  TimeFrameUnit.Minute),
            "15m": TimeFrame(15, TimeFrameUnit.Minute),
            "30m": TimeFrame(30, TimeFrameUnit.Minute),
            "60m": TimeFrame(1,  TimeFrameUnit.Hour),
            "1h":  TimeFrame(1,  TimeFrameUnit.Hour),
            "1D":  TimeFrame(1,  TimeFrameUnit.Day),
            "1d":  TimeFrame(1,  TimeFrameUnit.Day),
        }
    tf = _TF_MAP.get(interval)
    if tf is None:
        raise ValueError(
            f"Unsupported interval '{interval}' for Alpaca. "
            f"Supported: {list(_TF_MAP.keys())}"
        )
    return tf


def load_alpaca_bars(
    symbol: str,
    start_date: str,
    end_date: str,
    interval: str,
    api_key: str | None = None,
    api_secret: str | None = None,
) -> pd.DataFrame:
    """
    Downloads OHLCV bars from Alpaca Markets.

    Reads API credentials from the environment if not supplied directly.
    Returns a timezone-naive DatetimeIndex DataFrame with standard OHLCV columns.

    Args:
        symbol: Ticker symbol (e.g. 'SPY').
        start_date: ISO date string 'YYYY-MM-DD'.
        end_date: ISO date string 'YYYY-MM-DD'.
        interval: Bar interval matching our standard strings ('1m', '5m', '1h', '1D', …).
        api_key: Alpaca API key (overrides env var).
        api_secret: Alpaca API secret (overrides env var).

    Returns:
        DataFrame with columns Open, High, Low, Close, Volume and timezone-naive DatetimeIndex.

    Raises:
        DataError: If credentials are missing or the download fails.
        ImportError: If alpaca-py is not installed.
    """
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from datetime import datetime
    except ImportError:
        raise ImportError(
            "alpaca-py is not installed. Run: pip install alpaca-py"
        )

    # Resolve credentials
    key    = api_key    or os.environ.get("ALPACA_API_KEY", "")
    secret = api_secret or os.environ.get("ALPACA_API_SECRET", "")

    if not key or not secret:
        raise DataError(
            "Alpaca API credentials not found. "
            "Set ALPACA_API_KEY and ALPACA_API_SECRET in your .env file."
        )

    logger.info(f"Downloading {symbol} ({interval}) from Alpaca: {start_date} -> {end_date}")

    try:
        client = StockHistoricalDataClient(key, secret)

        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=_get_timeframe(interval),
            start=datetime.fromisoformat(start_date),
            end=datetime.fromisoformat(end_date),
            # Do NOT set limit — alpaca-py treats it as total cap, not page size.
            # Omitting it lets the SDK auto-paginate and return ALL bars in range.
            # 1 year of 5-min data ≈ 20k bars; 3 years ≈ 60k bars.
            adjustment="all",   # split + dividend adjusted, same as yfinance auto_adjust=True
        )

        bars = client.get_stock_bars(request)
        df = bars.df

    except Exception as e:
        raise DataError(f"Alpaca download failed for {symbol}: {e}") from e

    if df is None or df.empty:
        raise DataError(
            f"Alpaca returned no data for {symbol} ({interval}) "
            f"{start_date}→{end_date}. Check the ticker and date range."
        )

    # Flatten MultiIndex (symbol, timestamp) → just timestamp
    if isinstance(df.index, pd.MultiIndex):
        df = df.xs(symbol, level="symbol")

    # Rename to standard OHLCV column names expected by the rest of the codebase
    df = df.rename(columns={
        "open":  "Open",
        "high":  "High",
        "low":   "Low",
        "close": "Close",
        "volume": "Volume",
    })

    # Strip timezone — simulator and cleaner both expect tz-naive DatetimeIndex
    from utils.date_utils import ensure_tz_naive
    df = ensure_tz_naive(df)

    # Keep only OHLCV columns
    available = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    df = df[available]

    logger.info(f"Alpaca download complete. Shape: {df.shape}")
    return df
