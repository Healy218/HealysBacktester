import pytest

from nn_meta.v7.action_inventory import candidate, reconcile, symbols


def cash(provider, amount=1., identifier='cash', **changes):
    row = (dict(id=identifier, ticker='ABC', ex_dividend_date='2022-05-06', cash_amount=amount,
                currency='USD', historical_adjustment_factor=.01, split_adjusted_cash_amount=.1)
           if provider == 'massive' else
           dict(id=identifier, symbol='ABC', ex_date='2022-05-06', rate=amount, foreign=False,
                process_date='2022-05-20'))
    row.update(changes)
    return make(provider, 'dividends' if provider == 'massive' else 'cash_dividends', row)


def make(provider, kind, record):
    return candidate(provider, kind, record, scoped_symbols={'ABC'}, start='2022-03-15',
                     end='2026-09-14', source={'payload': 'retained-original'})


def test_cash_reconciles_original_amount_not_current_share_factor_or_pay_date():
    rows = [cash('massive'), cash('alpaca')]
    result = reconcile(rows, {('ABC', '2022-05-06'): {'identity'}})[0]
    assert result['status'] == 'matching_single_event_terms'
    assert result['provider_terms'] == {'massive': '1.0', 'alpaca': '1.0'}
    assert result['eligible_security_id'] == 'identity'
    assert result['effective_date'] == '2022-05-06'
    assert rows[1]['process_date'] == '2022-05-20'
    assert not result['publication_verified'] and not result['research_ready']


def test_explicit_split_ratios_ignore_cumulative_factor_and_detect_combined_day():
    m = make('massive', 'splits', dict(id='split', ticker='ABC', execution_date='2022-05-06',
        split_from=1, split_to=4, adjustment_type='forward_split', historical_adjustment_factor=.001))
    a = make('alpaca', 'forward_splits', dict(id='split', symbol='ABC', ex_date='2022-05-06',
        old_rate=2, new_rate=8, process_date='2022-05-10'))
    result = reconcile([m, a], {})[0]
    assert result['provider_terms'] == {'massive': '4', 'alpaca': '4'}
    assert result['status'] == 'matching_single_event_terms'
    both = reconcile([m, a, cash('massive'), cash('alpaca')], {})
    assert len(both) == 2
    assert all(r['combined_event_day'] and r['status'] == 'matching_total_requires_combined_review' for r in both)
    assert all(r['eligible_security_id'] is None for r in both)


def test_multiple_cash_records_keep_all_ids_and_never_auto_admit_matching_sum():
    result = reconcile([cash('massive', 1., 'ordinary'), cash('massive', .25, 'special'),
                        cash('alpaca', 1.25)], {})[0]
    assert result['status'] == 'matching_total_requires_combined_review'
    assert result['multiple_records']
    assert result['provider_action_ids']['massive'] == ['ordinary', 'special']
    assert result['provider_terms'] == {'massive': '1.25', 'alpaca': '1.25'}


def test_event_roles_include_acquirees_and_nested_stock_legs_without_name_matching():
    row = dict(id='complex', acquiree_symbol='ABC', acquirer_symbol='DEF', effective_date='2022-05-06',
               stock_movements=[dict(symbol='XYZ')], name='ABC Holdings')
    found = symbols(row)
    assert found == [{'role': 'acquiree_symbol', 'symbol': 'ABC'},
                     {'role': 'acquirer_symbol', 'symbol': 'DEF'},
                     {'role': 'stock_movements.0.symbol', 'symbol': 'XYZ'}]
    c = make('alpaca', 'stock_mergers', row)
    assert c['category'] == 'complex'
    result = reconcile([c, cash('massive'), cash('alpaca')], {})[0]
    assert result['combined_event_day'] and result['complex_action_ids'] == ['complex']
    assert make('alpaca', 'stock_mergers', dict(id='other', name='ABC', symbol='NOTABC',
               effective_date='2022-05-06')) is None


def test_process_only_actions_remain_undated_and_ex_dates_control_window():
    c = make('alpaca', 'name_changes', dict(id='rename', old_symbol='ABC', new_symbol='XYZ',
                process_date='2022-05-06'))
    assert c['effective_date'] is None
    assert c['term_issues'] == ['missing_effective_date']
    assert cash('alpaca', ex_date='2022-03-14', process_date='2022-03-20') is None
    assert cash('alpaca', ex_date='2026-09-14', process_date='2026-09-30')['effective_date'] == '2026-09-14'


@pytest.mark.parametrize('change', [dict(rate=None), dict(rate=True), dict(foreign=True)])
def test_incomplete_foreign_or_invalid_terms_stay_unreviewed(change):
    result = reconcile([cash('massive'), cash('alpaca', **change)], {})[0]
    assert result['status'] == 'unreviewed_terms'


def test_date_mismatches_and_missing_counterparts_are_never_nearest_matched():
    groups = reconcile([cash('massive'), cash('alpaca', ex_date='2022-05-09')], {})
    assert len(groups) == 2 and all(r['status'] == 'single_provider' for r in groups)
    assert reconcile([cash('massive'), cash('alpaca', 1.01)], {})[0]['status'] == 'term_mismatch'


def test_duplicate_records_and_ambiguous_active_identity_fail_closed():
    c = cash('massive')
    with pytest.raises(ValueError, match='Duplicate'):
        reconcile([c, c], {})
    with pytest.raises(ValueError, match='Ambiguous'):
        reconcile([c], {('ABC', '2022-05-06'): {'old', 'new'}})


def test_invalid_date_is_not_normalized_or_used_as_processing_time():
    with pytest.raises(ValueError, match='ISO'):
        cash('massive', ex_dividend_date='20220506')
    with pytest.raises(ValueError, match='JSON compliant'):
        cash('alpaca', rate=float('inf'))


def test_stock_dividend_in_splits_endpoint_is_not_admitted_as_simple_share_split():
    row = make('massive', 'splits', dict(id='stock-div', ticker='ABC', execution_date='2022-05-06',
        split_from=1, split_to=1.1, adjustment_type='stock_dividend'))
    assert row['term_issues'] == ['not_a_declared_simple_split']
    assert reconcile([row], {})[0]['status'] == 'unreviewed_terms'
