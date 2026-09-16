import numpy as np
import pandas as pd
import pytest

from nn_meta.multitimeframe_catalog import registered_catalog
from nn_meta.v7.causal_features import CausalFeatures
from nn_meta.v7.causal_prices import split_action
from nn_meta.v7.rows import FEATURE_NAMES, TECHNICAL


def fixture(minutes=1, end='2022-03-16'):
    days = ['2022-03-14', '2022-03-15', '2022-03-16']
    index = pd.DatetimeIndex(np.concatenate([pd.date_range(d+'T13:30Z', periods=120, freq='min') for d in days]))
    close = 100+np.sin(np.arange(len(index))*.13)*3+np.arange(len(index))*.01
    after = index >= pd.Timestamp('2022-03-16T13:30Z')
    raw = pd.DataFrame(dict(Open=close, High=close+.1, Low=close-.1, Close=close, Volume=100.), index=index)
    raw.loc[after, ['Open', 'High', 'Low', 'Close']] /= 2
    raw.loc[after, 'Volume'] *= 2
    raw['available_at'] = index+pd.Timedelta(minutes=1)
    calendar = dict(timezone='America/New_York', coverage_start=days[0], coverage_end=days[-1],
                    sessions=[dict(date=d, open='09:30', close='16:00') for d in days])
    action = split_action(old_shares=1, new_shares=2, event_id='synthetic-split',
        effective_at=pd.Timestamp('2022-03-16T13:30Z'), available_at=pd.Timestamp('2022-03-01T00:00Z'),
        source_identity='synthetic-proof')
    chart = CausalFeatures(raw, [action], calendar, security_id='fixture', minutes=minutes,
                           start='2022-03-15', end=end)
    return chart, raw, action, calendar


@pytest.mark.parametrize('minutes', [1, 5, 15, 30])
def test_all_timeframes_keep_epoch_units_full_tv_schema_and_cold_start(minutes):
    chart, raw, action, _ = fixture(minutes)
    epochs = list(chart.epochs())
    assert len(epochs) == 2
    before, after = epochs
    assert len(before.observed) == len(after.observed) == 120//minutes
    assert tuple(before.tv) == tuple(after.tv) == FEATURE_NAMES
    assert tuple(before.technical) == tuple(after.technical) == TECHNICAL
    assert before.action_ids == () and after.action_ids == ('synthetic-split',)
    assert before.bars.index.min() == pd.Timestamp('2022-03-15T13:30Z')
    np.testing.assert_allclose(after.bars.loc[before.bars.index, 'Close'], before.bars.Close/2)
    np.testing.assert_allclose(after.bars.loc[before.bars.index, 'Volume'], before.bars.Volume*2)
    assert before.tv.attrs['minimum_tick'] == after.tv.attrs['minimum_tick'] == .01
    assert after.observed.min() >= action.effective_at
    basis = chart.proposal_basis()
    np.testing.assert_allclose(basis.loc[after.observed, 'Close'], after.bars.loc[after.observed, 'Close']*2)


def test_future_price_and_split_cannot_rewrite_prior_epoch_features_or_signals():
    full, raw, action, calendar = fixture()
    prefix, *_ = fixture(end='2022-03-15')
    changed = raw.copy()
    changed.loc[changed.index >= action.effective_at, ['Open', 'High', 'Low', 'Close']] *= 17
    other = CausalFeatures(changed, [action], calendar, security_id='fixture', minutes=1,
                           start='2022-03-15', end='2022-03-16')
    a, b, c = next(full.epochs()), next(prefix.epochs()), next(other.epochs())
    pd.testing.assert_frame_equal(a.tv, b.tv)
    pd.testing.assert_frame_equal(a.tv, c.tv)
    pd.testing.assert_frame_equal(a.technical, b.technical)
    variants = [next(v for v in registered_catalog(['fixture'])['records']
                if v['signal_minutes'] == 1 and v['strategy'] == family) for family in ('ma', 'tv_fibonacci')]
    one = list(full.signal_batches(variants, batch_columns=2))[0][1]
    two = list(prefix.signal_batches(variants, batch_columns=2))[0][1]
    for left, right in zip(one, two):
        pd.testing.assert_frame_equal(left.loc[right.index], right)


