from copy import deepcopy

import pandas as pd
import pytest

from nn_meta.v7.share_class_history import canonical_candidates, review_mapping
from nn_meta.v7.security_history import security_history
from nn_meta.v7.storage import identity
from tests.test_v7_security_history import fixture as history_fixture


def fixture():
    anchor = dict(ticker='ABC', composite_figi='security', share_class_figi='share',
        primary_exchange='XNYS', type='CS', market='stocks', locale='us',
        currency_name='usd', cik='issuer', active=True)
    current = dict(anchor, composite_figi='provider-conflict')
    review = dict(symbol='ABC', security_id='security', date='2022-03-17',
        anchor_date='2022-03-16', share_class_figi='share',
        original_composite_figi='provider-conflict', anchor_record_sha256=identity(anchor),
        record_sha256=identity(current))
    return review, anchor, current


def test_exact_share_class_resolves_history_without_mutating_original_provider_identity():
    review, anchor, current = fixture()
    mapping = review_mapping(review, anchor, current, scoped_ids={'security'})
    stock, clock = history_fixture()
    stock['stock_ticker'] = 'ABC'
    stock.loc[2, 'listed_security_id'] = 'provider-conflict'
    original = stock.copy(deep=True)
    resolved = canonical_candidates(stock, [mapping])
    pd.testing.assert_frame_equal(stock, original)
    assert mapping['provider_composite_figi'] == 'provider-conflict'
    assert mapping['share_class_figi'] == 'share'
    before = security_history(stock[stock.listed_security_id.eq('security')], clock, security_id='security')
    after = security_history(resolved, clock, security_id='security')
    pd.testing.assert_frame_equal(before.iloc[:2], after.iloc[:2])
    assert after.identity_span.nunique() == 1
    assert after.raw_close.tolist() == [100., 101., 102., 103.]


@pytest.mark.parametrize('field,value', [('share_class_figi', 'other-class'), ('share_class_figi', None),
    ('ticker', 'OTHER'), ('primary_exchange', 'XNAS'), ('type', 'ADR'), ('market', 'otc'),
    ('locale', 'ca'), ('currency_name', 'cad'), ('cik', 'other-issuer'), ('active', False)])
def test_names_or_prices_cannot_override_different_or_missing_identifiers(field, value):
    review, anchor, current = fixture()
    current[field] = value
    review['record_sha256'] = identity(current)
    with pytest.raises(ValueError): review_mapping(review, anchor, current, scoped_ids={'security'})


@pytest.mark.parametrize('change', ['future_anchor', 'same_day_anchor', 'wrong_anchor', 'corrupt_record',
    'competing_study_id', 'wrong_original', 'outside_scope'])
def test_scope_clock_and_evidence_conflicts_fail(change):
    review, anchor, current = fixture(); scoped = {'security'}
    if change == 'future_anchor': review['anchor_date'] = '2022-03-18'
    if change == 'same_day_anchor': review['anchor_date'] = review['date']
    if change == 'wrong_anchor':
        anchor['composite_figi'] = 'different'; review['anchor_record_sha256'] = identity(anchor)
    if change == 'corrupt_record': current['name'] = 'changed'
    if change == 'competing_study_id': scoped.add('provider-conflict')
    if change == 'wrong_original': review['original_composite_figi'] = 'wrong'
    if change == 'outside_scope': scoped = {'other'}
    with pytest.raises(ValueError): review_mapping(review, anchor, current, scoped_ids=scoped)


def test_captured_share_class_can_resolve_missing_composite_without_inventing_original_id():
    review, anchor, current = fixture(); current.pop('composite_figi')
    review.update(original_composite_figi=None, record_sha256=identity(current))
    mapping = review_mapping(review, anchor, current, scoped_ids={'security'})
    assert mapping['provider_composite_figi'] is None
    panel = pd.DataFrame([dict(stock_ticker='ABC', source_date='2022-03-17',
        listed_security_id=pd.NA, identity_status='missing_composite_figi')])
    assert canonical_candidates(panel, [mapping]).listed_security_id.iloc[0] == 'security'


@pytest.mark.parametrize('change', ['absent', 'ambiguous', 'changed_id', 'duplicate_review', 'duplicate_panel'])
def test_adapter_cannot_create_rows_or_mask_collision(change):
    review, anchor, current = fixture()
    mapping = review_mapping(review, anchor, current, scoped_ids={'security'})
    panel = pd.DataFrame([dict(stock_ticker='ABC', source_date='2022-03-17',
        listed_security_id='provider-conflict', identity_status='dated_identity')])
    mappings = [mapping]
    if change == 'absent': panel = panel.iloc[:0]
    if change == 'ambiguous': panel.loc[0, 'identity_status'] = 'ambiguous_listed_symbol'
    if change == 'changed_id': panel.loc[0, 'listed_security_id'] = 'unexpected'
    if change == 'duplicate_review': mappings *= 2
    if change == 'duplicate_panel': panel = pd.concat([panel, panel])
    with pytest.raises(ValueError): canonical_candidates(panel, mappings)
