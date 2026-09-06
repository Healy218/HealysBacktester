"""Fold-local probability calibration for the v4 meta-classifier.

Raw sigmoid / GBT scores rank trades well but are not calibrated
probabilities.  These calibrators are fit on the validation slice only and
applied to the test slice, so test outcomes never inform the mapping — the same
nested-selection discipline the rest of the v4 contract enforces.  Both
calibrators are pure-numpy to keep the local test suite dependency-free.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def brier_score(prob, label) -> float:
    """Mean squared error between predicted probability and 0/1 outcome."""
    p = np.asarray(prob, dtype=float)
    y = np.asarray(label, dtype=float)
    if len(p) == 0:
        return float("nan")
    return float(np.mean((p - y) ** 2))


@dataclass(frozen=True)
class PlattCalibrator:
    """Sigmoid calibration: p = sigmoid(a * score + b)."""

    a: float
    b: float

    def predict(self, scores) -> np.ndarray:
        z = self.a * np.asarray(scores, dtype=float) + self.b
        return 1.0 / (1.0 + np.exp(-z))


def fit_platt(scores, labels, *, max_iter: int = 100, tol: float = 1e-9) -> PlattCalibrator:
    """Fit Platt scaling by Newton's method on the validation slice."""
    s = np.asarray(scores, dtype=float)
    y = np.asarray(labels, dtype=float)
    a, b = 1.0, 0.0
    for _ in range(max_iter):
        p = 1.0 / (1.0 + np.exp(-(a * s + b)))
        w = np.clip(p * (1.0 - p), 1e-12, None)
        g_a, g_b = float(np.sum((p - y) * s)), float(np.sum(p - y))
        h_aa, h_ab, h_bb = float(np.sum(w * s * s)), float(np.sum(w * s)), float(np.sum(w))
        det = h_aa * h_bb - h_ab * h_ab
        if abs(det) < 1e-12:
            break
        da = (h_bb * g_a - h_ab * g_b) / det
        db = (h_aa * g_b - h_ab * g_a) / det
        a, b = a - da, b - db
        if max(abs(da), abs(db)) < tol:
            break
    return PlattCalibrator(float(a), float(b))


@dataclass(frozen=True)
class IsotonicCalibrator:
    """Monotone step calibration built from pool-adjacent-violators breakpoints."""

    x: np.ndarray
    y: np.ndarray

    def predict(self, scores) -> np.ndarray:
        return np.interp(np.asarray(scores, dtype=float), self.x, self.y,
                         left=float(self.y[0]), right=float(self.y[-1]))


