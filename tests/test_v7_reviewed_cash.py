from copy import deepcopy

import pandas as pd
import pytest

from nn_meta.session_calendar import SessionCalendar
from nn_meta.v7.action_inventory import candidate
from nn_meta.v7.causal_daily import returns
from nn_meta.v7.ordinary_actions import price_action
from nn_meta.v7.reviewed_cash import compile_reviewed_cash


def fixture():
    cal = SessionCalendar(dict(coverage_start='2024-06-11', coverage_end='2024-06-13',
        sessions=[dict(date=d, open='09:30', close='16:00') for d in
                  ['2024-06-11', '2024-06-12', '2024-06-13']]))
    originals = [('massive', 'dividends', dict(id='base', ticker='ABC', cash_amount=.075,
        currency='USD', ex_dividend_date='2024-06-12')),
        ('massive', 'dividends', dict(id='variable', ticker='ABC', cash_amount=.075,
        currency='USD', ex_dividend_date='2024-06-12')),
        ('alpaca', 'cash_dividends', dict(id='a', symbol='ABC', rate=.075, ex_date='2024-06-12'))]
    rows = [candidate(p, k, r, scoped_symbols={'ABC'}, start=cal.start, end=cal.end,
        source={'receipt': 'original'}) for p, k, r in originals]
    history = pd.DataFrame([dict(stock_ticker='ABC', source_date=d, security_id='sid',
        identity_span='span', observed_minutes=390, raw_close=c,
        available_ns=cal.bounds(d)[1].tz_localize('UTC').value) for d, c in
        [('2024-06-11', 100.), ('2024-06-12', 99.85)]])
    review = dict(schema='v7-primary-common-share-cash-review-v1', event_id='reviewed',
        symbol='ABC', effective_date='2024-06-12', security_id='sid', currency='USD',
        cash_units='per_common_share', cash_amount='0.15', record_date='2024-06-12',
        pay_date='2024-06-13', other_security_entitlement=False,
        components=[dict(name='base', cash_amount='.075'), dict(name='variable', cash_amount='.075')],
        rationale='Primary issuer total replaces the incomplete provider rate.',
        evidence_identity='primary-source', publication_available_at='2024-06-01T04:00Z',
        replaces=[{k: r[k] for k in ('provider', 'kind', 'action_id', 'record_sha256')} for r in rows])
    return rows, [review], history, cal


def test_primary_whole_event_correction_reaches_real_return_consumer_once():
    rows, reviews, history, calendar = fixture()
    original = deepcopy(rows)
    events, pending = compile_reviewed_cash(rows, reviews, history, calendar)
    assert len(events) == 1 and not pending and rows == original
    event = events[0]
    assert event['cash_amount'] == '0.15' and len(event['replaces']) == 3
    assert event['reviewed_pay_date'] == '2024-06-13'
    result = returns(history, [price_action(event)], calendar, security_id='sid',
        start=calendar.start, end='2024-06-12', action_evidence_identity='primary')
    assert result.simple_return.iloc[-1] == pytest.approx(0)


@pytest.mark.parametrize('change', ['normalized', 'original', 'partial', 'currency', 'units',
    'components', 'duplicate_component', 'late', 'naive', 'record', 'pay', 'identity',
    'span', 'missing_prior', 'other_security', 'duplicate', 'complex'])
def test_refuses_unsupported_or_incomplete_cash_corrections(change):
    rows, reviews, history, calendar = fixture()
    review = reviews[0]
    if change == 'normalized': rows[0]['term'] = '1'
    if change == 'original': rows[0]['record']['cash_amount'] = 1
    if change == 'partial': review['replaces'].pop()
    if change == 'currency': review['currency'] = 'CAD'
    if change == 'units': review['cash_units'] = 'per_ordinary_share_for_ADR'
    if change == 'components': review['cash_amount'] = '.075'
    if change == 'duplicate_component': review['components'][1]['name'] = 'base'
    if change == 'late': review['publication_available_at'] = '2024-06-12T14:00Z'
    if change == 'naive': review['publication_available_at'] = '2024-06-01'
    if change == 'record': review['record_date'] = '2024-06-11'
    if change == 'pay': review['pay_date'] = '2024-06-11'
    if change == 'identity': review['security_id'] = 'other'
    if change == 'span': history.loc[0, 'identity_span'] = 'old'
    if change == 'missing_prior': history = history.iloc[1:]
    if change == 'other_security': review['other_security_entitlement'] = True
    if change == 'duplicate': reviews.append(deepcopy(review))
    if change == 'complex':
        rows.append(candidate('alpaca', 'spin_offs', dict(id='spin', source_symbol='ABC',
            effective_date='2024-06-12'), scoped_symbols={'ABC'}, start=calendar.start,
            end=calendar.end, source={'receipt': 'original'}))
    with pytest.raises(ValueError):
        compile_reviewed_cash(rows, reviews, history, calendar)
