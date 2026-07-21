"""Deflated Sharpe and PBO against known analytic cases."""
import numpy as np
import pytest

from nn_meta.multiple_testing import (combinatorial_pbo, deflated_sharpe_ratio,
                                      deflated_sharpe_from_trials,
                                      expected_max_sharpe,
                                      probabilistic_sharpe_ratio,
                                      sharpe_moments)


def test_psr_is_half_at_zero_sharpe():
    assert probabilistic_sharpe_ratio(0.0, 100) == pytest.approx(0.5)


def test_psr_increases_with_sharpe():
    lo = probabilistic_sharpe_ratio(0.05, 200)
    hi = probabilistic_sharpe_ratio(0.15, 200)
    assert 0.5 < lo < hi < 1.0


def test_expected_max_sharpe_grows_with_trials_and_scales_with_sd():
    assert expected_max_sharpe(1, 1.0) == 0.0
    assert expected_max_sharpe(10, 1.0) < expected_max_sharpe(1000, 1.0)
    # Scales with the standard deviation of trial Sharpes.
    assert expected_max_sharpe(50, 4.0) == pytest.approx(2 * expected_max_sharpe(50, 1.0))


def test_deflated_sharpe_falls_as_more_configs_are_tried():
    kwargs = dict(skew=0.0, kurtosis=3.0, variance_trial_sr=0.01)
    few = deflated_sharpe_ratio(0.12, 250, n_trials=3, **kwargs)
    many = deflated_sharpe_ratio(0.12, 250, n_trials=200, **kwargs)
    assert few > many


def test_deflated_sharpe_with_one_trial_equals_undeflated_psr():
    dsr = deflated_sharpe_ratio(0.1, 250, skew=0.0, kurtosis=3.0,
                                n_trials=1, variance_trial_sr=0.01)
    assert dsr == pytest.approx(probabilistic_sharpe_ratio(0.1, 250))


def test_sharpe_moments_on_normal_sample():
    rng = np.random.default_rng(0)
    x = rng.normal(0.01, 0.1, 10000)
    sr, n, skew, kurt = sharpe_moments(x)
    assert n == 10000
    assert sr == pytest.approx(0.1, abs=0.03)
    assert abs(skew) < 0.15 and kurt == pytest.approx(3.0, abs=0.2)


def test_deflated_sharpe_from_trials_needs_two_trials():
    assert deflated_sharpe_from_trials([0.1, -0.1, 0.2], [0.3]) is None


def test_pbo_zero_for_a_dominant_strategy():
    # Strategy 0 is best in every block, in and out of sample -> no overfitting.
    M = np.tile([3.0, 2.0, 1.0], (8, 1))
    out = combinatorial_pbo(M, n_splits=4, metric="mean")
    assert out["pbo"] == 0.0
    assert out["n_combinations"] == 6


def test_pbo_near_half_for_pure_noise():
    rng = np.random.default_rng(1)
    M = rng.normal(size=(400, 10))
    out = combinatorial_pbo(M, n_splits=8, metric="sharpe")
    assert 0.25 < out["pbo"] < 0.75


def test_pbo_validates_inputs():
    with pytest.raises(ValueError, match="2D"):
        combinatorial_pbo(np.zeros(10), n_splits=4)
    with pytest.raises(ValueError, match="even"):
        combinatorial_pbo(np.zeros((10, 3)), n_splits=3)
    with pytest.raises(ValueError, match="more splits"):
        combinatorial_pbo(np.zeros((3, 3)), n_splits=4)
    with pytest.raises(ValueError, match="metric"):
        combinatorial_pbo(np.zeros((10, 3)), n_splits=2, metric="cagr")
