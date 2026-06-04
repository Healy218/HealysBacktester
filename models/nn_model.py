# models/nn_model.py
import os
import tensorflow as tf
from tensorflow.keras.models import Sequential  # type: ignore
from tensorflow.keras.layers import LSTM, Dense, Dropout, Input  # type: ignore
from tensorflow.keras.callbacks import EarlyStopping  # type: ignore

def create_model(input_shape, mode='classification'):
    """
    Creates an LSTM neural network model.

    Args:
        input_shape: Tuple of (lookback_window, n_features) for 3D sequence input,
                     or (n_features,) for 2D flat input.
        mode: 'classification' for binary buy/no-buy signals (sigmoid output),
              'regression' for continuous return prediction (linear output).
    """
    model = Sequential()
    model.add(Input(shape=input_shape))

    if len(input_shape) == 2:
        # 3D sequence input (lookback, features) -> LSTM
        model.add(LSTM(64, return_sequences=True))
        model.add(Dropout(0.2))
        model.add(LSTM(32, return_sequences=False))
        model.add(Dropout(0.2))
    else:
        # 2D flat input fallback -> Dense
        model.add(Dense(64, activation='relu'))
        model.add(Dropout(0.2))
        model.add(Dense(32, activation='relu'))
        model.add(Dropout(0.2))

    model.add(Dense(16, activation='relu'))

    if mode == 'regression':
        model.add(Dense(1, activation='linear'))
        model.compile(
            optimizer='adam',
            loss='mse',
            metrics=['mae']
        )
    else:
        model.add(Dense(1, activation='sigmoid'))
        model.compile(
            optimizer='adam',
            loss='binary_crossentropy',
            metrics=['accuracy', tf.keras.metrics.AUC(name='auc')]
        )

    return model

def train_model(model, X_train, y_train, config, class_weight=None):
    """
    Trains the neural network model with early stopping.

    Args:
        model: Compiled Keras model.
        X_train: Training features.
        y_train: Training labels.
        config: Dict with EPOCHS, BATCH_SIZE, VALIDATION_SPLIT keys.
        class_weight: Optional dict mapping class indices to weights
                      (e.g. {0: 1.0, 1: 2.5}) to handle imbalanced labels.
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
        class_weight=class_weight,
        verbose=1
    )

    return model, history

def predict_probabilities(model, X):
    """
    Predicts buy probabilities using the trained neural network.
    """
    probabilities = model.predict(X)
    return probabilities.flatten()

def save_model(model, save_dir='models/saved'):
    """
    Saves a trained model to disk.

    Args:
        model: Trained Keras model.
        save_dir: Directory to save into.

    Returns:
        Path to the saved model file.
    """
    os.makedirs(save_dir, exist_ok=True)
    path = os.path.join(save_dir, 'nn_model.keras')
    model.save(path)
    return path

def load_model(path='models/saved/nn_model.keras'):
    """
    Loads a previously saved model from disk.
    """
    return tf.keras.models.load_model(path)