def test_causal_signal_channels_match_direct_epoch_calculation_for_every_family():
    from nn_meta.v7.signals import signal_batches
    chart, *_ = fixture()
    catalog = [v for v in registered_catalog(['fixture'])['records'] if v['signal_minutes'] == 1]
    variants = [next(v for v in catalog if v['strategy'] == strategy) for strategy in sorted({v['strategy'] for v in catalog})]
    batches = list(chart.signal_batches(variants, batch_columns=8))
    actual = [pd.concat([channels[i] for _, channels in batches], axis=1) for i in range(4)]
    for epoch in chart.epochs():
        for records, expected in signal_batches(epoch.bars, variants, sources=epoch.sources, batch_columns=8):
            ids = [v['variant_id'] for v in records]
            for left, right in zip(actual, expected):
                pd.testing.assert_frame_equal(left.loc[epoch.observed, ids], right.loc[epoch.observed, ids])


def test_unverified_mid_session_action_and_inexact_minute_clock_are_rejected():
    _, raw, action, calendar = fixture()
    from dataclasses import replace
    with pytest.raises(ValueError, match='effective open'):
        CausalFeatures(raw, [replace(action, effective_at=action.effective_at+pd.Timedelta(minutes=1))],
            calendar, security_id='fixture', minutes=1, start='2022-03-15', end='2022-03-16')
    raw.available_at += pd.Timedelta(seconds=1)
    with pytest.raises(ValueError, match='completed raw minute'):
        CausalFeatures(raw, [action], calendar, security_id='fixture', minutes=1,
                       start='2022-03-15', end='2022-03-16')


def test_later_bars_within_an_action_epoch_cannot_change_earlier_features():
    chart, raw, action, calendar = fixture()
    prefix = raw.loc[raw.index < pd.Timestamp('2022-03-15T14:20Z')]
    shorter = CausalFeatures(prefix, [action], calendar, security_id='fixture', minutes=1,
                            start='2022-03-15', end='2022-03-16')
    full, part = next(chart.epochs()), next(shorter.epochs())
    pd.testing.assert_frame_equal(full.tv.loc[part.observed], part.tv)
    pd.testing.assert_frame_equal(full.technical.loc[part.observed], part.technical)


def test_cross_action_proposal_stop_does_not_treat_a_split_as_a_price_loss():
    from nn_meta.v7.proposals import proposals_from_signals
    chart, raw, _, calendar = fixture()
    # Constant economic value, halved raw price at the split.
    raw.loc[:, ['Open', 'High', 'Low', 'Close']] = np.repeat(np.where(
        (raw.index >= pd.Timestamp('2022-03-16T13:30Z'))[:, None], 50., 100.), 4, axis=1)
    chart = CausalFeatures(raw, chart.history.actions, calendar, security_id='fixture', minutes=1,
                          start='2022-03-15', end='2022-03-16')
    basis = chart.proposal_basis()
    variant = next(v for v in registered_catalog(['fixture'])['records'] if v['strategy']=='ma' and v['signal_minutes']==1)
    channels = [pd.DataFrame(False, index=basis.index, columns=[variant['variant_id']]) for _ in range(4)]
    channels[0].iloc[10,0] = True
    channels[1].iloc[-1,0] = True
    output = list(proposals_from_signals('TEST', basis, [([variant], tuple(channels))],
                                       start='2022-03-15', end='2022-03-16'))[0][1]
    assert len(output) == 1 and output[0]['proposal_closed']
    assert output[0]['exit_decision_at'] == basis.index[-1]+pd.Timedelta(minutes=1)
