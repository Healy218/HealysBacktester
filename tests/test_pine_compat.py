"""Reference-formula and causality checks; not exported TradingView fixtures."""

import numpy as np
import pandas as pd
import pytest

from v3 import pine_compat as pine


def test_ema_starts_on_first_value_and_retains_state_across_na():
    source = pd.Series([np.nan, 10.0, 20.0, np.nan, 30.0], index=list("abcde"))
    result = pine.ema(source, 3)
    pd.testing.assert_series_equal(result, pd.Series([np.nan, 10., 15., 15., 22.5], index=source.index))


def test_rma_uses_full_sma_seed_and_ignores_na_observations():
    result = pine.rma(pd.Series([np.nan, 3., 6., np.nan, 9., 12.]), 3)
    np.testing.assert_allclose(result, [np.nan, np.nan, np.nan, np.nan, 6., 8.], equal_nan=True)


def test_sma_uses_non_na_count_instead_of_fixed_bar_window():
    result = pine.sma(pd.Series([1., np.nan, 3., 5., np.nan, 7.]), 3)
    np.testing.assert_allclose(result, [np.nan, np.nan, np.nan, 3., 3., 5.], equal_nan=True)


def test_atr_includes_initial_high_low_and_overnight_gap():
    bars = pd.DataFrame({"high": [11., 15., 13.], "low": [9., 13., 10.], "close": [10., 14., 11.]})
    np.testing.assert_allclose(pine.atr(bars, 2), [np.nan, 3.5, 3.75], equal_nan=True)


def test_rsi_directional_and_undefined_flat_edges():
    np.testing.assert_allclose(pine.rsi(pd.Series([1., 2., 3., 4.]), 2),
                               [np.nan, np.nan, 100., 100.], equal_nan=True)
    np.testing.assert_allclose(pine.rsi(pd.Series([4., 3., 2., 1.]), 2),
                               [np.nan, np.nan, 0., 0.], equal_nan=True)
    assert pine.rsi(pd.Series([4.] * 5), 2).isna().all()
    np.testing.assert_allclose(pine.rsi(pd.Series([1., 3., 2., 5.]), 2).iloc[2:],
                               [100 * 2 / 3, 100 * 2 / 2.25])


def test_rounding_ties_are_toward_positive_infinity():
    np.testing.assert_allclose(pine.round_half_up(np.array([-2.5, -1.5, 1.5, 2.5, np.nan])),
                               [-2., -1., 2., 3., np.nan], equal_nan=True)


def test_supertrend_reference_direction_and_band_transitions():
    bars = pd.DataFrame({"high": [11., 12., 16., 11., 9.], "low": [9., 10., 14., 9., 7.],
                         "close": [10., 11., 15., 10., 8.]})
    result = pine.supertrend(bars, 1., 2)
    # ATR: na, 2, 3.5, 4.75, 3.875. Prior bands determine transitions.
    np.testing.assert_allclose(result.direction, [1., 1., -1., 1., 1.])
    np.testing.assert_allclose(result.supertrend.iloc[1:], [13., 11.5, 14.75, 11.875])


def test_every_primitive_is_prefix_invariant():
    close = pd.Series([10., 11., 12., 11., 9., 12., 13., 8., 10.])
    bars = pd.DataFrame({"high": close + 1., "low": close - 1., "close": close})
    factor = pd.Series(np.linspace(1., 2., len(bars)))
    for length in (1, 3):
        for helper in (pine.sma, pine.ema, pine.rma, pine.rsi):
            full = helper(close, length)
            for end in range(1, len(bars) + 1):
                pd.testing.assert_series_equal(helper(close.iloc[:end], length), full.iloc[:end])
        full = pine.supertrend(bars, factor, length)
        for end in range(1, len(bars) + 1):
            pd.testing.assert_frame_equal(pine.supertrend(bars.iloc[:end], factor.iloc[:end], length), full.iloc[:end])


@pytest.mark.parametrize("length", [0, -1, 2.5, True])
def test_invalid_lengths_fail(length):
    with pytest.raises(ValueError, match="positive integer"):
        pine.ema(pd.Series([1., 2.]), length)
