# nn_options_signal/model.py
"""Small MLP regressor: predicted net H-day option return, Huber loss."""
import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")   # macOS OpenMP clash

import tensorflow as tf
from tensorflow.keras import layers, regularizers  # type: ignore

from nn_options_signal import config


def build_mlp(n_features: int, hidden: list[int], lr: float) -> tf.keras.Model:
    inp = layers.Input(shape=(n_features,))
    x = inp
    for units in hidden:
        x = layers.Dense(units, activation="relu",
                         kernel_regularizer=regularizers.l2(config.L2_REG))(x)
        x = layers.Dropout(config.DROPOUT)(x)
    out = layers.Dense(1, activation="linear")(x)
    model = tf.keras.Model(inp, out)
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=lr),
                  loss=tf.keras.losses.Huber(delta=config.HUBER_DELTA))
    return model