def _pav(values: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Pool-adjacent-violators: nearest non-decreasing fit, same length."""
    blocks: list[list[float]] = []  # [value, weight, count]
    for v, w in zip(values, weights):
        blocks.append([float(v), float(w), 1.0])
        while len(blocks) >= 2 and blocks[-2][0] >= blocks[-1][0]:
            v2, w2, c2 = blocks.pop()
            v1, w1, c1 = blocks.pop()
            nw = w1 + w2
            blocks.append([(v1 * w1 + v2 * w2) / nw, nw, c1 + c2])
    out: list[float] = []
    for v, _, c in blocks:
        out.extend([v] * int(c))
    return np.asarray(out, dtype=float)


def fit_isotonic(scores, labels) -> IsotonicCalibrator:
    """Fit isotonic regression on the validation slice."""
    s = np.asarray(scores, dtype=float)
    y = np.asarray(labels, dtype=float)
    order = np.argsort(s, kind="mergesort")
    s_sorted, y_sorted = s[order], y[order]
    xs, first = np.unique(s_sorted, return_index=True)
    sums = np.add.reduceat(y_sorted, first)
    counts = np.diff(np.append(first, len(y_sorted)))
    ys = _pav(sums / counts, counts)
    if len(xs) == 1:  # np.interp needs at least two breakpoints
        xs = np.array([xs[0], xs[0] + 1e-9])
        ys = np.array([ys[0], ys[0]])
    return IsotonicCalibrator(xs, ys)


@dataclass(frozen=True)
class IdentityCalibrator:
    """The 'no calibration' choice: raw scores pass through unchanged. A real
    candidate in selection, so a calibrator only ships when it beats raw."""

    def predict(self, scores) -> np.ndarray:
        return np.asarray(scores, dtype=float)


def fit_calibrator(method: str, scores, labels):
    """Return a fitted calibrator; only validation-slice data is passed in."""
    if method == "none":
        return IdentityCalibrator()
    if method == "isotonic":
        return fit_isotonic(scores, labels)
    if method == "platt":
        return fit_platt(scores, labels)
    raise ValueError("method must be 'none', 'isotonic', or 'platt'")


def _cv_brier(method: str, s: np.ndarray, y: np.ndarray, n_splits: int) -> float:
    """Mean out-of-fold Brier for ``method`` under k-fold CV on validation.

    Interleaved (index % k) folds keep it deterministic — no RNG, which the
    workflow environment forbids and which would break resume."""
    folds = np.arange(len(s)) % n_splits
    errs = []
    for k in range(n_splits):
        tr, te = folds != k, folds == k
        if te.sum() == 0 or tr.sum() < 2 or len(np.unique(y[tr])) < 2:
            continue
        pred = fit_calibrator(method, s[tr], y[tr]).predict(s[te])
        errs.append(brier_score(pred, y[te]))
    return float(np.mean(errs)) if errs else float("nan")


def select_calibrator(val_scores, val_labels, *,
                      methods=("none", "platt", "isotonic"), n_splits: int = 3):
    """Pick the calibrator with the best out-of-fold validation Brier.

    Includes ``none`` (raw scores) as a candidate, so isotonic — which can
    perfectly fit a small validation tail and then generalize badly (the v3.1
    smoke runs mapped 100+ test trades to p=1.0) — is chosen only when it
    actually beats raw scores out-of-fold. Returns ``(method_name, calibrator)``.
    Fits solely on validation; test never enters here.
    """
    s = np.asarray(val_scores, dtype=float)
    y = np.asarray(val_labels, dtype=float)
    mask = ~(np.isnan(s) | np.isnan(y))
    s, y = s[mask], y[mask]
    # Too little data (or one class) to validate a calibrator — keep raw scores.
    if len(s) < 2 * n_splits or len(np.unique(y)) < 2:
        return "none", IdentityCalibrator()
    scored = [(m, _cv_brier(m, s, y, n_splits)) for m in methods]
    scored = [(m, b) for m, b in scored if not np.isnan(b)]
    if not scored:
        return "none", IdentityCalibrator()
    best = min(scored, key=lambda mb: mb[1])[0]
    return best, fit_calibrator(best, s, y)  # refit the winner on all validation


def reliability_table(prob, label, n_bins: int = 10) -> pd.DataFrame:
    """Binned reliability: predicted probability vs realized frequency."""
    p = np.asarray(prob, dtype=float)
    y = np.asarray(label, dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, n_bins - 1)
    rows = []
    for b in range(n_bins):
        m = idx == b
        if not m.any():
            continue
        rows.append({"bin": f"[{edges[b]:.1f},{edges[b + 1]:.1f})",
                     "n": int(m.sum()), "mean_pred": float(p[m].mean()),
                     "frac_pos": float(y[m].mean())})
    return pd.DataFrame(rows)


def calibration_summary(val_labels, val_scores, test_labels, test_scores, *,
                        method: str = "auto", n_bins: int = 10) -> dict | None:
    """Fit on validation, score test: Brier (raw vs calibrated) and reliability.

    ``method="auto"`` (default) selects among none/platt/isotonic by out-of-fold
    validation Brier (:func:`select_calibrator`), so a calibrator ships only
    when it beats raw scores — the fix for isotonic overfitting small validation
    tails. A fixed ``method`` still forces that calibrator. Either way the
    calibrator is fit strictly from ``val_*``; ``test_*`` is only scored.
    """
    v = pd.DataFrame({"y": np.asarray(val_labels, dtype=float),
                      "s": np.asarray(val_scores, dtype=float)}).dropna()
    t = pd.DataFrame({"y": np.asarray(test_labels, dtype=float),
                      "s": np.asarray(test_scores, dtype=float)}).dropna()
    if v.empty or t.empty:
        return None
    if method == "auto":
        chosen, cal = select_calibrator(v["s"].to_numpy(), v["y"].to_numpy())
    else:
        chosen, cal = method, fit_calibrator(method, v["s"].to_numpy(), v["y"].to_numpy())
    test_calibrated = cal.predict(t["s"].to_numpy())
    return {
        "method": chosen,
        "selection": "auto (min OOF validation Brier)" if method == "auto" else "fixed",
        "brier_raw": brier_score(t["s"].to_numpy(), t["y"].to_numpy()),
        "brier_calibrated": brier_score(test_calibrated, t["y"].to_numpy()),
        "reliability": reliability_table(test_calibrated, t["y"].to_numpy(), n_bins)
        .to_dict("records"),
    }
