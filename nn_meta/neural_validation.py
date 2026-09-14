"""Train-only missingness policy and fail-closed neural numerical checks.

An entirely unobserved training feature is disabled for that fit, including
at inference. Validation data never supplies a mean or activates a feature.
NaN is missing data; infinity and float32 overflow are errors.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

POLICY = "train-only-inactive-zero-v1"


def require_finite(values, name, *, binary=False):
    values = np.asarray(values)
    for start in range(0, len(values), 65536):
        block = values[start:start + 65536]
        if not np.isfinite(block).all():
            raise ValueError(f"{name} contains non-finite values")
        if binary and not np.isin(block, [0, 1]).all():
            raise ValueError(f"{name} must contain binary labels")
    return values


def fit_scaler(train, features):
    if train.empty or not features or len(set(features)) != len(features):
        raise ValueError("scaler requires training rows and unique features")
    counts, means, deviations = {}, {}, {}
    for feature in features:
        values = train[feature].to_numpy(dtype=float)
        if np.isinf(values).any():
            raise ValueError(f"training feature {feature} contains infinity")
        counts[feature] = int(np.isfinite(values).sum())
        means[feature] = float(train[feature].mean()) if counts[feature] else 0.0
        std = float(train[feature].std()) if counts[feature] > 1 else 1.0
        deviations[feature] = std if std != 0 else 1.0
    mean, std = pd.Series(means), pd.Series(deviations)
    validate_scaler(features, mean, std)
    inactive = [f for f in features if counts[f] == 0]
    return mean, std, {"policy": POLICY, "inactive": inactive,
                       "observed_train_counts": counts}


def validate_scaler(features, mean, std, inactive=()):
    if set(features) != set(mean.index) or set(features) != set(std.index):
        raise ValueError("scaler feature schema mismatch")
    require_finite(mean.to_numpy(), "scaler means")
    require_finite(std.to_numpy(), "scaler standard deviations")
    if (std <= 0).any() or not set(inactive) <= set(features):
        raise ValueError("invalid scaler deviations or inactive features")


def matrix(rows, features, mean, std, inactive=()):
    validate_scaler(features, mean, std, inactive)
    values = rows[features].copy()
    if np.isinf(values.to_numpy(dtype=float)).any():
        raise ValueError("neural features contain infinity")
    values = (values.fillna(mean) - mean) / std
    if inactive:
        values.loc[:, list(inactive)] = 0.0
    with np.errstate(over="ignore", invalid="ignore"):
        result = values.to_numpy(dtype="float32")
    return require_finite(result, "standardized neural features")


def finite_callback():
    import tensorflow as tf

    class FiniteLoss(tf.keras.callbacks.Callback):
        def on_train_batch_end(self, batch, logs=None):
            self.check(logs)

        def on_epoch_end(self, epoch, logs=None):
            self.check(logs)

        @staticmethod
        def check(logs):
            for name, value in (logs or {}).items():
                require_finite(np.atleast_1d(value), f"training {name}")

    return FiniteLoss()


def validate_weights(model):
    for weight in model.weights:
        require_finite(np.asarray(weight.numpy()).reshape(-1), f"model weight {weight.name}")


def validate_fit(model, history, x_val, *, head):
    for name in ("loss", "val_loss"):
        values = history.history.get(name, [])
        if not len(values):
            raise ValueError(f"{head} training lacks {name}")
        require_finite(np.asarray(values), f"{head} {name}")
    validate_weights(model)
    for start in range(0, len(x_val), 65536):
        predictions = model.predict(x_val[start:start + 65536], batch_size=4096, verbose=0)
        require_finite(predictions, f"{head} validation predictions")
    return {"val_loss": float(min(history.history["val_loss"])),
            "finite_losses": True, "finite_weights": True,
            "finite_predictions": True, "validation_rows": len(x_val)}
