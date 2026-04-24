# signals/volume_breakout.py

import gc
import pandas as pd
import numpy as np
import vectorbt as vbt
import traceback
from itertools import product as iter_product
from utils.logging_utils import setup_logging
from utils.error_handling import handle_errors, BacktesterError

# Setup logger
logger = setup_logging(log_file="logs/backtester.log")

# Memory budget for aligned float64 arrays during broadcasting.
# Peak per chunk: avg_vol_aligned + temp multiplication + exit_ma_aligned ≈ 4 arrays
_SIGNAL_MEM_BUDGET = 2 * 1024**3
_VOL_FLOAT_ARRAYS = 4


def _max_vol_combos(n_rows: int) -> int:
    """Max parameter combos per broadcasting pass to stay within memory budget."""
    cols = _SIGNAL_MEM_BUDGET // (_VOL_FLOAT_ARRAYS * max(n_rows, 1) * 8)
    return max(500, min(50_000, int(cols)))


@handle_errors
def generate_volume_signals(
    ohlcv_df: pd.DataFrame,            # Needs 'Open', 'High', 'Low', 'Close', 'Volume'
    volume_window_range: np.ndarray,   # Rolling window range for average volume
    volume_multiplier_range: np.ndarray,# Range of factors to multiply average volume by
    exit_ma_window_range: np.ndarray,  # Range of exit MA window parameters
    confirm_price_increase: bool = True, # Require price increase on breakout day?
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame | None, pd.DataFrame | None]:
    """
    Generates entry signals based on Volume Breakouts and exit signals based
    on price crossing below a Moving Average. Uses vectorized operations and handles
    combinations of volume_window_range, volume_multiplier_range, and exit_ma_window_range.

    For large parameter spaces, internally chunks the broadcasting step to stay
    within a ~2 GB memory budget per chunk.

    Args:
        ohlcv_df: DataFrame with OHLCV data.
        volume_window_range: 1D numpy array defining the range for volume averaging windows.
        volume_multiplier_range: 1D numpy array defining the range for multipliers.
        exit_ma_window_range: 1D numpy array defining the range for exit MA windows.
        confirm_price_increase: If True, requires Close > previous Close for entry signal.

    Returns:
        A tuple containing: entries_df, exits_df, None, None.
        Columns are MultiIndex named ('volume_window', 'volume_multiplier', 'exit_ma_window').
    """
    # --- Input Validation ---
    if not isinstance(volume_window_range, np.ndarray): volume_window_range = np.array(volume_window_range)
    if not isinstance(volume_multiplier_range, np.ndarray): volume_multiplier_range = np.array(volume_multiplier_range)
    if not isinstance(exit_ma_window_range, np.ndarray): exit_ma_window_range = np.array(exit_ma_window_range)

    if volume_window_range.size == 0 or volume_multiplier_range.size == 0 or exit_ma_window_range.size == 0:
        raise ValueError("Input range arrays cannot be empty.")
    required_cols = ['Close', 'Volume']
    if not all(col in ohlcv_df.columns for col in required_cols):
         raise ValueError(f"OHLCV DataFrame must contain {required_cols} columns.")

    # --- Prepare Parameter Combinations and Final Index ---
    param_product = list(iter_product(volume_window_range, volume_multiplier_range, exit_ma_window_range))
    column_index = pd.MultiIndex.from_tuples(
        param_product,
        names=['volume_window', 'volume_multiplier', 'exit_ma_window']
    )
    n_combinations = len(param_product)
    n_rows = len(ohlcv_df)

    logger.info(f"Calculating Volume/MA signals for {n_combinations} combinations (vectorized)...")

    # --- Vectorized Calculation ---
    try:
        volume_series = ohlcv_df['Volume']
        close_series = ohlcv_df['Close']

        # 1. Calculate Rolling Average Volume and Exit MA for unique windows (small)
        avg_volume_df = vbt.MA.run(volume_series, window=volume_window_range, short_name='vol_ma').ma
        exit_ma_df = vbt.MA.run(close_series, window=exit_ma_window_range, short_name='exit_ma').ma

        # 2. Prepare shared arrays for broadcasting
        volume_np = volume_series.values[:, np.newaxis]
        close_np = close_series.values[:, np.newaxis]

        window_map = {w: i for i, w in enumerate(volume_window_range)}
        exit_window_map = {e: i for i, e in enumerate(exit_ma_window_range)}

        price_increase_np = None
        if confirm_price_increase:
            price_increase_np = (close_series > close_series.shift(1)).values[:, np.newaxis]

        max_combos = _max_vol_combos(n_rows)

        if n_combinations <= max_combos:
            # Single-pass: all combos fit within memory budget
            entries_np, exits_np = _vol_compute_signals(
                param_product, avg_volume_df, exit_ma_df,
                window_map, exit_window_map,
                volume_np, close_np, confirm_price_increase, price_increase_np,
            )
        else:
            # Chunked: process subsets to stay within memory budget
            n_chunks = (n_combinations + max_combos - 1) // max_combos
            logger.info(
                f"[VOLUME] Signal computation chunked: {n_combinations:,} combos → "
                f"{n_chunks} chunks of ≤{max_combos:,} (n_rows={n_rows:,})"
            )

            entries_chunks = []
            exits_chunks = []

            for chunk_idx, start in enumerate(range(0, n_combinations, max_combos)):
                end = min(start + max_combos, n_combinations)
                logger.info(f"[VOLUME]   Signal chunk {chunk_idx + 1}/{n_chunks}: combos {start:,}–{end:,}")

                chunk_params = param_product[start:end]
                chunk_entries, chunk_exits = _vol_compute_signals(
                    chunk_params, avg_volume_df, exit_ma_df,
                    window_map, exit_window_map,
                    volume_np, close_np, confirm_price_increase, price_increase_np,
                )

                entries_chunks.append(chunk_entries)
                exits_chunks.append(chunk_exits)
                gc.collect()

            entries_np = np.concatenate(entries_chunks, axis=1)
            exits_np = np.concatenate(exits_chunks, axis=1)
            del entries_chunks, exits_chunks

        # 3. Create Final DataFrames
        entries_df = pd.DataFrame(entries_np, index=ohlcv_df.index, columns=column_index)
        entries_df = entries_df.fillna(False)

        exits_df = pd.DataFrame(exits_np, index=ohlcv_df.index, columns=column_index)
        exits_df = exits_df.fillna(False)

    except Exception as e:
        logger.error(f"Error during vectorized signal calculation: {e}")
        traceback.print_exc()
        raise

    logger.info(f"Volume Breakout/MA Exit signals generated. Shape: {entries_df.shape}")
    return entries_df, exits_df, None, None  # No short signals


