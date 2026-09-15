import numpy as np
import pandas as pd
import pytest
from nn_meta.v7.adjustments import daily_scale_bounds


def test_large_reverse_split_rounding_is_distinct_from_inconsistent_price_basis():
    raw = pd.DataFrame({'timestamp': pd.date_range('2022-03-07T15:00Z', periods=2, freq='min'),
                        'Open': [.2608, .28], 'High': [.2624, .30],
                        'Low': [.2607, .27], 'Close': [.2607, .29]})
    adj = raw.copy()
    adj.iloc[:, 1:] = np.round(raw.iloc[:, 1:] * 120, 2)
    result = daily_scale_bounds(raw, adj, adjusted_half_unit=.005000001)
    assert result.rounding_compatible.all()
    assert result.factor_lower.iloc[0] <= 120 <= result.factor_upper.iloc[0]
    adj.loc[1, 'Close'] += .10
    assert not daily_scale_bounds(raw, adj, adjusted_half_unit=.005000001).rounding_compatible.any()


def test_changed_timestamps_do_not_pass_a_price_only_comparison():
    raw = pd.DataFrame({'timestamp': pd.to_datetime(['2022-03-07T15:00Z']),
                        'Open': [1.], 'High': [1.], 'Low': [1.], 'Close': [1.]})
    adj = raw.copy()
    adj.timestamp += pd.Timedelta(minutes=1)
    with pytest.raises(ValueError, match='timestamps'):
        daily_scale_bounds(raw, adj, adjusted_half_unit=.005)
