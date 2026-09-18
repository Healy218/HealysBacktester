from copy import deepcopy
import pytest
from nn_meta.v7.dividend_review_extensions import validate_precision, acquirer_cash_view
from nn_meta.v7.storage import identity


def precision_fixture():
    e = {'capture': 'retained-primary', 'payload_sha256': 'abc'}
    raw = {'currency': 'USD'}
    row = dict(provider='massive', kind='dividends', action_id='one', record=raw,
               record_sha256=identity(raw), category='cash', subject_symbol='ETF', term='0.23289563')
    ref = {k: row[k] for k in ('provider', 'kind', 'action_id', 'record_sha256')}
    review = dict(symbol='ETF', amount_basis='primary_corroborated_provider_precision',
                  cash_per_share='0.23289563', payments=[{}], replaces=[ref], evidence=[e],
                  precision_review=dict(published_amount='.233', published_quantum='.001',
                  rounding='nearest', primary_evidence_identity=identity(e), rationale='reviewed display'))
    return row, review


def test_precision_preserves_original_digits():
    row, review = precision_fixture()
    before = deepcopy(row)
    assert validate_precision(review, [row])
    assert row == before


@pytest.mark.parametrize('change', ['currency', 'published', 'coarse', 'unbound', 'invented_digits'])
def test_precision_rejects_real_conflicts(change):
    row, review = precision_fixture()
    if change == 'currency':
        row['record']['currency'] = 'CAD'; row['record_sha256'] = identity(row['record'])
        review['replaces'][0]['record_sha256'] = row['record_sha256']
    elif change == 'published': review['precision_review']['published_amount'] = '.234'
    elif change == 'coarse': review['precision_review']['published_quantum'] = '.01'
    elif change == 'unbound': review['precision_review']['primary_evidence_identity'] = 'other'
    else: review['cash_per_share'] = '.232895631'
    with pytest.raises(ValueError): validate_precision(review, [row])


def merger_fixture():
    e = {'capture': 'issuer-merger'}
    raw = dict(acquirer_symbol='BUY', acquiree_symbol='SELL', acquirer_cusip='111111111', acquiree_cusip='222222222')
    row = dict(provider='alpaca', kind='cash_mergers', action_id='merger', record=raw,
               record_sha256=identity(raw), category='complex', effective_date='2025-09-04', scoped_symbols=['BUY'])
    ref = {k: row[k] for k in ('provider', 'kind', 'action_id', 'record_sha256')}
    j = dict(record=ref, acquiree_symbol='SELL', acquirer_cusip='111111111', acquiree_cusip='222222222',
             existing_acquirer_shares_unchanged=True, consume_merger_record=False,
             primary_evidence_identity=identity(e), rationale='Acquiree alone receives consideration')
    return row, dict(symbol='BUY', ex_date='2025-09-04', evidence=[e], acquirer_role_reviews=[j])


def test_acquirer_view_does_not_consume_original():
    row, review = merger_fixture(); originals = [row]; before = deepcopy(originals)
    assert acquirer_cash_view(originals, [review]) == []
    assert originals == before


@pytest.mark.parametrize('change', ['acquiree_scoped', 'consume', 'cusip', 'mutated', 'different_day'])
def test_acquirer_review_cannot_hide_entitled_or_other_records(change):
    row, review = merger_fixture()
    if change == 'acquiree_scoped': row['scoped_symbols'].append('SELL')
    elif change == 'consume': review['acquirer_role_reviews'][0]['consume_merger_record'] = True
    elif change == 'cusip': review['acquirer_role_reviews'][0]['acquirer_cusip'] = 'wrong'
    elif change == 'mutated': row['record']['acquirer_symbol'] = 'SELL'
    else: review['ex_date'] = '2025-09-05'
    with pytest.raises(ValueError): acquirer_cash_view([row], [review])
