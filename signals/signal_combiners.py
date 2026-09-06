# signals/signal_combiners.py

import pandas as pd
import numpy as np
import vectorbt as vbt # Still useful for type hints or other functions if needed
import warnings
from itertools import product as iter_product # Use alias to avoid confusion
from utils.logging_utils import setup_logging
from utils.error_handling import handle_errors, BacktesterError # Import the decorator and any custom errors if needed

# Setup logger
logger = setup_logging(log_file="logs/backtester.log")

@handle_errors
def _get_combined_index(df1: pd.DataFrame, df2: pd.DataFrame) -> pd.MultiIndex:
    """Helper function to create the combined MultiIndex."""
    def tuples(columns):
        return list(columns) if isinstance(columns, pd.MultiIndex) else [(c,) for c in columns]

    # Preserve actual valid tuples (e.g. fast < slow), not a product of levels.
    names = []
    for group, columns in enumerate((df1.columns, df2.columns), 1):
        for level, name in enumerate(columns.names):
            candidate = name or f"param{group}_{level}"
            while candidate in names:
                candidate = f"{candidate}_{group}"
            names.append(candidate)
    pairs = [a + b for a, b in iter_product(tuples(df1.columns), tuples(df2.columns))]
    return pd.MultiIndex.from_tuples(pairs, names=names)



