# data_preprocessing.py
import pandas as pd
import numpy as np
import talib

def clean_data(df):
    """
    Cleans the input DataFrame by handling missing values and outliers.
    """
    # Convert columns to numeric, coercing errors to NaN
    for col in df.columns:
        if col != 'timestamp':  # Keep timestamp as string for now
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Handle missing values (example: fill with mean)
    for col in df.columns:
        if df[col].isnull().any() and col != 'timestamp':
            df[col].fillna(df[col].mean(), inplace=True)

    # Identify and handle outliers (example: using z-score)
    for col in df.columns:
        if df[col].dtype in ['int64', 'float64']:
            mean = df[col].mean()
            std = df[col].std()
            if std != 0:
                df['zscore_' + col] = np.abs((df[col] - mean) / std)
                df.drop(df[df['zscore_' + col] > 3].index, inplace=True) # Remove outliers with z-score > 3
                df.drop(columns=['zscore_' + col], inplace=True)
    return df

def feature_engineer(df):
    """
    Engineers new features from the raw data, such as technical indicators.
    """
    # Ensure necessary columns exist and are numeric
    if '4. close' in df.columns:
        close_prices = pd.to_numeric(df['4. close'], errors='coerce').dropna()
        # Calculate moving averages (example: 20 and 50 periods)
        df['SMA_20'] = close_prices.rolling(window=20).mean()
        df['SMA_50'] = close_prices.rolling(window=50).mean()

        # Calculate RSI (example: 14 periods)
        if len(close_prices) > 14:
            df['RSI_14'] = talib.RSI(close_prices.values, timeperiod=14)

        # Calculate MACD (example: 12, 26, 9 periods)
        if len(close_prices) > 26:
            macd, macdsignal, macdhist = talib.MACD(close_prices.values, fastperiod=12, slowperiod=26, signalperiod=9)
            df['MACD'] = macd
            df['MACD_SIGNAL'] = macdsignal

    return df

# Pseudo-code for other preprocessing functions