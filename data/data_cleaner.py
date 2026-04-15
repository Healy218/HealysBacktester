# data/data_cleaner.py

import pandas as pd
import numpy as np
from utils.logging_utils import setup_logging
from utils.error_handling import handle_errors, BacktesterError # Import the decorator and any custom errors if needed

# Setup logger
logger = setup_logging(log_file="logs/backtester.log")

@handle_errors
def clean_ohlcv_data(raw_df: pd.DataFrame) -> pd.DataFrame | None:
    """
    Cleans raw OHLCV data: ensures DatetimeIndex, standard columns,
    numeric types, and handles NaNs.

    Args:
        raw_df: Raw pandas DataFrame, expects DatetimeIndex and
                columns like 'Open', 'High', 'Low', 'Close', 'Volume'.

    Returns:
        Cleaned pandas DataFrame, or None if cleaning fails validation.
    """
    if raw_df is None or raw_df.empty:
        logger.error("Error: Cannot clean None or empty DataFrame.")
        return None

    logger.info("Starting data cleaning...")
    df = raw_df.copy()

    # --- Index Cleaning ---
    # Ensure index is DatetimeIndex (should be from loader, but double-check)
    try:
        df.index = pd.to_datetime(df.index)
    except Exception as e:
        logger.error(f"Error converting index to datetime: {e}. Returning None.")
        return None
    # Remove timezone if present
    if df.index.tz is not None:
        logger.info("Removing timezone information from index.")
        df.index = df.index.tz_localize(None)
    # Sort by index
    if not df.index.is_monotonic_increasing:
        logger.info("Sorting DataFrame by index.")
        df = df.sort_index()

    # --- Filter out non-trading days (weekends) ---
    weekend_mask = df.index.dayofweek >= 5  # Saturday=5, Sunday=6
    if weekend_mask.any():
        n_weekend = int(weekend_mask.sum())
        logger.info(f"Removing {n_weekend} weekend bars.")
        df = df[~weekend_mask]

    if df.empty:
        logger.error("Error: DataFrame is empty after removing weekend bars.")
        return None

    # --- Column Cleaning ---
    required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
    # Check if required columns exist
    if not all(col in df.columns for col in required_cols):
        missing = [col for col in required_cols if col not in df.columns]
        logger.error(f"Error: Missing required columns: {missing}. Returning None.")
        return None
    # Optional: Select only required columns if extra ones exist
    # df = df[required_cols]

    # --- Data Type and Value Cleaning ---
    for col in required_cols:
        # Convert to numeric, coercing errors (turns non-numeric into NaN)
        df[col] = pd.to_numeric(df[col], errors='coerce')
        # Optional: Check for non-positive values (except maybe volume?)
        if col != 'Volume':
            if (df[col] <= 0).any():
                logger.warning(f"Warning: Column {col} contains non-positive values.")
                # Decide how to handle: set to NaN, remove row, etc.
                # Example: df.loc[df[col] <= 0, col] = np.nan

    # --- Handle Missing Values (NaNs) ---
    if df.isnull().values.any():
        logger.warning("Warning: NaNs found before filling. Applying ffill/bfill.")
        nan_counts_before = df.isnull().sum()
        df = df.ffill().bfill()
        nan_counts_after = df.isnull().sum()
        if nan_counts_after.sum() < nan_counts_before.sum():
             logger.debug("NaNs filled.")
        # Check if any NaNs remain after filling
        if df.isnull().values.any():
            logger.error("Error: NaNs still present after ffill/bfill. Data quality issue.")
            # Decide: return None, raise error, or return partial data? Returning None for safety.
            return None

    logger.info(f"Data cleaning complete. Final shape: {df.shape}")
    return df

# Example usage (optional - for testing the cleaner directly)
# if __name__ == '__main__':
#     # Create a dummy raw DataFrame for testing
#     test_data = {'Open': [10, 11, np.nan, 13], 'High': [11, 12, 11.5, 14],
#                  'Low': [9.5, 10.5, 10, 12.5], 'Close': ['10.5', 11.5, 11, 13.5], # Test string
#                  'Volume': [100, 110, 90, 120]}
#     test_index = pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-03', '2023-01-04'])
#     raw_test_df = pd.DataFrame(test_data, index=test_index)
#     print("Raw Test DataFrame:\n", raw_test_df)
#     cleaned_df = clean_ohlcv_data(raw_test_df)
#     if cleaned_df is not None:
#         print("\nCleaned DataFrame head:")
#         print(cleaned_df.head())
#         print("\nCleaned DataFrame info:")
#         cleaned_df.info()