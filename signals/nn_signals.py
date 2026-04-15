# signals/nn_signals.py
import pandas as pd
import numpy as np
from models.data_preprocessing import create_features
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
    
    # 1. Create features for the provided data
    X = create_features(df)
    
    # 2. Scale features
    # Note: X might have NaNs at the beginning due to indicators
    X_filled = X.fillna(0) # Simple fill for prediction; or drop them and align later
    X_scaled = scaler.transform(X_filled)
    
    # 3. Predict probabilities
    probs = predict_probabilities(model, X_scaled)
    
    # 4. Create Signal Series
    prob_series = pd.Series(probs, index=df.index)
    
    # 5. Generate Entries/Exits based on thresholds
    # Entry: Probability > PROBABILITY_THRESHOLD
    entries = (prob_series > config['PROBABILITY_THRESHOLD']).to_frame(name='nn_signal')
    
    # Exit: Probability < EXIT_PROBABILITY_THRESHOLD
    exits = (prob_series < config['EXIT_PROBABILITY_THRESHOLD']).to_frame(name='nn_signal')
    
    # Align signals (masking rows where features were NaN)
    valid_mask = X.notna().all(axis=1)
    entries[~valid_mask] = False
    exits[~valid_mask] = False
    
    logger.info(f"Generated {entries.sum().iloc[0]} entry signals and {exits.sum().iloc[0]} exit signals.")
    
    return entries, exits, None, None
