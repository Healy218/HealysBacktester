# signals/sentiment_signals.py
"""Generate vectorbt-compatible entry/exit signals from sentiment data."""

import pandas as pd
import numpy as np
from typing import Optional, Tuple, List
from utils.logging_utils import setup_logging
from utils.error_handling import handle_errors

logger = setup_logging(log_file="logs/backtester.log")


@handle_errors
def generate_sentiment_signals(
    close_prices_series: pd.Series,
    sentiment_series: pd.Series,
    window: np.ndarray,
    entry_threshold: np.ndarray,
    exit_threshold: np.ndarray,
    enable_shorting: bool = False,
) -> Tuple[pd.DataFrame, pd.DataFrame, Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    """
    Generates long/short signals from smoothed sentiment crossing thresholds.

    Produces a cross-product of (window x entry_threshold x exit_threshold)
    combinations. Column structure matches other signal generators:
        MultiIndex: (entry_threshold, exit_threshold, sentiment_window)

    Logic:
        - Long entry:  smoothed sentiment crosses ABOVE entry_threshold
        - Long exit:   smoothed sentiment crosses BELOW exit_threshold
        - Short entry: smoothed sentiment crosses BELOW exit_threshold
        - Short exit:  smoothed sentiment crosses ABOVE entry_threshold

    Args:
        close_prices_series: Price Series (used for index alignment).
        sentiment_series: Time-indexed sentiment scores (from sentiment_analyzer).
        window: 1D array of smoothing window sizes (rolling mean on sentiment).
        entry_threshold: 1D array of bullish thresholds (e.g., 0.1, 0.2).
        exit_threshold: 1D array of bearish thresholds (e.g., -0.1, -0.2).
        enable_shorting: If True, generate short signals.

    Returns:
        (entries_df, exits_df, short_entries_df, short_exits_df)
        All with MultiIndex columns: (entry_threshold, exit_threshold, sentiment_window)
    """
    if not isinstance(close_prices_series, pd.Series):
        raise TypeError("close_prices_series must be a pandas Series.")
    if close_prices_series.empty:
        empty_df = pd.DataFrame()
        return empty_df, empty_df, None, None

    window = np.asarray(window)
    entry_threshold = np.asarray(entry_threshold)
    exit_threshold = np.asarray(exit_threshold)

    # Align sentiment to price index via forward-fill
    sentiment_aligned = sentiment_series.reindex(close_prices_series.index, method="ffill").fillna(0.0)

    # Pre-compute smoothed sentiment for each window
    logger.info(f"[Sentiment] Smoothing sentiment with {len(window)} windows...")
    smoothed = {}
    for w in window:
        smoothed[int(w)] = sentiment_aligned.rolling(window=int(w), min_periods=1).mean()

    # Pre-compute crossing signals for each threshold
    n_combos = len(entry_threshold) * len(exit_threshold) * len(window)
    logger.info(
        f"[Sentiment] Building signals: {len(entry_threshold)} entry x "
        f"{len(exit_threshold)} exit x {len(window)} windows = {n_combos:,} combos"
    )

    entries_pieces: List[pd.DataFrame] = []
    exits_pieces: List[pd.DataFrame] = []
    keys: List[Tuple[float, float]] = []

    for et in entry_threshold:
        for xt in exit_threshold:
            # For each (entry, exit) pair, build a DataFrame with one column per window
            entry_cols = {}
            exit_cols = {}
            for w in window:
                s = smoothed[int(w)]
                # Crossed above entry threshold
                entry_cols[int(w)] = (s > float(et)) & (s.shift(1) <= float(et))
                # Crossed below exit threshold
                exit_cols[int(w)] = (s < float(xt)) & (s.shift(1) >= float(xt))

            entries_pieces.append(pd.DataFrame(entry_cols, index=close_prices_series.index))
            exits_pieces.append(pd.DataFrame(exit_cols, index=close_prices_series.index))
            keys.append((float(et), float(xt)))

    mi = pd.MultiIndex.from_tuples(keys, names=["entry_threshold", "exit_threshold"])

    entries_df = pd.concat(entries_pieces, axis=1, keys=mi)
    exits_df = pd.concat(exits_pieces, axis=1, keys=mi)
    entries_df.columns.names = ["entry_threshold", "exit_threshold", "sentiment_window"]
    exits_df.columns.names = ["entry_threshold", "exit_threshold", "sentiment_window"]

    logger.info(f"[Sentiment] Signals built. Entries shape: {entries_df.shape}")

    # Short signals
    short_entries_df = None
    short_exits_df = None

    if enable_shorting:
        short_entries_pieces: List[pd.DataFrame] = []
        short_exits_pieces: List[pd.DataFrame] = []

        for et in entry_threshold:
            for xt in exit_threshold:
                entry_cols = {}
                exit_cols = {}
                for w in window:
                    s = smoothed[int(w)]
                    # Short entry: sentiment crosses BELOW exit threshold (bearish)
                    entry_cols[int(w)] = (s < float(xt)) & (s.shift(1) >= float(xt))
                    # Short exit: sentiment crosses ABOVE entry threshold (bullish)
                    exit_cols[int(w)] = (s > float(et)) & (s.shift(1) <= float(et))

                short_entries_pieces.append(pd.DataFrame(entry_cols, index=close_prices_series.index))
                short_exits_pieces.append(pd.DataFrame(exit_cols, index=close_prices_series.index))

        short_entries_df = pd.concat(short_entries_pieces, axis=1, keys=mi)
        short_exits_df = pd.concat(short_exits_pieces, axis=1, keys=mi)
        short_entries_df.columns.names = ["entry_threshold", "exit_threshold", "sentiment_window"]
        short_exits_df.columns.names = ["entry_threshold", "exit_threshold", "sentiment_window"]
        logger.info(f"[Sentiment] Short signals shape: {short_entries_df.shape}")

    return entries_df, exits_df, short_entries_df, short_exits_df
