# signals/elliott_wave_signals.py
"""
Elliott Wave / Fibonacci Retracement signal generator.

Sweeps over:
  - swing_order: how many bars on each side confirm a swing point
  - fib_level: which Fibonacci retracement level to trade (0.236–0.786)
  - fib_tolerance: how wide the Fibonacci zone is (±% of the fib price)

Uses Numba-compiled swing detection and batched signal computation from
indicators/elliott_wave.py for performance.  All (fib_level × fib_tolerance)
combos are processed in a single Numba call per swing order, eliminating
135k individual Python→Numba dispatches.
"""

import pandas as pd
import numpy as np
from indicators.elliott_wave import _detect_swings, _compute_fib_signals_batch
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
        swing_order_range: Array of swing detection orders.
        fib_level_range: Array of Fibonacci levels.
        fib_tolerance_range: Array of zone tolerances.
        enable_shorting: If True, generate short signals.

    Returns:
        (entries, exits, short_entries, short_exits) — boolean DataFrames with
        MultiIndex columns (swing_order, fib_level, fib_tolerance).
    """
    if close.empty:
        raise ValueError("Close price series is empty.")

    swing_order_range = np.asarray(swing_order_range, dtype=int)
    fib_level_range = np.asarray(fib_level_range, dtype=np.float64)
    fib_tolerance_range = np.asarray(fib_tolerance_range, dtype=np.float64)

    n_fib_combos = fib_level_range.size * fib_tolerance_range.size
    total = swing_order_range.size * n_fib_combos
    logger.info(f"[ELLIOTT] Generating signals for {total:,} combinations...")

    high_arr = high.values.astype(np.float64)
    low_arr = low.values.astype(np.float64)
    close_arr = close.values.astype(np.float64)

    # Cache swing detection per order (most expensive step)
    swing_cache = {}

    all_le = []
    all_lx = []
    all_se = []
    all_sx = []

    for order in swing_order_range:
        if order not in swing_cache:
            swing_cache[order] = _detect_swings(high_arr, low_arr, int(order))

        sh, sl = swing_cache[order]

        # Batch all (fib_level × fib_tolerance) combos in one Numba call
        le, lx, se, sx = _compute_fib_signals_batch(
            close_arr, sh, sl, fib_level_range, fib_tolerance_range,
        )
        # Each result is (n_bars, n_fib_combos) — append for later concat
        all_le.append(le)
        all_lx.append(lx)
        if enable_shorting:
            all_se.append(se)
            all_sx.append(sx)

    # Build column MultiIndex: (swing_order, fib_level, fib_tolerance)
    col_tuples = []
    for order in swing_order_range:
        for fib_level in fib_level_range:
            for fib_tol in fib_tolerance_range:
                col_tuples.append((
                    int(order),
                    round(float(fib_level), 3),
                    round(float(fib_tol), 4),
                ))

    mi = pd.MultiIndex.from_tuples(
        col_tuples,
        names=["swing_order", "fib_level", "fib_tolerance"],
    )

    # Assemble DataFrames
    logger.info("[ELLIOTT] Assembling signal DataFrames...")
    entries_df = pd.DataFrame(
        np.concatenate(all_le, axis=1), index=close.index, columns=mi,
    )
    exits_df = pd.DataFrame(
        np.concatenate(all_lx, axis=1), index=close.index, columns=mi,
    )

    short_entries_df = None
    short_exits_df = None
    if enable_shorting and all_se:
        short_entries_df = pd.DataFrame(
            np.concatenate(all_se, axis=1), index=close.index, columns=mi,
        )
        short_exits_df = pd.DataFrame(
            np.concatenate(all_sx, axis=1), index=close.index, columns=mi,
        )

    logger.info(f"[ELLIOTT] Signals generated. Shape: {entries_df.shape}")
    return entries_df, exits_df, short_entries_df, short_exits_df
