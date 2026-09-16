import pytest

from nn_meta.v7.publication_body import cash_body_publication


def fixture():
    action = dict(id='event', ticker='ABC', cash_amount=.32, currency='USD',
        declaration_date='2022-03-10', ex_dividend_date='2022-04-07',
        record_date='2022-04-08', pay_date='2022-04-21')
    article = dict(id=1, headline='ABC Reports Quarterly Results', symbols=['ABC'],
        url='https://example.org/report', author='Reporter',
        created_at='2022-03-10T21:19:13Z', updated_at='2022-03-10T21:19:13Z',
        content='<p>The company declared a quarterly cash dividend of <b>$0.32</b> per common share, '
                'payable April 21, 2022, to shareholders of record on April 8, 2022.</p>')
    return action, article, '2022-04-07T09:30:00-04:00'


def test_body_adds_reported_dates_without_claiming_issuer_or_effective_evidence():
    result = cash_body_publication(*fixture())
    assert result['cash_amount'] == '0.32'
    assert result['reported_record_date'] == '2022-04-08'
    assert result['reported_pay_date'] == '2022-04-21'
    assert result['paragraph_numbers'] == [0]
    assert result['amount_publication_verified']
    assert not any(result[k] for k in ['original_issuer_document', 'effective_date_verified',
        'security_identity_verified', 'combined_action_units_verified', 'research_ready'])


@pytest.mark.parametrize('old,new', [
    ('quarterly cash', 'annual cash'), ('common share', 'Class A common share'),
    ('$0.32', 'C$0.32'), ('quarterly cash', 'special cash'),
    ('company declared', 'company has not declared'),
    ('April 21, 2022', 'April 21'), ('April 21, 2022', 'April 22, 2022'),
    ('April 8, 2022', 'April 8, 2021')])
def test_ambiguous_units_negation_and_missing_or_wrong_dates_are_rejected(old, new):
    action, article, effective = fixture()
    article['content'] = article['content'].replace(old, new)
    assert cash_body_publication(action, article, effective) is None


def test_no_amount_date_join_across_unrelated_html_blocks_or_hidden_scripts():
    action, article, effective = fixture()
    text = article['content']
    article['content'] = text.replace('payable', '</p><p>payable')
    assert cash_body_publication(action, article, effective) is None
    article['content'] = '<script>' + text + '</script>'
    assert cash_body_publication(action, article, effective) is None


@pytest.mark.parametrize('change', [dict(updated_at='2022-04-08T10:00Z'),
    dict(created_at='2022-03-09T21:19:13Z'), dict(symbols=['ABC', 'XYZ']),
    dict(updated_at='2022-03-10T20:00:00Z')])
def test_report_version_and_single_issuer_are_required(change):
    action, article, effective = fixture()
    assert cash_body_publication(action, article | change, effective) is None


def test_two_reported_dividends_in_same_paragraph_are_ambiguous():
    action, article, effective = fixture()
    second = ' The company declared a cash dividend of $0.25 per share payable April 21, 2022, with record date April 8, 2022.'
    article['content'] = article['content'].replace('</p>', second + '</p>')
    assert cash_body_publication(action, article, effective) is None
