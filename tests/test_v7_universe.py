import pandas as pd

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
