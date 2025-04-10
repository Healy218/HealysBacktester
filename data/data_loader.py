# Purpose: Fetch raw price data from a source (e.g., API, local files) and potentially cache it.

function load_price_data(symbol, start_date, end_date, interval, api_key=None, cache_dir="data/cache"):
  # INPUTS: Ticker symbol, date range, interval (e.g., '1D'), optional API key, cache location
  # OUTPUT: Raw pandas DataFrame with DatetimeIndex and OHLCV columns

  # Define cache filename based on inputs
  cache_filename = generate_cache_filename(symbol, start_date, end_date, interval)
  cache_filepath = combine_path(cache_dir, cache_filename)

  # Check if cached data exists
  if file_exists(cache_filepath):
    print("Loading data from cache:", cache_filepath)
    raw_df = load_dataframe_from_csv(cache_filepath)
    return raw_df

  # If not cached, fetch from source (e.g., AlphaVantage, Yahoo Finance via yfinance)
  print("Fetching data from source for:", symbol)
  # --- API/Library Specific Code ---
  # Example using a hypothetical API client:
  # client = initialize_api_client(api_key)
  # raw_data = client.get_historical_data(symbol, start_date, end_date, interval)
  # raw_df = convert_api_data_to_dataframe(raw_data) # Ensure OHLCV columns and DatetimeIndex
  # --- End API/Library Specific Code ---

  # Handle potential errors during fetch (e.g., symbol not found, API errors)
  if fetch_was_successful and raw_df_is_valid:
    # Create cache directory if it doesn't exist
    create_directory_if_not_exists(cache_dir)
    # Save the raw DataFrame to cache
    save_dataframe_to_csv(raw_df, cache_filepath)
    print("Saved raw data to cache:", cache_filepath)
    return raw_df
  else:
    print("Error fetching data for:", symbol)
    return empty_dataframe # Or raise an error

end function