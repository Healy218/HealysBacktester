import pandas as pd
import numpy as np
from numba import njit
from sklearn.preprocessing import StandardScaler
import vectorbt as vbt
import logging

logger = logging.getLogger('backtester')

def create_features(df, market_df=None):
    """
    Advanced features including sequence-ready market correlation.
    """
    try:
        close = df['Close']
        high = df['High']
        low = df['Low']
        volume = df['Volume']

        features = pd.DataFrame(index=df.index)

        # 1. Standard Indicators
        features['RSI_14'] = vbt.RSI.run(close, window=14).rsi
        
        # 2. Volatility Features
        bbands = vbt.BBANDS.run(close, window=20, alpha=2.0)
        features['BB_WIDTH'] = bbands.bandwidth
        features['BB_PERCENT_B'] = bbands.percent_b
        
        # 3. Market Correlation (The "Big Brother" feature)
        if market_df is not None:
            # Align market data to the current ticker index
            m_close = market_df['Close'].reindex(df.index).ffill()
            
            # Relative Momentum (Ticker vs SPY)
            features['rel_momentum_5'] = close.pct_change(5) - m_close.pct_change(5)
            features['rel_momentum_20'] = close.pct_change(20) - m_close.pct_change(20)
            
            # Is the market trending?
            features['m_rsi'] = vbt.RSI.run(m_close, window=14).rsi
        else:
            features['rel_momentum_5'] = 0
            features['rel_momentum_20'] = 0
            features['m_rsi'] = 50

        # 4. Volume Surge
        vol_sma = vbt.MA.run(volume, window=20).ma
        features['VOL_SURGE'] = volume / (vol_sma + 1e-6)

        # 5. Time-of-Day (0 to 1 scale)
        features['market_time'] = (df.index.hour * 60 + df.index.minute - 570) / 390 

        return features
    except Exception as e:
        logger.error(f"Error in create_features: {e}")
        raise

def create_labels(df, forward_periods, return_threshold):
    """
    Calculates forward returns and creates binary labels (y).
    """
    forward_return = df['Close'].shift(-forward_periods) / df['Close'] - 1
    labels = (forward_return > return_threshold).astype(int)
    return labels

@njit
def _triple_barrier_numba(close_arr, horizon, pt, sl):
    """
    Numba-accelerated triple barrier labeling.
    Returns an int array of labels (1 = profit target hit first, 0 otherwise).
    """
    n = len(close_arr)
    labels = np.zeros(n, dtype=np.int64)
    for i in range(n - horizon):
        entry_price = close_arr[i]
        for j in range(i + 1, i + horizon + 1):
            ret = close_arr[j] / entry_price - 1.0
            if ret >= pt:
                labels[i] = 1
                break
            if ret <= -sl:
                break
    return labels


def create_triple_barrier_labels(df, horizon, pt, sl_mult):
    """
    Triple Barrier Method for labeling.
    1 if price hits Profit Target (pt) before Stop Loss or Horizon.
    0 otherwise.

    Uses Numba @njit for performance on large datasets (20k+ bars).
    """
    close_arr = df['Close'].values.astype(np.float64)
    sl = pt * sl_mult
    labels_arr = _triple_barrier_numba(close_arr, horizon, pt, sl)
    return pd.Series(labels_arr, index=df.index)

def create_sequences(X, y, window_size=30):
    """
    Reshapes 2D features into 3D sequences for LSTM.
    """
    Xs, ys = [], []
    for i in range(len(X) - window_size):
        Xs.append(X[i:(i + window_size)])
        ys.append(y[i + window_size])
    return np.array(Xs), np.array(ys)

def prepare_nn_data(df, config, forward_periods, mode='classification', use_sequences=True, market_df=None):
    """
    Prepares data for training (supports 3D sequences and market correlation).
    """
    try:
        # 1. Create Features
        X = create_features(df, market_df=market_df)
        
        # 2. Create Labels
        if mode == 'triple_barrier':
            y = create_triple_barrier_labels(
                df, 
                horizon=forward_periods, 
                pt=config['RETURN_THRESHOLD'], 
                sl_mult=config.get('STOP_LOSS_MULT', 0.5)
            )
        elif mode == 'regression':
            y = df['Close'].shift(-forward_periods) / df['Close'] - 1
        else:
            y = create_labels(df, forward_periods, config['RETURN_THRESHOLD'])
        
        # 3. Combine and drop NaNs
        data = pd.concat([X, y.rename('target')], axis=1).dropna()
        
        X_df = data.drop(columns=['target'])
        y_series = data['target']
        
        # 4. Chronological Train/Test Split
        split_idx = int(len(X_df) * config['TRAIN_TEST_SPLIT'])
        
        X_train_raw = X_df.iloc[:split_idx]
        y_train_raw = y_series.iloc[:split_idx]
        X_test_raw = X_df.iloc[split_idx:]
        y_test_raw = y_series.iloc[split_idx:]
        
        # 5. Scale Features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train_raw)
        X_test_scaled = scaler.transform(X_test_raw)
        
        # 6. Create Sequences if needed (LSTM requirement)
        if use_sequences:
            window = config.get('LOOKBACK_WINDOW', 24)
            X_train, y_train = create_sequences(X_train_scaled, y_train_raw.values, window)
            X_test, y_test = create_sequences(X_test_scaled, y_test_raw.values, window)
            return X_train, X_test, y_train, y_test, scaler, X_df.columns
        
        return X_train_scaled, X_test_scaled, y_train_raw, y_test_raw, scaler, X_df.columns
    except Exception as e:
        logger.error(f"Error in prepare_nn_data: {e}")
        raise
