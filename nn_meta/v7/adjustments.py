"""Test a declared rounding explanation without declaring price-vintage safety."""
import numpy as np
import pandas as pd


def daily_scale_bounds(raw, adjusted, *, adjusted_half_unit):
    """Intersect all OHLC constraints for one common positive factor per date.

    For raw price p and adjusted price a, rounding tolerance e implies
    (a-e)/p <= factor <= (a+e)/p. A nonempty intersection is only consistency
    with that explanation; it is not proof of the factor or its availability.
    """
    if not np.isfinite(adjusted_half_unit) or adjusted_half_unit <= 0:
        raise ValueError('Explicit positive adjusted-price rounding tolerance required')
    if not raw.timestamp.equals(adjusted.timestamp):
        raise ValueError('Raw and adjusted timestamps differ')
    columns = ['Open', 'High', 'Low', 'Close']
    r, a = raw[columns].to_numpy(), adjusted[columns].to_numpy()
    if not np.isfinite(r).all() or not np.isfinite(a).all() or (r <= 0).any() or (a <= 0).any():
        raise ValueError('Positive finite OHLC observations required')
    if raw.empty:
        return pd.DataFrame(columns=['date', 'factor_lower', 'factor_upper', 'observed_minutes',
                                     'rounding_compatible', 'adjusted_half_unit'])
    lower = np.maximum(0., ((a - adjusted_half_unit) / r).max(axis=1))
    upper = ((a + adjusted_half_unit) / r).min(axis=1)
    days = raw.timestamp.dt.tz_convert('America/New_York').dt.strftime('%Y-%m-%d')
    result = pd.DataFrame({'date': days, 'factor_lower': lower, 'factor_upper': upper})
    result = result.groupby('date').agg(factor_lower=('factor_lower', 'max'),
                                      factor_upper=('factor_upper', 'min'), observed_minutes=('date', 'size'))
    result['rounding_compatible'] = result.factor_lower <= result.factor_upper + 1e-10
    result['adjusted_half_unit'] = adjusted_half_unit
    return result.reset_index()
