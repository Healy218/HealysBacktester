# data/data_loader.py

import pandas as pd
import vectorbt as vbt
import yfinance as yf
import os
import time
import traceback
from utils.logging_utils import setup_logging
from utils.error_handling import handle_errors, DataError

# Loaded lazily to avoid hard dependency when alpaca-py isn't installed
_alpaca_loader = None


def _try_alpaca(symbol, start_date, end_date, interval):
    """Attempts an Alpaca download. Returns DataFrame or None on any failure."""
    global _alpaca_loader
    try:
        if _alpaca_loader is None:
            from data import alpaca_loader as _al
            _alpaca_loader = _al
        return _alpaca_loader.load_alpaca_bars(symbol, start_date, end_date, interval)
    except ImportError:
        logger.debug("alpaca-py not installed — skipping Alpaca source.")
        return None
    except DataError as e:
        logger.warning(f"Alpaca unavailable: {e}. Falling back to yfinance.")
        return None
    except Exception as e:
        logger.warning(f"Alpaca error: {e}. Falling back to yfinance.")
        return None

logger = setup_logging(log_file="logs/backtester.log")

# ---------------------------------------------------------------------------
# Retry configuration for rate-limited downloads
# ---------------------------------------------------------------------------
_MAX_RETRIES = 4
_RETRY_BACKOFF_BASE = 5   # seconds — doubles each retry: 5, 10, 20, 40


def _download_with_retry(symbol: str, start_date: str, end_date: str, interval: str) -> pd.DataFrame | None:
    """
    Downloads OHLCV data from Yahoo Finance via yfinance directly, with
    exponential backoff retry on rate-limit errors.

    Uses yfinance directly (not via vectorbt.YFData) because newer yfinance
    versions handle cookies/crumb authentication better and expose cleaner errors.

    Args:
        symbol: Ticker symbol.
        start_date: Start date string (YYYY-MM-DD).
        end_date: End date string (YYYY-MM-DD).
        interval: Bar interval string (e.g., '5m', '1D').

    Returns:
        DataFrame with OHLCV columns, or None if all retries exhausted.
    """
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            logger.info(f"Download attempt {attempt}/{_MAX_RETRIES} for {symbol} ({interval}) {start_date} -> {end_date}")

            # yf.download with auto_adjust=True merges Adj Close into Close,
            # which is what we want for backtesting (handles splits/dividends).
            raw = yf.download(
                tickers=symbol,
                start=start_date,
                end=end_date,
                interval=interval,
                auto_adjust=True,
                progress=False,   # suppress tqdm bar
                threads=False,    # avoid threading issues in some envs
            )

            if raw is None or raw.empty:
                logger.warning(f"Attempt {attempt}: Empty response for {symbol}. "
                               "This may be a rate limit or the symbol/date range is invalid.")
                # Don't retry on empty — likely a bad request, not a rate limit
                return None

            # yf.download returns MultiIndex columns for multi-ticker requests.
            # For single ticker, flatten if needed.
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.droplevel(1)

            logger.info(f"Download successful. Shape: {raw.shape}")
            return raw

        except Exception as e:
            err_str = str(e).lower()
            is_rate_limit = any(kw in err_str for kw in ('rate limit', 'too many requests', '429', 'ratelimit'))

            if is_rate_limit:
                wait = _RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
                logger.warning(f"Rate limited by Yahoo Finance (attempt {attempt}/{_MAX_RETRIES}). "
                               f"Waiting {wait}s before retry...")
                time.sleep(wait)
            else:
                logger.error(f"Non-rate-limit error on attempt {attempt}: {e}")
                return None  # Don't retry on non-rate-limit errors

    logger.error(f"All {_MAX_RETRIES} download attempts failed for {symbol}. "
                 "Consider using a different data source (see README).")
    return None


