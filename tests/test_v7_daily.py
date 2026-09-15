import numpy as np
import pandas as pd
import pytest

from nn_meta.session_calendar import SessionCalendar
from nn_meta.v7.daily import daily_context, surface_day


def fixture():
    days = pd.bdate_range('2022-01-03', periods=71).strftime('%Y-%m-%d').tolist()
    calendar = SessionCalendar({'coverage_start': days[0], 'coverage_end': days[-1],
        'sessions': [{'date': d, 'open': '09:30', 'close': '16:00'} for d in days]})
    prices = 100 + np.arange(70) * .1 + np.sin(np.arange(70))
    stock = pd.DataFrame({'source_date': days[:-1], 'raw_close': prices * 2, 'adjusted_close': prices})
    surfaces = pd.DataFrame({'source_date': days[:-1], 'atm_iv_near': .3,
                            'atm_iv_far': .35, 'pc_ratio': 1., 'capture_complete': True})
    return stock, surfaces, calendar


def test_daily_context_is_prefix_invariant_and_available_next_session():
    stock, surfaces, calendar = fixture()
    result = daily_context(stock, surfaces, calendar, security_id='SPY', is_market=True)
    part = daily_context(stock.iloc[:65], surfaces.iloc[:65], calendar, security_id='SPY', is_market=True)
    pd.testing.assert_frame_equal(result.iloc[:65], part)
    assert result.index[0] == calendar.bounds('2022-01-04')[0].tz_localize('UTC')
    assert result.beta_60d.iloc[-1] == pytest.approx(1.)


def test_missing_aggregate_day_cannot_be_forward_filled_and_market_is_explicit():
    stock, surfaces, calendar = fixture()
    with pytest.raises(ValueError, match='Missing aggregate'):
        daily_context(stock, surfaces.drop(20), calendar, security_id='SPY', is_market=True)
    with pytest.raises(ValueError, match='market context'):
        daily_context(stock, surfaces, calendar, security_id='MSFT')


def test_surface_uses_raw_spot_and_preserves_observed_absence():
    options = pd.DataFrame({'ticker': ['O:SPY220311C00420000', 'O:SPY220415C00420000',
                                       'O:SPY220311P00420000'],
                            'close': [3., 10., 3.], 'volume': [100., 100., 50.]})
    row = surface_day('SPY', '2022-03-07', options, 420.)
    assert np.isfinite(row['atm_iv_near']) and np.isfinite(row['atm_iv_far'])
    assert row['pc_ratio'] == .25
    other_basis = surface_day('SPY', '2022-03-07', options, 210.)
    assert np.isnan(other_basis['atm_iv_near'])
