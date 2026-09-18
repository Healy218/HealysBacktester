from copy import deepcopy

import pytest

from nn_meta.v7.stock_cash_dates import compile_date_reviewed_cash
from nn_meta.v7.stock_cash import validate_cash_event
from nn_meta.v7.storage import identity
from tests.test_v7_stock_cash_extension import inputs


def case():
    args = list(inputs())
    source = args[0][0]
    review = dict(schema='v7-primary-cash-date-review-v1',
        compiled_event_id=source['action']['event_id'], compiled_source_identity=identity(source),
        symbol='ABC', security_id='sid', cash_per_share='.15', ex_date='2024-06-12',
        record_date='2024-06-12', pay_date='2024-06-12', conclusion='ordinary_cash_dates_resolved',
        publication_time_used_for_chart=False, evidence_identity='retained-primary-source',
        rationale='Exact primary date correction only.', replaces=deepcopy(source['replaces']))
    return args, review


def test_date_correction_preserves_chart_source_and_releases_only_after_pay():
    args, review = case()
    source_before = deepcopy(args[0])
    events = compile_date_reviewed_cash(*args, [review])
    assert args[0] == source_before
    e = events[0]
    validate_cash_event(e, args[3])
    assert e['source_identity'] == identity(source_before[0])
    assert e['date_basis'] == 'retained_primary_date_review'
    assert e['release_ns'] == args[3].bounds('2024-06-13')[0].tz_localize('UTC').value
    assert e['cash_per_share'] == '0.15' and e['withholding_fraction'] == 0
    assert not e['broker_posting_verified']
    args[2] = events
    assert compile_date_reviewed_cash(*args, []) == events


@pytest.mark.parametrize('change', ['unapproved', 'source', 'amount', 'security', 'record',
    'publication', 'partial', 'original', 'duebill', 'duplicate', 'horizon', 'evidence'])
def test_rejects_unsupported_cash_date_claims(change):
    args, review = case()
    if change == 'unapproved': args[4]['status'] = 'proposed'
    if change == 'source': review['compiled_source_identity'] = 'different'
    if change == 'amount': review['cash_per_share'] = '.3'
    if change == 'security': review['security_id'] = 'different'
    if change == 'record': review['record_date'] = '2024-06-11'
    if change == 'publication': review['publication_time_used_for_chart'] = True
    if change == 'partial': review['replaces'].pop()
    if change == 'original': args[1][0]['record']['cash_amount'] = 1
    if change == 'duebill': args[1][0]['record']['due_bill_on_date'] = '2024-06-12'
    if change == 'horizon': review['pay_date'] = '2024-06-13'
    if change == 'evidence': review['evidence_identity'] = ''
    reviews = [review, deepcopy(review)] if change == 'duplicate' else [review]
    with pytest.raises(ValueError): compile_date_reviewed_cash(*args, reviews)
