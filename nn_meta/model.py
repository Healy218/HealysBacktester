# nn_meta/model.py
"""Meta-classifier: P(proposed option trade wins). Sigmoid head + BCE,
sample-weighted by |realized net return| so consequential trades dominate."""
import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")   # macOS OpenMP clash

import tensorflow as tf
from tensorflow.keras import layers, regularizers  # type: ignore

from nn_meta import config


def build_meta_mlp(n_features: int, hidden: list[int], lr: float) -> tf.keras.Model:
    inp = layers.Input(shape=(n_features,))
    x = inp
    for units in hidden:
        x = layers.Dense(units, activation="relu",
                         kernel_regularizer=regularizers.l2(config.L2_REG))(x)
        x = layers.Dropout(config.DROPOUT)(x)
    out = layers.Dense(1, activation="sigmoid")(x)
    model = tf.keras.Model(inp, out)
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=lr),
                  loss=tf.keras.losses.BinaryCrossentropy(),
                  weighted_metrics=[tf.keras.metrics.AUC(name="auc")])
    return model


def build_magnitude_mlp(n_features: int, hidden: list[int], lr: float) -> tf.keras.Model:
    """Magnitude head (v4 EV sizing): same trunk as the classifier, linear
    output regressing the signed realized net return under a Huber loss, so a
    handful of multi-bagger option payoffs cannot dominate the fit."""
    inp = layers.Input(shape=(n_features,))
    x = inp
    for units in hidden:
        x = layers.Dense(units, activation="relu",
                         kernel_regularizer=regularizers.l2(config.L2_REG))(x)
        x = layers.Dropout(config.DROPOUT)(x)
    out = layers.Dense(1, activation="linear")(x)
    model = tf.keras.Model(inp, out)
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=lr),
                  loss=tf.keras.losses.Huber(delta=0.5))
    return model