def _vol_compute_signals(
    params: list,
    avg_volume_df: pd.DataFrame,
    exit_ma_df: pd.DataFrame,
    window_map: dict,
    exit_window_map: dict,
    volume_np: np.ndarray,
    close_np: np.ndarray,
    confirm_price_increase: bool,
    price_increase_np: np.ndarray | None,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute entry/exit boolean arrays for a batch of parameter combos."""
    # Align volume averages to combo order
    col_indices_vol = [window_map[w] for w, m, e in params]
    avg_volume_aligned_np = avg_volume_df.values[:, col_indices_vol]

    multipliers_ordered = np.array([m for w, m, e in params])
    multiplier_aligned_np = multipliers_ordered[np.newaxis, :]

    volume_breakout_np = volume_np > (multiplier_aligned_np * avg_volume_aligned_np)
    del avg_volume_aligned_np  # free float64 intermediate

    if confirm_price_increase and price_increase_np is not None:
        entries_np = volume_breakout_np & price_increase_np
        del volume_breakout_np
    else:
        entries_np = volume_breakout_np

    # Align exit MAs to combo order
    col_indices_exit = [exit_window_map[e] for w, m, e in params]
    exit_ma_aligned_np = exit_ma_df.values[:, col_indices_exit]

    exits_np = close_np < exit_ma_aligned_np
    del exit_ma_aligned_np  # free float64 intermediate

    return entries_np, exits_np
