# data/vbt_data_loader.py
"""
vectorBT-native data loader — Alpaca only.

Market data comes exclusively from Alpaca (via vbt.AlpacaData). There is no
Yahoo Finance fallback: if Alpaca lacks credentials, doesn't support the
requested interval, or returns no data, the loader returns None and logs a
clear error rather than silently substituting a different data source.

Priority:
  1. Local CSV cache (instant)
  2. Alpaca Markets via vbt.AlpacaData

The public API mirrors data_loader.load_price_data_smart() so runners
can swap imports without any other code changes.
"""

import os
import pandas as pd
import vectorbt as vbt
from utils.logging_utils import setup_logging
from utils.error_handling import handle_errors

logger = setup_logging(log_file="logs/backtester.log")


# ---------------------------------------------------------------------------
# Interval mapping for vectorBT's AlpacaData
# ---------------------------------------------------------------------------
_VBT_ALPACA_INTERVAL_MAP = {
    "1m": "1m", "2m": "2m", "5m": "5m", "15m": "15m", "30m": "30m",
    "60m": "1h", "1h": "1h",
    "1D": "1d", "1d": "1d",
}


def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalizes a DataFrame from any vbt Data source to standard OHLCV format:
    - Capitalize column names (Open, High, Low, Close, Volume)
    - Strip timezone from index
    - Keep only OHLCV columns
    """
    if df is None or df.empty:
        return df

    # Handle MultiIndex index (vbt.AlpacaData returns (symbol, timestamp))
    if isinstance(df.index, pd.MultiIndex):
        # Drop the symbol level, keep the timestamp level
        ts_level = None
        for i, name in enumerate(df.index.names):
            if name and "time" in str(name).lower():
                ts_level = i
                break
        if ts_level is not None:
            df = df.droplevel([j for j in range(df.index.nlevels) if j != ts_level])
        else:
            # Fallback: assume last level is the timestamp
            df = df.droplevel(list(range(df.index.nlevels - 1)))

    # Handle MultiIndex columns (vbt sometimes returns (col, symbol))
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Standardize column names
    col_map = {}
    for col in df.columns:
        lower = str(col).lower()
        if lower == "open":
            col_map[col] = "Open"
        elif lower == "high":
            col_map[col] = "High"
        elif lower == "low":
            col_map[col] = "Low"
        elif lower == "close":
            col_map[col] = "Close"
        elif lower == "volume":
            col_map[col] = "Volume"
    if col_map:
        df = df.rename(columns=col_map)

    # Strip timezone
    if isinstance(df.index, pd.DatetimeIndex) and df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    # Keep only OHLCV
    keep = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    return df[keep]


def _download_vbt_alpaca(
    symbol: str, start_date: str, end_date: str, interval: str
) -> pd.DataFrame | None:
    """Downloads data via vbt.AlpacaData.download(). Returns DataFrame or None."""
    vbt_interval = _VBT_ALPACA_INTERVAL_MAP.get(interval)
    if vbt_interval is None:
        logger.debug(f"Interval '{interval}' not supported by Alpaca via vbt. Skipping.")
        return None

    # vbt.AlpacaData reads credentials from vbt.settings, not from env vars.
    # Push env vars into vbt settings before each call.
    api_key = os.environ.get("ALPACA_API_KEY", "")
    api_secret = os.environ.get("ALPACA_API_SECRET", "")
    if not api_key or not api_secret:
        logger.debug("Alpaca credentials not found in environment. Skipping vbt.AlpacaData.")
        return None

    try:
        vbt.settings['data']['alpaca']['api_key'] = api_key
        vbt.settings['data']['alpaca']['secret_key'] = api_secret

        data = vbt.AlpacaData.download(
            symbol,
            start=start_date,
            end=end_date,
            timeframe=vbt_interval,
            limit=10000,  # max bars per page (API default is 1000)
        )
        df = data.get()
        if df is None or df.empty:
            logger.warning(f"vbt.AlpacaData returned empty data for {symbol}.")
            return None
        return _normalize_ohlcv(df)
    except Exception as e:
        logger.warning(f"vbt.AlpacaData failed for {symbol}: {e}")
        return None


@handle_errors
def load_price_data_smart(
    symbol: str,
    start_date: str,
    end_date: str,
    interval: str,
    cache_dir: str = "data/cache",
    force_download: bool = False,
) -> pd.DataFrame | None:
    """
    Alpaca-only data loader using vectorBT's data classes.

    Drop-in replacement for data_loader.load_price_data_smart().
    Same signature, same return type.

    Priority:
      1. Local CSV cache (instant)
      2. vbt.AlpacaData

    Returns None (with a clear logged error) if Alpaca credentials are missing,
    the interval is unsupported by Alpaca, or Alpaca returns no data. There is
    no Yahoo Finance fallback.

    Args:
        symbol: Ticker symbol (e.g. 'SPY').
        start_date: Start date 'YYYY-MM-DD'.
        end_date: End date 'YYYY-MM-DD'.
        interval: Bar interval ('1m', '5m', '1h', '1D', ...).
        cache_dir: Local cache directory.
        force_download: Skip cache and always fetch fresh data.

    Returns:
        OHLCV DataFrame or None on failure.
    """
    os.makedirs(cache_dir, exist_ok=True)

    safe_symbol = symbol.replace("/", "_")
    cache_filename = f"{safe_symbol}_{interval}_{start_date}_{end_date}.csv"
    cache_filepath = os.path.join(cache_dir, cache_filename)

    # 1. Cache check
    if not force_download and os.path.exists(cache_filepath):
        logger.info(f"[vbt-smart] Cache hit: {cache_filepath}")
        try:
            df = pd.read_csv(cache_filepath, index_col=0, parse_dates=True)
            if not df.empty and isinstance(df.index, pd.DatetimeIndex):
                return df
        except Exception as e:
            logger.warning(f"[vbt-smart] Cache read failed: {e}. Re-downloading.")

    # 2. Alpaca — the ONLY remote source (hard Alpaca-only policy; no Yahoo fallback)
    if not os.environ.get("ALPACA_API_KEY") or not os.environ.get("ALPACA_API_SECRET"):
        logger.error(
            f"[vbt-smart] Alpaca credentials missing — set ALPACA_API_KEY and "
            f"ALPACA_API_SECRET (check your .env). Cannot load {symbol}."
        )
        return None

    if _VBT_ALPACA_INTERVAL_MAP.get(interval) is None:
        logger.error(
            f"[vbt-smart] Interval '{interval}' is not supported by Alpaca. "
            f"Supported intervals: {sorted(set(_VBT_ALPACA_INTERVAL_MAP))}."
        )
        return None

    logger.info(f"[vbt-smart] Loading {symbol} ({interval}) from Alpaca…")
    df = _download_vbt_alpaca(symbol, start_date, end_date, interval)
    if df is not None and not df.empty:
        _cache_df(df, cache_filepath)
        return df

    logger.error(
        f"[vbt-smart] Alpaca returned no data for {symbol} ({interval}) "
        f"{start_date}->{end_date}. Alpaca-only mode — no Yahoo fallback."
    )
    return None


def _cache_df(df: pd.DataFrame, filepath: str) -> None:
    """Saves a DataFrame to CSV cache, logging any errors."""
    try:
        df.to_csv(filepath)
        logger.info(f"[vbt-smart] Cached: {filepath}")
    except Exception as e:
        logger.warning(f"[vbt-smart] Could not cache to {filepath}: {e}")
