import pandas as pd
import pytest

from nn_meta.v7.universe import membership


def fixture():
    days = ['2022-01-03', '2022-01-04', '2022-01-05', '2022-02-01', '2022-02-02', '2022-02-03']
    calendar = {'sessions': [{'date': d} for d in days + ['2022-03-01']]}
    daily = pd.DataFrame({'date': days, 'root': 'X', 'opt_dollar_vol': 100.})
    masters = {'2022-01-05': {'X': {'ticker': 'X', 'composite_figi': 'old-security'}},
               '2022-02-03': {'X': {'ticker': 'X', 'composite_figi': 'new-security'},
                              'OLD': {'ticker': 'OLD', 'composite_figi': 'old-security'}}}
    return daily, masters, calendar


def test_reused_ticker_cannot_inherit_another_security_liquidity():
    daily, masters, calendar = fixture()
    identities = {('X', '2022-02-01'): 'old-security', ('X', '2022-02-02'): 'old-security',
                  ('X', '2022-02-03'): 'new-security'}
    rows, report = membership(daily, masters, calendar, through='2022-02', window=3,
                              min_active=2, enter=1, exit=1, identity_days=identities)
    feb = rows[rows.month == '2022-02']
    assert feb.security_id.tolist() == ['old-security']
    assert feb.ticker.tolist() == ['OLD']
    assert feb.available_at.tolist() == ['2022-03-01']
    assert report['identity_boundaries_verified']


def test_missing_transition_evidence_blocks_identity_admission():
    daily, masters, calendar = fixture()
    rows, report = membership(daily, masters, calendar, through='2022-02', window=3,
                              min_active=2, enter=1, exit=1)
    assert not report['identity_boundaries_verified']
    assert len(report['unresolved_transitions'][0]['uncaptured_days']) == 3
    assert 'new-security' not in rows.security_id.tolist()


def test_deleted_sessions_consume_lookback_without_becoming_zero_or_older_data():
    days = ['2022-01-03', '2022-01-04', '2022-01-05', '2022-02-01', '2022-02-02', '2022-02-03']
    calendar = {'sessions': [{'date': d} for d in days + ['2022-03-01']]}
    daily = pd.DataFrame({'date': days, 'root': 'X', 'opt_dollar_vol': [1., 2., 999., 100., 200., 300.]})
    masters = {d: {'X': {'ticker': 'X', 'composite_figi': 'id'}} for d in (days[2], days[-1])}
    kept = daily[~daily.date.eq('2022-02-02')]
    rows, report = membership(kept, masters, calendar, window=3, min_active=2,
                              excluded_sessions=['2022-02-02'])
    assert rows.iloc[-1].score == 200.  # median of 100, 300, not 0 or 999
    assert rows.iloc[-1].available_at == '2022-03-01'
    assert report['lookback_windows'][-1]['retained_sessions'] == 2
    strict, _ = membership(kept, masters, calendar, window=3, min_active=3,
                            excluded_sessions=['2022-02-02'])
    assert '2022-02' not in strict.month.tolist()
    with pytest.raises(ValueError, match='missing captured'):
        membership(kept, masters, calendar, window=3, min_active=2)
    with pytest.raises(ValueError, match='absent from inputs'):
        membership(daily, masters, calendar, window=3, min_active=2, excluded_sessions=['2022-02-02'])
    with pytest.raises(ValueError, match='remain in calendar'):
        membership(kept, masters, calendar, window=3, min_active=2, excluded_sessions=['2022-02-06'])
