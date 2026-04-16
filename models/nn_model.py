# models/nn_model.py
import os
import re
import tensorflow as tf
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import Dense, Dropout, Input, LSTM, BatchNormalization
from tensorflow.keras.callbacks import EarlyStopping

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "saved_models")

def create_model(input_shape, mode='classification'):
    """
    Creates an LSTM-based brain for sequence learning.
    input_shape: (time_steps, num_features)
    """
    model = Sequential([
        Input(shape=input_shape),
        LSTM(64, return_sequences=True),
        BatchNormalization(),
        Dropout(0.2),
        LSTM(32),
        BatchNormalization(),
        Dropout(0.2),
        Dense(16, activation='relu'),
        Dense(1, activation='sigmoid' if mode == 'classification' else 'linear')
    ])
    
    if mode == 'classification':
        model.compile(
            optimizer='adam', 
            loss='binary_crossentropy', 
            metrics=['accuracy', tf.keras.metrics.AUC(name='auc')]
        )
    else:
        model.compile(optimizer='adam', loss='mse', metrics=['mae'])
    return model

def train_model(model, X_train, y_train, config):
    """
    Trains the neural network model with early stopping.
    """
    early_stop = EarlyStopping(
        monitor='val_loss', 
        patience=5, 
        restore_best_weights=True
    )
    
    history = model.fit(
        X_train, y_train,
        epochs=config['EPOCHS'],
        batch_size=config['BATCH_SIZE'],
        validation_split=config['VALIDATION_SPLIT'],
        callbacks=[early_stop],
        verbose=1
    )
    
    return model, history

def predict_probabilities(model, X):
    """
    Predicts buy probabilities using the trained neural network.
    """
    probabilities = model.predict(X)
    return probabilities.flatten()


def _next_alpha_version():
    """Finds the next available HealysNNAlpha version number."""
    os.makedirs(MODEL_DIR, exist_ok=True)
    existing = [f for f in os.listdir(MODEL_DIR) if f.startswith("HealysNNAlpha")]
    if not existing:
        return 1
    nums = []
    for f in existing:
        match = re.search(r'HealysNNAlpha(\d+)', f)
        if match:
            nums.append(int(match.group(1)))
    return max(nums) + 1 if nums else 1


def save_model(model, version=None):
    """
    Saves model as HealysNNAlpha{version}.keras.
    Auto-increments if no version is provided.
    Returns the saved file path.
    """
    os.makedirs(MODEL_DIR, exist_ok=True)
    if version is None:
        version = _next_alpha_version()
    name = f"HealysNNAlpha{version}.keras"
    path = os.path.join(MODEL_DIR, name)
    model.save(path)
    return path


def load_alpha_model(version=None):
    """
    Loads a HealysNNAlpha model by version number.
    If no version given, loads the latest.
    """
    if version is None:
        version = _next_alpha_version() - 1
        if version < 1:
            raise FileNotFoundError("No HealysNNAlpha models found.")
    path = os.path.join(MODEL_DIR, f"HealysNNAlpha{version}.keras")
    return load_model(path)
