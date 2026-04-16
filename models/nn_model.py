# models/nn_model.py
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, Input
from tensorflow.keras.callbacks import EarlyStopping

def create_model(input_shape):
    """
    Creates a neural network model for binary classification.
    """
    model = Sequential([
        Input(shape=(input_shape,)),
        Dense(64, activation='relu'),
        Dropout(0.2),
        Dense(32, activation='relu'),
        Dropout(0.2),
        Dense(16, activation='relu'),
        Dense(1, activation='sigmoid') # Buy probability
    ])
    
    model.compile(
        optimizer='adam', 
        loss='binary_crossentropy', 
        metrics=['accuracy', tf.keras.metrics.AUC(name='auc')]
    )
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
