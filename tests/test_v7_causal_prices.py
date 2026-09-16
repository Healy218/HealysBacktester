import numpy as np
import pandas as pd
import pytest

from nn_meta.v7.causal_prices import CausalPriceHistory, PriceAction, cash_distribution_action, split_action


def raw():
    index = pd.date_range('2022-03-07 14:30Z', periods=5, freq='D')
    prices = np.array([100., 102., 51., 50., 52.])
    return pd.DataFrame({'Open': prices, 'High': prices, 'Low': prices, 'Close': prices,
                         'Volume': 100., 'available_at': index + pd.Timedelta(minutes=1)}, index=index)


def split():
    return split_action(old_shares=1, new_shares=2, event_id='split',
                        effective_at=pd.Timestamp('2022-03-09 14:30Z'),
                        available_at=pd.Timestamp('2022-03-01 00:00Z'), source_identity='source-sha')


def test_future_action_and_future_raw_data_cannot_change_prefix():
    frame = raw()
    before = pd.Timestamp('2022-03-08 15:00Z')
    plain = CausalPriceHistory(frame, [], security_id='security').view(before)
    full = CausalPriceHistory(frame, [split()], security_id='security').view(before)
    pd.testing.assert_frame_equal(plain, full)
    changed = frame.copy()
    changed.loc[changed.index > before, ['Open', 'High', 'Low', 'Close']] *= 100
    later_action = split_action(old_shares=20, new_shares=1, event_id='later',
                               effective_at=pd.Timestamp('2022-03-11 14:30Z'),
                               available_at=pd.Timestamp('2022-03-10 00:00Z'), source_identity='later-source')
    other = CausalPriceHistory(changed, [split(), later_action], security_id='security').view(before)
    pd.testing.assert_frame_equal(full, other)


def test_split_asof_units_and_cross_epoch_proposal_stop_basis():
    history = CausalPriceHistory(raw(), [split()], security_id='security')
    after = history.view(pd.Timestamp('2022-03-09 14:31Z'))
    assert after.Close.tolist() == [50., 51., 51.]
    assert after.Volume.tolist() == [200., 200., 100.]
    forward = history.proposal_basis()
    assert forward.Close.tolist() == [100., 102., 102., 100., 104.]
    assert forward.Volume.tolist() == [100., 100., 50., 50., 50.]
    pd.testing.assert_frame_equal(history.view(pd.Timestamp('2022-03-09 14:30Z')).iloc[-1:],
                                  after.iloc[1:2])
    assert len(history.epochs(start=raw().index[0], end=raw().available_at.iloc[-1])) == 2


def test_cash_chart_factor_requires_past_close_and_does_not_adjust_volume():
    action = cash_distribution_action(cash_per_share=2., prior_raw_close=102.,
        prior_close_at=pd.Timestamp('2022-03-08 21:00Z'), event_id='div',
        effective_at=pd.Timestamp('2022-03-09 14:30Z'),
        available_at=pd.Timestamp('2022-03-01 00:00Z'), source_identity='div-source')
    assert action.available_at == pd.Timestamp('2022-03-08 21:00Z')
    view = CausalPriceHistory(raw(), [action], security_id='security').view(pd.Timestamp('2022-03-09 15:00Z'))
    assert view.Close.iloc[1] == pytest.approx(100.)
    assert view.Volume.tolist() == [100., 100., 100.]
    with pytest.raises(ValueError, match='prior raw close'):
        cash_distribution_action(cash_per_share=2., prior_raw_close=102.,
            prior_close_at=pd.Timestamp('2022-03-10 21:00Z'), event_id='div',
            effective_at=pd.Timestamp('2022-03-09 14:30Z'),
            available_at=pd.Timestamp('2022-03-01 00:00Z'), source_identity='div-source')


def test_reject_late_unknown_or_conflicting_action_inputs():
    with pytest.raises(ValueError, match='not available'):
        PriceAction('x', pd.Timestamp('2022-03-09 14:30Z'), pd.Timestamp('2022-03-10 00:00Z'), .5, 2., 'src')
    with pytest.raises(ValueError, match='Duplicate'):
        CausalPriceHistory(raw(), [split(), split()], security_id='security')
    other = PriceAction('different', split().effective_at, split().available_at, .9, 1., 'src')
    with pytest.raises(ValueError, match='Simultaneous'):
        CausalPriceHistory(raw(), [split(), other], security_id='security')
    with pytest.raises(ValueError, match='availability'):
        CausalPriceHistory(raw().drop(columns='available_at'), [], security_id='security')
