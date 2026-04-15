# models/data_preprocessing.py
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import vectorbt as vbt

def create_features(df):
    """
    Calculates technical indicators to serve as input features (X).
    """
    # Use close prices for most indicators
    close = df['Close']
    high = df['High']
    low = df['Low']
    volume = df['Volume']

    features = pd.DataFrame(index=df.index)

    # Relative Strength Index
    features['RSI_14'] = vbt.RSI.run(close, window=14).rsi
    
    # Moving Averages
    features['SMA_20_DIFF'] = (close - vbt.MA.run(close, window=20).ma) / close
    features['SMA_50_DIFF'] = (close - vbt.MA.run(close, window=50).ma) / close
    features['EMA_20_DIFF'] = (close - vbt.MA.run(close, window=20, ewm=True).ma) / close

    # MACD
    macd = vbt.MACD.run(close, fast_window=12, slow_window=26, signal_window=9)
    features['MACD'] = macd.macd
    features['MACD_SIGNAL'] = macd.signal
    features['MACD_DIFF'] = macd.diff

    # Bollinger Bands
    bbands = vbt.BBANDS.run(close, window=20, alpha=2.0)
    features['BB_UPPER_DIFF'] = (bbands.upper - close) / close
    features['BB_LOWER_DIFF'] = (close - bbands.lower) / close
    features['BB_WIDTH'] = bbands.bandwidth

    # ATR (Volatility)
    atr = vbt.ATR.run(high, low, close, window=14).atr
    features['ATR_NORM'] = atr / close

    # Volume
    features['VOL_SMA_DIFF'] = (volume - vbt.MA.run(volume, window=20).ma) / vbt.MA.run(volume, window=20).ma

    # Price Returns (Momentum)
    features['RETURN_1'] = close.pct_change(1)
    features['RETURN_5'] = close.pct_change(5)

    return features

def create_labels(df, forward_periods, return_threshold):
    """
    Calculates forward returns and creates binary labels (y).
    1 if forward return > return_threshold, else 0.
    """
    # Calculate forward percentage return
    forward_return = df['Close'].shift(-forward_periods) / df['Close'] - 1
    
    # Create binary labels
    labels = (forward_return > return_threshold).astype(int)
    
    return labels

def prepare_nn_data(df, config):
    """
    Prepares data for training and testing a neural network.
    """
    # 1. Create Features
    X = create_features(df)
    
    # 2. Create Labels
    y = create_labels(df, config['FORWARD_RETURN_PERIODS'], config['RETURN_THRESHOLD'])
    
    # 3. Combine and drop NaNs (due to indicators and forward shift)
    data = pd.concat([X, y.rename('target')], axis=1).dropna()
    
    X = data.drop(columns=['target'])
    y = data['target']
    
    # 4. Chronological Train/Test Split (Prevent leakage)
    split_idx = int(len(X) * config['TRAIN_TEST_SPLIT'])
    
    X_train = X.iloc[:split_idx]
    y_train = y.iloc[:split_idx]
    X_test = X.iloc[split_idx:]
    y_test = y.iloc[split_idx:]
    
    # 5. Scale Features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    return X_train_scaled, X_test_scaled, y_train, y_test, scaler, X.columns
