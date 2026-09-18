from copy import deepcopy

import pytest

from nn_meta.v7.dividend_dates import compile_remaining_dates
from nn_meta.v7.storage import identity
from tests.test_v7_stock_cash_dates import case


def nominal():
    args, review = case()
    review.update(conclusion='cash_distribution_dates_resolved', distribution_kind='special_cash',
        option_notice_evidence_identity='retained-occ-notice', option_treatment_resolved=False,
        pay_date_qualifier='on_or_after', payment_model='nominal_date_broker_posting_unverified')
    return args, review


def test_qualified_special_cash_retains_terms_without_claiming_option_treatment():
    args, r = nominal()
    e = compile_remaining_dates(*args, [r])[0]
    assert e['distribution_kind'] == 'special_cash'
    assert e['pay_date_qualifier'] == 'on_or_after'
    assert not e['option_treatment_resolved'] and not e['broker_posting_verified']
    assert e['date_review_identity'] == identity(r)
    assert e['event_id'] == 'stock-cash:' + identity({k:v for k,v in e.items() if k!='event_id'})
    args[2] = [e]
    assert compile_remaining_dates(*args, []) == [e]
    with pytest.raises(ValueError): compile_remaining_dates(*args, [r])


@pytest.mark.parametrize('field,value', [('option_notice_evidence_identity',''),
    ('option_treatment_resolved',True), ('pay_date_qualifier','actual_posting'),
    ('payment_model','verified'), ('distribution_kind','stock_dividend')])
def test_rejects_unreviewed_semantics(field, value):
    args, r = nominal(); r[field] = value
    with pytest.raises(ValueError): compile_remaining_dates(*args, [r])
