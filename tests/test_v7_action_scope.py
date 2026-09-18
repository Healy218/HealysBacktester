from copy import deepcopy

import pytest

from nn_meta.v7.action_scope import other_instrument_treatments
from nn_meta.v7.storage import identity
from tests.test_v7_ordinary_actions import fixture


def inputs():
    rows = fixture()[0]
    listing = dict(ticker='ABC', composite_figi='other', share_class_figi='other-class',
        active=True, market='stocks', locale='us', primary_exchange='XNYS')
    review = dict(symbol='ABC', effective_date='2024-09-13', treatment='reviewed_unrelated_instrument',
        rationale='Reviewed unrelated issuer reused this ticker.', relationship='unrelated_ticker_reuse',
        other_security_id='other', other_share_class_figi='other-class', successor_or_entitlement_inference=False,
        listed_record_sha256=identity(listing),
        replaces=[{k:r[k] for k in ('provider', 'kind', 'action_id', 'record_sha256')} for r in rows])
    return rows, [review], {('ABC', '2024-09-13'): listing}


def test_unrelated_records_are_retained_whole_without_creating_chart_or_held_actions():
    rows, reviews, listings = inputs()
    results, pending = other_instrument_treatments(rows, reviews, listings, scoped_ids={'security'}, selected_keys=set())
    assert len(results) == 1 and not pending
    assert results[0]['replaces'] == reviews[0]['replaces']
    assert results[0]['review_identity'] == identity(reviews[0])
    assert 'action' not in results[0]


@pytest.mark.parametrize('change', ['in_scope', 'selected', 'missing_listing', 'missing_share',
    'changed_record', 'partial_group', 'duplicate_review', 'wrong_action_hash', 'successor'])
def test_missing_conflicting_or_successor_evidence_cannot_dismiss_original_records(change):
    rows, reviews, listings = deepcopy(inputs()); scoped, selected = {'security'}, set()
    if change == 'in_scope': scoped.add('other')
    if change == 'selected': selected.add(('ABC', '2024-09-13'))
    if change == 'missing_listing': listings = {}
    if change == 'missing_share':
        listings['ABC', '2024-09-13']['share_class_figi'] = None
        reviews[0]['listed_record_sha256'] = identity(listings['ABC', '2024-09-13'])
    if change == 'changed_record': listings['ABC', '2024-09-13']['name'] = 'changed'
    if change == 'partial_group': reviews[0]['replaces'].pop()
    if change == 'duplicate_review': reviews *= 2
    if change == 'wrong_action_hash': reviews[0]['replaces'][0]['record_sha256'] = 'wrong'
    if change == 'successor': reviews[0]['successor_or_entitlement_inference'] = True
    with pytest.raises(ValueError):
        other_instrument_treatments(rows, reviews, listings, scoped_ids=scoped, selected_keys=selected)
