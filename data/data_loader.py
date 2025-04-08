# data_loader.py
import requests
from datetime import datetime
import os
import pandas as pd
from dotenv import load_dotenv
import time

# Initialize an API request counter outside the function
api_request_counter = 0

# Pseudo-code for loading data from Finnhub
def load_stock_data(symbol, interval): #start_date, end_date):
    """
    Loads historical stock data for a given symbol from AlphaVantage.
    Tracks API requests and handles potential limit responses.
    """
    global api_request_counter
    load_dotenv(dotenv_path="/.env")
    #api_key = os.getenv('ALPHAVANTAGE_KEY') 
    api_key = "X5GPTHJQCO4FKCTL"
    print(api_key)
    
    base_url = 'https://www.alphavantage.co/query?'
    params = {
        'function': '',  # Will be set based on interval
        'symbol': symbol,
        'interval': '',  # Will be set for intraday
        'outputsize': 'compact',   # Consider 'compact' for testing with fewer requests
        'apikey': api_key
    }

    if interval in ['1min', '5min', '15min', '30min', '60min']:
        params['function'] = 'TIME_SERIES_INTRADAY'
        params['interval'] = interval
    elif interval == 'daily':
        params['function'] = 'TIME_SERIES_DAILY'
    elif interval == 'weekly':
        params['function'] = 'TIME_SERIES_WEEKLY_ADJUSTED'
    elif interval == 'monthly':
        params['function'] = 'TIME_SERIES_MONTHLY_ADJUSTED'
    else:
        print(f"Invalid interval: {interval}")
        return None

    # Construct the API URL
    url = base_url + '&'.join([f"{key}={value}" for key, value in params.items()])

    data = {}
    try:
        # Make the request
        print(f"Sending API request {api_request_counter + 1} to Alpha Vantage...")
        r = requests.get(url, timeout=10) # Add a timeout to prevent hanging
        r.raise_for_status() # Raise an exception for bad status codes
        data = r.json()
        api_request_counter += 1

        if 'Information' in data:
            print(f"Alpha Vantage Information for {symbol} ({interval}): {data['Information']}")
            if "Our standard API call frequency limit" in data['Information']:
                print("Likely reached the Alpha Vantage API limit.")
                return None # Or raise an exception if you prefer
    except requests.exceptions.RequestException as e:
        print(f"Error during API request for {symbol} ({interval}): {e}")
        return None

    if 'Error Message' in data:
        print(f"Alpha Vantage API Error for {symbol} ({interval}): {data['Error Message']}")
        return None

    # Convert JSON to Pandas DataFrame
    time_series_key = None
    if 'Time Series ({} min)'.format(interval.replace('min', '')) in data:
        time_series_key = 'Time Series ({} min)'.format(interval.replace('min', ''))
    elif 'Time Series (Daily)' in data:
        time_series_key = 'Time Series (Daily)'
    elif 'Weekly Adjusted Time Series' in data:
        time_series_key = 'Weekly Adjusted Time Series'
    elif 'Monthly Adjusted Time Series' in data:
        time_series_key = 'Monthly Adjusted Time Series'

    if time_series_key:
        df = pd.DataFrame.from_dict(data[time_series_key], orient='index')
        df.index = pd.to_datetime(df.index)
        df.sort_index(inplace=True)

        # Save the DataFrame locally to CSV for caching
        filename = f"data/{symbol}_{interval}.csv" # Assuming a 'data' folder exists
        os.makedirs('data', exist_ok=True)
        df.to_csv(filename)
        print(f"Saved data for {symbol} ({interval}) to {filename}")
        print(f"URL: {url}") # Print the constructed URL for verification

        return df
    else:
        print(f"Could not find time series data in response for {symbol} ({interval})")
        return None

def load_crypto_data(symbol, start_date, end_date):
    """
    Loads historical cryptocurrency data for a given symbol from Finnhub.
    """
    # Placeholder for crypto data loading if you decide to add it later
    pass

# Example usage remains similar
if __name__ == "__main__":
    # Example usage to fetch and save data locally
    symbols_to_load = ["NVDA"]#, "NVDA"]
    intervals_to_load = ["5min"]#, "daily", "weekly"] # Be mindful of the API limit
    #start_date = "2023-01-01" # Although this isn't currently used in the function
    #end_date = "2024-12-31"   # Although this isn't currently used in the function

    for symbol in symbols_to_load:
        for interval in intervals_to_load:
            load_stock_data(symbol, interval)#, start_date, end_date)
            # Add a small delay to be cautious with the API rate limit during local testing
            time.sleep(15)