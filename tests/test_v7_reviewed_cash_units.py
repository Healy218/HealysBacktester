from copy import deepcopy
import json
from pathlib import Path

import pandas as pd
import pytest

from nn_meta.session_calendar import SessionCalendar
from nn_meta.v7.action_inventory import candidate
from nn_meta.v7.ordinary_actions import price_action
from nn_meta.v7.reviewed_cash_units import compile_unit_reviewed_cash
from nn_meta.v7.storage import identity


def fixture():
    cal = SessionCalendar(dict(coverage_start='2024-06-11', coverage_end='2024-06-13',
        sessions=[dict(date=d, open='09:30', close='16:00') for d in
                  ['2024-06-11', '2024-06-12', '2024-06-13']]))
    originals = [('massive', 'dividends', dict(id='m', ticker='ABC', cash_amount=.25,
        currency='USD', ex_dividend_date='2024-06-12')),
        ('alpaca', 'cash_dividends', dict(id='a', symbol='ABC', rate=.25,
            foreign=True, ex_date='2024-06-12'))]
    rows = [candidate(p, k, r, scoped_symbols={'ABC'}, start=cal.start, end=cal.end,
        source={'receipt': 'original'}) for p, k, r in originals]
    h = pd.DataFrame([dict(stock_ticker='ABC', source_date=d, security_id='sid',
        identity_span='same', raw_close=100., observed_minutes=390,
        available_ns=cal.bounds(d)[1].tz_localize('UTC').value,
        session_open_ns=cal.bounds(d)[0].tz_localize('UTC').value) for d in cal.sessions])
    w = dict(schema='v7-primary-common-share-cash-review-v1', event_id='witness', symbol='ABC',
        security_id='sid', effective_date='2024-06-11', currency='USD', cash_units='per_common_share')
    r = dict(schema='v7-finite-matching-cash-unit-review-v1', symbol='ABC', security_id='sid',
        effective_date='2024-06-12', cash_amount='.25', unit_witness_event_id='witness',
        unit_witness_review_identity=identity(w),
        replaces=[{k: row[k] for k in ('provider', 'kind', 'action_id', 'record_sha256')} for row in rows])
    policy = json.loads((Path(__file__).resolve().parents[1]/
        'docs/specs/V7_ORDINARY_ACTION_ADMISSION_20260917.json').read_text())
    return rows, [r], {'witness': w}, h, cal, policy


def test_resolves_units_without_claiming_amount_publication_or_changing_originals():
    args = fixture(); original = deepcopy(args[0])
    events, pending = compile_unit_reviewed_cash(*args)
    assert len(events) == 1 and not pending and args[0] == original
    action = price_action(events[0])
    assert action.price_factor == .9975 and action.volume_factor == 1
    assert action.available_at == action.effective_at and not action.publication_verified
    assert events[0]['held_position_treatment'] == 'requires_separate_authorized_entitlement'
    assert compile_unit_reviewed_cash(args[0], [], *args[2:]) == ([], original)


@pytest.mark.parametrize('change', ['different_amount', 'currency', 'adr', 'changed_witness',
    'later_witness', 'identity', 'span', 'no_close', 'clock', 'duplicate', 'reference', 'combined'])
def test_rejects_unresolved_currency_gross_net_and_identity_cases(change):
    rows, reviews, witnesses, h, cal, policy = fixture()
    r, w = reviews[0], witnesses['witness']
    if change in ('different_amount', 'currency'):
        source = deepcopy(rows[0]['record'])
        source['cash_amount' if change == 'different_amount' else 'currency'] = .2 if change == 'different_amount' else 'CAD'
        rows[0] = candidate('massive', 'dividends', source, scoped_symbols={'ABC'},
            start=cal.start, end=cal.end, source=rows[0]['source'])
        r['replaces'][0]['record_sha256'] = rows[0]['record_sha256']
    if change == 'adr': w['cash_units'] = 'per_ordinary_share_for_ADR'; r['unit_witness_review_identity'] = identity(w)
    if change == 'changed_witness': w['currency'] = 'CAD'
    if change == 'later_witness': w['effective_date'] = '2024-06-13'; r['unit_witness_review_identity'] = identity(w)
    if change == 'identity': r['security_id'] = 'other'
    if change == 'span': h.loc[0, 'identity_span'] = 'old'
    if change == 'no_close': h.loc[0, 'observed_minutes'] = 0
    if change == 'clock': h.loc[1, 'session_open_ns'] += 1
    if change == 'duplicate': reviews.append(deepcopy(r))
    if change == 'reference': r['replaces'][0]['record_sha256'] = 'changed'
    if change == 'combined': rows.append(deepcopy(rows[0]))
    with pytest.raises(ValueError):
        compile_unit_reviewed_cash(rows, reviews, witnesses, h, cal, policy)
