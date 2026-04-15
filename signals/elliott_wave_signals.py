# signals/elliott_wave_signals.py
"""
Elliott Wave / Fibonacci Retracement signal generator.

Sweeps over:
  - swing_order: how many bars on each side confirm a swing point
  - fib_level: which Fibonacci retracement level to trade (0.236–0.786)
  - fib_tolerance: how wide the Fibonacci zone is (±% of the fib price)

Uses Numba-compiled swing detection and signal computation from
indicators/elliott_wave.py for performance.
"""

import pandas as pd
import numpy as np
from itertools import product as iter_product
from indicators.elliott_wave import _detect_swings, _compute_fib_signals
from utils.logging_utils import setup_logging
from utils.error_handling import handle_errors

logger = setup_logging(log_file="logs/backtester.log")


@handle_errors
def generate_elliott_wave_signals(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    swing_order_range: np.ndarray,
    fib_level_range: np.ndarray,
    fib_tolerance_range: np.ndarray,
    enable_shorting: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame | None, pd.DataFrame | None]:
    """
    Generates entry/exit signals based on Elliott Wave swing detection
    and Fibonacci retracement zones.

    Sweeps over swing_order × fib_level × fib_tolerance combinations.

    Args:
        high: High price series.
        low: Low price series.
        close: Close price series.
        swing_order_range: Array of swing detection orders (e.g., np.arange(3, 20)).
        fib_level_range: Array of Fibonacci levels (e.g., np.arange(0.236, 0.80, 0.01)).
        fib_tolerance_range: Array of zone tolerances (e.g., np.arange(0.005, 0.05, 0.005)).
        enable_shorting: If True, generate short signals.

    Returns:
        (entries, exits, short_entries, short_exits) — boolean DataFrames with
        MultiIndex columns (swing_order, fib_level, fib_tolerance).
    """
    if close.empty:
        raise ValueError("Close price series is empty.")

    swing_order_range = np.asarray(swing_order_range, dtype=int)
    fib_level_range = np.asarray(fib_level_range, dtype=float)
    fib_tolerance_range = np.asarray(fib_tolerance_range, dtype=float)

    total = swing_order_range.size * fib_level_range.size * fib_tolerance_range.size
    logger.info(f"[ELLIOTT] Generating signals for {total:,} combinations...")

    high_arr = high.values.astype(np.float64)
    low_arr = low.values.astype(np.float64)
    close_arr = close.values.astype(np.float64)

    all_entries = []
    all_exits = []
    all_short_entries = []
    all_short_exits = []
    col_tuples = []

    # Cache swing detection per order (most expensive step)
    swing_cache = {}

    for order in swing_order_range:
        if order not in swing_cache:
            swing_cache[order] = _detect_swings(high_arr, low_arr, int(order))

        sh, sl = swing_cache[order]

        for fib_level in fib_level_range:
            for fib_tol in fib_tolerance_range:
                le, lx, se, sx = _compute_fib_signals(
                    close_arr, sh, sl, float(fib_level), float(fib_tol)
                )

                all_entries.append(le)
                all_exits.append(lx)
                if enable_shorting:
                    all_short_entries.append(se)
                    all_short_exits.append(sx)

                col_tuples.append((
                    int(order),
                    round(float(fib_level), 3),
                    round(float(fib_tol), 4),
                ))

    # Assemble DataFrames
    logger.info("[ELLIOTT] Assembling signal DataFrames...")
    mi = pd.MultiIndex.from_tuples(
        col_tuples,
        names=["swing_order", "fib_level", "fib_tolerance"],
    )

    entries_df = pd.DataFrame(
        np.column_stack(all_entries), index=close.index, columns=mi,
    )
    exits_df = pd.DataFrame(
        np.column_stack(all_exits), index=close.index, columns=mi,
    )

    short_entries_df = None
    short_exits_df = None
    if enable_shorting and all_short_entries:
        short_entries_df = pd.DataFrame(
            np.column_stack(all_short_entries), index=close.index, columns=mi,
        )
        short_exits_df = pd.DataFrame(
            np.column_stack(all_short_exits), index=close.index, columns=mi,
        )

    logger.info(f"[ELLIOTT] Signals generated. Shape: {entries_df.shape}")
    return entries_df, exits_df, short_entries_df, short_exits_df
