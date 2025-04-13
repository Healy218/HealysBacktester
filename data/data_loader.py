# data/data_loader.py

import pandas as pd
import vectorbt as vbt
import os
import traceback # For detailed error logging

def load_price_data(symbol: str,
                    start_date: str,
                    end_date: str,
                    interval: str,
                    cache_dir: str = "data/cache") -> pd.DataFrame | None:
    """
    Loads OHLCV data for a given symbol and date range.
    Checks a local cache first, otherwise downloads using vectorbt.YFData.

    Args:
        symbol: Ticker symbol (e.g., 'SPY').
        start_date: Start date string (e.g., '2020-01-01').
        end_date: End date string (e.g., '2023-12-31').
        interval: Data interval string (e.g., '1D', '1h').
        cache_dir: Directory to store/retrieve cached data files.

    Returns:
        A pandas DataFrame with OHLCV data and DatetimeIndex, or None if loading fails.
    """
    # Sanitize inputs for filename (replace invalid chars if any, though usually ok for dates/symbols)
    safe_symbol = symbol.replace('/', '_') # Example basic sanitization
    cache_filename = f"{safe_symbol}_{interval}_{start_date}_{end_date}.csv"
    cache_filepath = os.path.join(cache_dir, cache_filename)

    # Check cache
    if os.path.exists(cache_filepath):
        print(f"Loading data for {symbol} from cache: {cache_filepath}")
        try:
            cached_df = pd.read_csv(cache_filepath, index_col=0, parse_dates=True)
            # Basic validation of cached data
            if not cached_df.empty and isinstance(cached_df.index, pd.DatetimeIndex):
                 print("Cache loaded successfully.")
                 return cached_df
            else:
                 print("Warning: Cached file seems invalid. Will attempt download.")
        except Exception as e:
            print(f"Warning: Error reading cache file {cache_filepath}: {e}. Will attempt download.")

    # If not cached or cache invalid, download
    print(f"Cache not found or invalid. Downloading data for {symbol} ({interval}) from {start_date} to {end_date}...")
    try:
        price_data_raw = vbt.YFData.download(
            symbols=symbol, # Use symbols plural
            start=start_date,
            end=end_date,
            interval=interval,
            missing_index='drop' # Keep dropping missing dates
        )
        # .get() returns a DataFrame with standard OHLCV names if data exists
        # For single symbol, result is DataFrame. For multiple, it's a dict of DataFrames.
        # We assume single symbol based on current scripts.
        raw_df = price_data_raw.get()

        if raw_df is None or raw_df.empty:
             print(f"Warning: No data downloaded for {symbol}.")
             return None

        print(f"Data downloaded successfully. Shape: {raw_df.shape}")

        # Save to cache
        try:
            os.makedirs(cache_dir, exist_ok=True) # Ensure cache directory exists
            raw_df.to_csv(cache_filepath)
            print(f"Saved downloaded data to cache: {cache_filepath}")
        except Exception as e:
            print(f"Warning: Could not save data to cache {cache_filepath}: {e}")

        return raw_df

    except Exception as e:
        print(f"FATAL ERROR downloading data for {symbol}: {e}")
        # traceback.print_exc() # Uncomment for detailed debug info
        return None

# Example usage (optional - for testing the loader directly)
# if __name__ == '__main__':
#     df = load_price_data('SPY', '2022-01-01', '2022-12-31', '1D')
#     if df is not None:
#         print("\nLoaded DataFrame head:")
#         print(df.head())
#         print("\nLoaded DataFrame info:")
#         df.info()