@handle_errors
def load_price_data(symbol: str,
                    start_date: str,
                    end_date: str,
                    interval: str,
                    cache_dir: str = "data/cache",
                    force_download: bool = False) -> pd.DataFrame | None:
    """
    Loads OHLCV data for a given symbol and date range.

    Checks a local CSV cache first to avoid unnecessary downloads.
    On cache miss, downloads from Yahoo Finance with automatic retry on rate limits.

    Args:
        symbol: Ticker symbol (e.g., 'SPY').
        start_date: Start date string (YYYY-MM-DD).
        end_date: End date string (YYYY-MM-DD).
        interval: Bar interval string (e.g., '1D', '5m').
                  Note: Yahoo Finance limits intraday history to ~60 days.
        cache_dir: Directory to store/retrieve cached CSV files.
        force_download: If True, skip the cache and always download fresh data.

    Returns:
        DataFrame with OHLCV columns and DatetimeIndex, or None on failure.
    """
    os.makedirs(cache_dir, exist_ok=True)

    safe_symbol = symbol.replace('/', '_')
    cache_filename = f"{safe_symbol}_{interval}_{start_date}_{end_date}.csv"
    cache_filepath = os.path.join(cache_dir, cache_filename)

    # --- Check cache ---
    if not force_download and os.path.exists(cache_filepath):
        logger.info(f"Loading {symbol} from cache: {cache_filepath}")
        try:
            cached_df = pd.read_csv(cache_filepath, index_col=0, parse_dates=True)
            if not cached_df.empty and isinstance(cached_df.index, pd.DatetimeIndex):
                logger.info(f"Cache hit. Shape: {cached_df.shape}")
                return cached_df
            else:
                logger.warning("Cached file is invalid (empty or bad index). Will re-download.")
        except Exception as e:
            logger.warning(f"Error reading cache file {cache_filepath}: {e}. Will re-download.")

    # --- Download with retry ---
    raw_df = _download_with_retry(symbol, start_date, end_date, interval)

    if raw_df is None or raw_df.empty:
        logger.error(f"Could not download data for {symbol}. "
                     "Check the symbol, date range, and your internet connection. "
                     "For intraday intervals, Yahoo Finance only provides ~60 days of history.")
        return None

    # --- Save to cache ---
    try:
        raw_df.to_csv(cache_filepath)
        logger.info(f"Saved to cache: {cache_filepath}")
    except Exception as e:
        logger.warning(f"Could not save data to cache {cache_filepath}: {e}")

    return raw_df


def load_price_data_smart(
    symbol: str,
    start_date: str,
    end_date: str,
    interval: str,
    cache_dir: str = "data/cache",
    force_download: bool = False,
) -> pd.DataFrame | None:
    """
    Smart data loader used by the interactive dashboard.

    Priority order:
      1. Local CSV cache (instant, always tried first)
      2. Alpaca Markets (if ALPACA_API_KEY env var is set)
      3. Yahoo Finance with retry (fallback)

    Args:
        symbol: Ticker symbol (e.g. 'SPY').
        start_date: Start date 'YYYY-MM-DD'.
        end_date: End date 'YYYY-MM-DD'.
        interval: Bar interval ('1m', '5m', '1h', '1D', …).
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
        logger.info(f"[smart] Cache hit: {cache_filepath}")
        try:
            df = pd.read_csv(cache_filepath, index_col=0, parse_dates=True)
            if not df.empty and isinstance(df.index, pd.DatetimeIndex):
                return df
        except Exception as e:
            logger.warning(f"[smart] Cache read failed: {e}. Re-downloading.")

    # 2. Try Alpaca
    alpaca_env_set = bool(os.environ.get("ALPACA_API_KEY"))
    if alpaca_env_set:
        logger.info(f"[smart] Trying Alpaca for {symbol}...")
        df = _try_alpaca(symbol, start_date, end_date, interval)
        if df is not None and not df.empty:
            try:
                df.to_csv(cache_filepath)
                logger.info(f"[smart] Alpaca data cached: {cache_filepath}")
            except Exception:
                pass
            return df

    # 3. Fall back to yfinance
    logger.info(f"[smart] Falling back to yfinance for {symbol}...")
    df = _download_with_retry(symbol, start_date, end_date, interval)
    if df is not None and not df.empty:
        try:
            df.to_csv(cache_filepath)
            logger.info(f"[smart] yfinance data cached: {cache_filepath}")
        except Exception:
            pass
        return df

    logger.error(f"[smart] All sources failed for {symbol} ({interval}) {start_date}->{end_date}.")
    return None
