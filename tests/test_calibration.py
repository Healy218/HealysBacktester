"""Fold-local calibration: correctness and the never-sees-test-rows guarantee."""
import numpy as np
import pytest

from nn_meta.calibration import (brier_score, calibration_summary,
                                 fit_calibrator, fit_isotonic, fit_platt,
                                 reliability_table, select_calibrator, _cv_brier)


def test_brier_score_matches_hand_value():
    assert brier_score([0.5, 0.5], [1, 0]) == pytest.approx(0.25)
    assert brier_score([1.0, 0.0], [1, 0]) == pytest.approx(0.0)


def _miscalibrated(n, seed):
    """Scores that rank correctly but overstate the true probability (p = s**3)."""
    rng = np.random.default_rng(seed)
    s = rng.uniform(0.0, 1.0, n)
    y = (rng.uniform(size=n) < s ** 3).astype(float)
    return s, y


def test_platt_reduces_brier_on_miscalibrated_scores():
    s, y = _miscalibrated(5000, 0)
    cal = fit_platt(s, y)
    assert brier_score(cal.predict(s), y) < brier_score(s, y)


def test_isotonic_is_monotone_and_reduces_brier():
    s, y = _miscalibrated(5000, 1)
    cal = fit_isotonic(s, y)
    grid = np.linspace(0, 1, 50)
    preds = cal.predict(grid)
    assert np.all(np.diff(preds) >= -1e-9)               # non-decreasing
    assert brier_score(cal.predict(s), y) < brier_score(s, y)


def test_isotonic_handles_degenerate_single_score():
    cal = fit_isotonic(np.full(10, 0.4), np.array([1, 0, 1, 1, 0, 1, 0, 1, 1, 0.0]))
    assert np.isfinite(cal.predict([0.4, 0.9]))[0]


def test_reliability_table_counts_cover_all_rows():
    s, y = _miscalibrated(1000, 2)
    table = reliability_table(s, y, n_bins=10)
    assert table["n"].sum() == len(s)


def test_fit_calibrator_rejects_unknown_method():
    with pytest.raises(ValueError, match="isotonic.*platt|method"):
        fit_calibrator("sigmoid_v2", [0.1], [1])


def test_calibrator_never_sees_test_labels():
    val_s, val_y = _miscalibrated(3000, 3)
    rng = np.random.default_rng(4)
    test_s = rng.uniform(0, 1, 1500)
    test_y = (rng.uniform(size=1500) < test_s ** 3).astype(float)
    flipped = 1.0 - test_y   # a completely different test-label vector

    out = calibration_summary(val_y, val_s, test_y, test_s)
    out_flipped = calibration_summary(val_y, val_s, flipped, test_s)

    # Bin membership and calibrated mean prediction depend only on the
    # validation fit and the test scores, never on the test labels.
    mean_pred = [r["mean_pred"] for r in out["reliability"]]
    mean_pred_flipped = [r["mean_pred"] for r in out_flipped["reliability"]]
    counts = [r["n"] for r in out["reliability"]]
    counts_flipped = [r["n"] for r in out_flipped["reliability"]]
    assert mean_pred == pytest.approx(mean_pred_flipped)
    assert counts == counts_flipped
    # The realized frequency, which does depend on labels, differs.
    assert out["brier_calibrated"] != pytest.approx(out_flipped["brier_calibrated"])


def test_calibration_summary_returns_none_on_empty_slice():
    assert calibration_summary([], [], [1], [0.5]) is None


# ── auto calibrator selection (item 6) ──────────────────────────────────────

def test_select_calibrator_falls_back_to_none_on_tiny_val():
    method, cal = select_calibrator([0.4, 0.6, 0.5], [0, 1, 1])
    assert method == "none"
    assert np.allclose(cal.predict([0.3, 0.7]), [0.3, 0.7])   # identity passthrough


def test_select_calibrator_returns_none_when_val_is_single_class():
    method, _ = select_calibrator(np.linspace(0.1, 0.9, 20), np.ones(20))
    assert method == "none"


def test_select_calibrator_never_worse_out_of_fold_than_raw():
    # The winner is the argmin of OOF Brier over methods that include 'none',
    # so it can never be beaten by raw scores out-of-fold — the whole point.
    s, y = _miscalibrated(2000, 7)
    method, _ = select_calibrator(s, y)
    none_b = _cv_brier("none", np.asarray(s, float), np.asarray(y, float), 3)
    chosen_b = _cv_brier(method, np.asarray(s, float), np.asarray(y, float), 3)
    assert chosen_b <= none_b + 1e-12


def test_select_calibrator_picks_real_calibration_when_clearly_miscalibrated():
    s, y = _miscalibrated(4000, 8)
    method, cal = select_calibrator(s, y)
    assert method in ("platt", "isotonic")
    assert brier_score(cal.predict(s), y) < brier_score(s, y)


def test_calibration_summary_auto_reports_the_chosen_method():
    s, y = _miscalibrated(3000, 9)
    out = calibration_summary(y, s, y[:1500], s[:1500], method="auto")
    assert out["method"] in ("none", "platt", "isotonic")
    assert out["selection"].startswith("auto")


def test_calibration_summary_none_method_is_identity():
    s, y = _miscalibrated(500, 10)
    out = calibration_summary(y, s, y, s, method="none")
    assert out["method"] == "none"
    assert out["brier_calibrated"] == pytest.approx(out["brier_raw"])
