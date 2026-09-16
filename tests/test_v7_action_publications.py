import pytest
from nn_meta.v7.action_publications import cash_publication


def fixture(headline='Apple Raises Qtr. Dividend From $0.22 To $0.23/Share'):
    action = dict(id='a', ticker='AAPL', cash_amount=.23, currency='USD',
                  declaration_date='2022-04-28', ex_dividend_date='2022-05-06')
    news = dict(id=1, headline=headline, symbols=['AAPL'], url='https://example.org/original',
                created_at='2022-04-28T20:31:12Z', updated_at='2022-04-28T20:31:12Z')
    return action, news, '2022-05-06T09:30:00-04:00'


@pytest.mark.parametrize('headline', ['Apple Raises Qtr. Dividend From $0.22 To $0.23/Share',
    'Apple Declares Quarterly Dividend Of $0.23 Per Share',
    'Apple Declares $0.23/Share Quarterly Dividend'])
def test_original_amount_is_matched_without_inventing_other_action_evidence(headline):
    result = cash_publication(*fixture(headline))
    assert result['cash_amount'] == '0.23' and result['amount_publication_verified']
    assert not any(result[k] for k in ('effective_date_verified', 'security_identity_verified',
                                     'combined_action_units_verified', 'research_ready'))


@pytest.mark.parametrize('change', [dict(updated_at='2022-05-07T00:00:00Z'),
    dict(created_at='2022-04-27T20:31:12Z'), dict(symbols=['AAPL', 'MSFT']),
    dict(headline='Apple Declares $0.23 Dividend'),
    dict(headline='Apple Declares C$0.23/Share Quarterly Dividend')])
def test_late_updates_ambiguous_issuers_currencies_and_units_do_not_admit(change):
    action, news, effective = fixture()
    assert cash_publication(action, {**news, **change}, effective) is None


def test_old_amount_in_raise_headline_is_not_mistaken_for_new_payment():
    action, news, effective = fixture()
    assert cash_publication({**action, 'cash_amount': .22}, news, effective) is None