def combine_signals_and(
    entries1_df: pd.DataFrame, exits1_df: pd.DataFrame,
    entries2_df: pd.DataFrame, exits2_df: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Combines two sets of signal DataFrames using logical AND for entries
    and OR for exits (exit if EITHER original exit is True).
    Uses NumPy broadcasting for the logical operations.

    Args:
        entries1_df, exits1_df: DataFrames for the first strategy.
        entries2_df, exits2_df: DataFrames for the second strategy.

    Returns:
        A tuple containing combined entry and exit DataFrames.
    """
    if not isinstance(entries1_df, pd.DataFrame) or not isinstance(entries2_df, pd.DataFrame):
        raise TypeError("Inputs must be pandas DataFrames.")
    if not entries1_df.columns.equals(exits1_df.columns):
        raise ValueError("Columns of entries1_df and exits1_df must match.")
    if not entries2_df.columns.equals(exits2_df.columns):
        raise ValueError("Columns of entries2_df and exits2_df must match.")

    logger.info("Combining signals using AND logic for entries (NumPy broadcasting)...")

    try:
        # --- Prepare for NumPy Operation ---
        entries1_np = entries1_df.astype(bool).values
        exits1_np = exits1_df.astype(bool).values
        entries2_np = entries2_df.astype(bool).values
        exits2_np = exits2_df.astype(bool).values

        n_rows = entries1_np.shape[0]
        n_cols1 = entries1_np.shape[1]
        n_cols2 = entries2_np.shape[1]

        # --- Perform Logical Operations using NumPy ---
        # Repeat/tile arrays to match the shape of the cross-product (n_rows, n_cols1 * n_cols2)

        # Entries: entries1 AND entries2
        op1_entries = entries1_np.repeat(n_cols2, axis=1)
        op2_entries = np.tile(entries2_np, n_cols1)
        combined_entries_np = op1_entries & op2_entries

        # Exits: exits1 OR exits2
        op1_exits = exits1_np.repeat(n_cols2, axis=1)
        op2_exits = np.tile(exits2_np, n_cols1)
        combined_exits_np = op1_exits | op2_exits

        # --- Create Combined Index and Final DataFrames ---
        combined_index = _get_combined_index(entries1_df, entries2_df)

        if combined_entries_np.shape[1] != len(combined_index):
             raise ValueError(f"Shape mismatch: NumPy result columns ({combined_entries_np.shape[1]}) != Combined Index length ({len(combined_index)})")

        combined_entries_df = pd.DataFrame(
            combined_entries_np,
            index=entries1_df.index,
            columns=combined_index
        )
        combined_exits_df = pd.DataFrame(
            combined_exits_np,
            index=exits1_df.index, # or entries1_df.index, should be same
            columns=combined_index
        )

    except Exception as e:
        logger.exception(f"Error during NumPy signal combination: {e}")
        raise # Re-raise the exception

    # Optional cleaning can go here if desired
    # print("Cleaning combined signals...")
    # combined_entries_df, combined_exits_df = combined_entries_df.vbt.signals.clean(combined_exits_df)

    logger.info(f"Signal 'AND' combination complete. Result shape: {combined_entries_df.shape}")

    return combined_entries_df, combined_exits_df


def combine_signals_or(
    entries1_df: pd.DataFrame, exits1_df: pd.DataFrame,
    entries2_df: pd.DataFrame, exits2_df: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Combines two sets of signal DataFrames using logical OR for entries.
    Exit logic: Exits if BOTH original exit signals are True (can be adjusted).
    Uses NumPy broadcasting for the logical operations.

    Args:
        entries1_df, exits1_df: DataFrames for the first strategy.
        entries2_df, exits2_df: DataFrames for the second strategy.

    Returns:
        A tuple containing combined entry and exit DataFrames.
    """
    if not isinstance(entries1_df, pd.DataFrame) or not isinstance(entries2_df, pd.DataFrame):
        raise TypeError("Inputs must be pandas DataFrames.")
    if not entries1_df.columns.equals(exits1_df.columns):
        raise ValueError("Columns of entries1_df and exits1_df must match.")
    if not entries2_df.columns.equals(exits2_df.columns):
        raise ValueError("Columns of entries2_df and exits2_df must match.")

    logger.info("Combining signals using OR logic for entries (NumPy broadcasting)...")

    try:
        # --- Prepare for NumPy Operation ---
        entries1_np = entries1_df.astype(bool).values
        exits1_np = exits1_df.astype(bool).values
        entries2_np = entries2_df.astype(bool).values
        exits2_np = exits2_df.astype(bool).values

        n_rows = entries1_np.shape[0]
        n_cols1 = entries1_np.shape[1]
        n_cols2 = entries2_np.shape[1]

        # --- Perform Logical Operations using NumPy ---
        # Repeat/tile arrays to match the shape of the cross-product (n_rows, n_cols1 * n_cols2)

        # Entries: entries1 OR entries2
        op1_entries = entries1_np.repeat(n_cols2, axis=1)
        op2_entries = np.tile(entries2_np, n_cols1)
        combined_entries_np = op1_entries | op2_entries

        # Exits: exits1 AND exits2 (Exit only if BOTH are true - adjust as needed)
        logger.info("Using AND logic for combined exits (Exit only if *both* strategies signal exit).")
        op1_exits = exits1_np.repeat(n_cols2, axis=1)
        op2_exits = np.tile(exits2_np, n_cols1)
        combined_exits_np = op1_exits & op2_exits

        # --- Create Combined Index and Final DataFrames ---
        combined_index = _get_combined_index(entries1_df, entries2_df)

        if combined_entries_np.shape[1] != len(combined_index):
             raise ValueError(f"Shape mismatch: NumPy result columns ({combined_entries_np.shape[1]}) != Combined Index length ({len(combined_index)})")

        combined_entries_df = pd.DataFrame(
            combined_entries_np,
            index=entries1_df.index,
            columns=combined_index
        )
        combined_exits_df = pd.DataFrame(
            combined_exits_np,
            index=exits1_df.index, # or entries1_df.index, should be same
            columns=combined_index
        )

    except Exception as e:
        logger.exception(f"Error during NumPy signal combination: {e}")
        raise # Re-raise the exception

    # Optional cleaning can go here if desired
    # print("Cleaning combined signals...")
    # combined_entries_df, combined_exits_df = combined_entries_df.vbt.signals.clean(combined_exits_df)

    logger.info(f"Signal 'OR' combination complete. Result shape: {combined_entries_df.shape}")

    return combined_entries_df, combined_exits_df