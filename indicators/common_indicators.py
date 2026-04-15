# indicators/common_indicators.py
"""
Extended technical indicators using vectorBT's built-in indicator classes
and the pandas-ta integration via IndicatorFactory.

All functions accept array-like parameters (lists/arrays) for vectorized
parameter sweeps, consistent with the existing MA/RSI/MACD indicator usage.
"""

import pandas as pd
import numpy as np
import vectorbt as vbt
from utils.logging_utils import setup_logging

logger = setup_logging(log_file="logs/backtester.log")


def calculate_bbands(
    close: pd.Series,
    window: int | np.ndarray | list = 20,
    alpha: float | np.ndarray | list = 2.0,
) -> tuple:
    """
    Calculates Bollinger Bands using vbt.BBANDS.

    Args:
        close: Close price series.
        window: Lookback window(s). Can be scalar or array for parameter sweep.
        alpha: Standard deviation multiplier(s). Can be scalar or array.

    Returns:
        vbt BBANDS indicator object with attributes:
          .upper, .middle, .lower, .bandwidth, .percent_b
    """
    logger.info(f"Calculating Bollinger Bands (window={window}, alpha={alpha})...")
    result = vbt.BBANDS.run(close, window=window, alpha=alpha)
    return result


def calculate_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    window: int | np.ndarray | list = 14,
) -> pd.Series | pd.DataFrame:
    """
    Calculates Average True Range using vbt.ATR.

    Args:
        high: High price series.
        low: Low price series.
        close: Close price series.
        window: ATR lookback window(s).

    Returns:
        vbt ATR indicator object with attributes: .tr, .atr
    """
    logger.info(f"Calculating ATR (window={window})...")
    result = vbt.ATR.run(high, low, close, window=window)
    return result


def calculate_stochastic(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    k_window: int | np.ndarray | list = 14,
    d_window: int | np.ndarray | list = 3,
) -> tuple:
    """
    Calculates Stochastic Oscillator using vbt.STOCH.

    Args:
        high: High price series.
        low: Low price series.
        close: Close price series.
        k_window: %K lookback window(s).
        d_window: %D smoothing window(s).

    Returns:
        vbt STOCH indicator object with attributes: .percent_k, .percent_d
    """
    logger.info(f"Calculating Stochastic (k={k_window}, d={d_window})...")
    result = vbt.STOCH.run(high, low, close, k_window=k_window, d_window=d_window)
    return result


def calculate_obv(
    close: pd.Series,
    volume: pd.Series,
) -> pd.Series | pd.DataFrame:
    """
    Calculates On-Balance Volume using vbt.OBV.

    Args:
        close: Close price series.
        volume: Volume series.

    Returns:
        vbt OBV indicator object with attributes: .obv
    """
    logger.info("Calculating OBV...")
    result = vbt.OBV.run(close, volume)
    return result


def get_pandas_ta_indicator(name: str, **kwargs):
    """
    Generic wrapper for any pandas-ta indicator via vectorBT's IndicatorFactory.

    This gives access to hundreds of technical indicators without writing
    individual wrapper functions.

    Usage:
        # RSI via pandas-ta
        rsi = get_pandas_ta_indicator('rsi', close=close_series, length=14)

        # Supertrend
        st = get_pandas_ta_indicator('supertrend', high=high, low=low, close=close)

    Args:
        name: pandas-ta indicator name (e.g. 'rsi', 'bbands', 'atr', 'supertrend').
        **kwargs: Passed to the indicator's .run() method.

    Returns:
        vectorBT indicator object.
    """
    logger.info(f"Running pandas-ta indicator: {name}")
    try:
        indicator_cls = vbt.IndicatorFactory.from_pandas_ta(name)
        result = indicator_cls.run(**kwargs)
        return result
    except Exception as e:
        logger.error(f"Failed to run pandas-ta indicator '{name}': {e}")
        raise
