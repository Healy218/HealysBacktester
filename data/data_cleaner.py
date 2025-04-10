
'''
# Purpose: Clean raw price data into a format suitable for backtesting.

function clean_ohlcv_data(raw_df):
  # INPUT: Raw pandas DataFrame from data_loader
  # OUTPUT: Cleaned pandas DataFrame with standard column names ('Open', 'High', 'Low', 'Close', 'Volume') and clean data.

  # Make a copy to avoid modifying the original DataFrame
  df = copy_dataframe(raw_df)

  # Rename columns to standard names (adjust based on your source)
  # Example: '1. open' -> 'Open', '4. close' -> 'Close'
  df = rename_columns(df, {'old_open': 'Open', 'old_high': 'High', ...})

  # Ensure required columns exist
  required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
  if not all_columns_exist(df, required_cols):
    raise ValueError("Missing required OHLCV columns")

  # Convert columns to numeric, coercing errors
  for col in required_cols:
    df[col] = convert_to_numeric(df[col], errors='coerce')

  # Ensure index is DatetimeIndex
  df.index = convert_to_datetime(df.index)
  df = sort_dataframe_by_index(df)

  # Handle missing values (choose a strategy: ffill, interpolation, drop)
  # Example: Forward fill first, then backfill any remaining NaNs
  df = forward_fill_missing_values(df)
  df = backward_fill_missing_values(df)
  # Optional: Drop any rows still containing NaNs if necessary
  # df = drop_rows_with_missing_values(df)

  # Optional: Check for and handle outliers or zero values if needed

  print("Data cleaning complete.")
  return df

end function
'''