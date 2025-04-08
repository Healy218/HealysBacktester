# nn_model.py
import tensorflow as tf

def create_model(input_shape, output_shape):
    """
    Creates a neural network model.
    """
    model = tf.keras.models.Sequential([
        tf.keras.layers.Dense(64, activation='relu', input_shape=input_shape),
        tf.keras.layers.Dense(output_shape, activation='sigmoid') # Example output for buy/sell probability
    ])
    model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
    return model

def train_model(model, features, labels, epochs=10):
    """
    Trains the neural network model.
    """
    model.fit(features, labels, epochs=epochs)
    return model

def predict_signal(model, features):
    """
    Predicts trading signals using the trained neural network.
    """
    predictions = model.predict(features)
    # Convert probabilities to trading signals (e.g., buy if probability > 0.7)
    return signals