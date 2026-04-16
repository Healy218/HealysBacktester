# signals/nn_signals.py
import pandas as pd
import numpy as np
from models.data_preprocessing import create_features, create_sequences
from models.nn_model import predict_probabilities
from utils.logging_utils import setup_logging
from utils.error_handling import handle_errors

logger = setup_logging(log_file="logs/backtester.log")

@handle_errors
def generate_nn_signals(
    df: pd.DataFrame,
    model,
    scaler,
    config: dict
):
    """
    Generates entry and exit signals using a trained neural network.

    Args:
        df: OHLCV DataFrame for the test period.
        model: Trained TensorFlow model.
        scaler: Fitted StandardScaler instance.
        config: STRATEGY_NN configuration dictionary.

    Returns:
        entries, exits, short_entries, short_exits (DataFrames)
    """
    logger.info("Generating Neural Network signals...")
    lookback = config.get('LOOKBACK_WINDOW', 24)

    # 1. Create features for the provided data
    X = create_features(df)

    # 2. Scale features
    # Note: X might have NaNs at the beginning due to indicators
    X_filled = X.fillna(0)
    X_scaled = scaler.transform(X_filled)

    # 3. Create 3D sequences for LSTM: (samples, lookback, features)
    # Use a dummy y since we only need the X sequences for prediction
    dummy_y = np.zeros(len(X_scaled))
    X_seq, _ = create_sequences(X_scaled, dummy_y, window_size=lookback)

    # 4. Predict probabilities
    probs = predict_probabilities(model, X_seq)

    # 5. Create Signal Series — sequences are shorter than df by lookback rows
    # The i-th sequence uses rows [i : i+lookback], so prediction i corresponds
    # to the timestamp at index i+lookback in the original DataFrame.
    seq_index = df.index[lookback:]
    prob_series = pd.Series(probs, index=seq_index)

    # Reindex to full df.index, filling the first lookback rows with NaN
    prob_series = prob_series.reindex(df.index)

    # 6. Generate Entries/Exits based on thresholds
    entries = (prob_series > config['PROBABILITY_THRESHOLD']).fillna(False).to_frame(name='nn_signal')
    exits = (prob_series < config['EXIT_PROBABILITY_THRESHOLD']).fillna(False).to_frame(name='nn_signal')

    # Mask rows where features were NaN (indicator warm-up period)
    valid_mask = X.notna().all(axis=1)
    entries.loc[~valid_mask, 'nn_signal'] = False
    exits.loc[~valid_mask, 'nn_signal'] = False

    logger.info(f"Generated {entries.sum().iloc[0]} entry signals and {exits.sum().iloc[0]} exit signals.")

    return entries, exits, None, None
