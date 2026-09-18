import copy
import json
from pathlib import Path

import pandas as pd
import pytest

from nn_meta.v7.dividend_dispositions import reviewed_dispositions, coverage_with_dispositions


@pytest.fixture
def case():
    return json.loads((Path(__file__).parent/'fixtures/v7_dividend_dispositions.json').read_text())


def compile_case(c):
    return reviewed_dispositions(c['originals'], c['pending'], c['reviews'],
        c['actions'], c['cash'], c['renames'])


def test_real_corrections_preserve_originals_and_existing_cash(case):
    before = copy.deepcopy(case)
    dispositions, remaining = compile_case(case)
    assert len(dispositions) == 10
    assert all(not d['creates_cash'] and not d['creates_price_factor'] for d in dispositions)
    assert all(r['category'] != 'cash' for r in remaining)
    assert case == before
    assert len(case['cash']) == 1  # GOLD aliases the existing B payment.


@pytest.mark.parametrize('change', ['original', 'alias_amount', 'rename', 'cusip',
    'cancel_date', 'noncash_dependency', 'unsupported', 'duplicate'])
def test_rejects_false_or_incomplete_corrections(case, change):
    if change == 'original':
        case['originals'][0]['record']['ticker'] = 'WRONG'
    elif change == 'alias_amount':
        case['cash'][0]['cash_per_share'] = '0.20'
    elif change == 'rename':
        case['renames'] = []
    elif change == 'cusip':
        next(r for r in case['reviews'] if r['symbol'] == 'TE')['reviewed_facts']['record_cusip'] = 'wrong'
    elif change == 'cancel_date':
        next(r for r in case['reviews'] if r['symbol'] == 'DFS')['reviewed_facts']['cancellation_date'] = '2025-05-24'
    elif change == 'noncash_dependency':
        next(r for r in case['reviews'] if r['symbol'] == 'AMC')['reviewed_facts']['pending_noncash_references'] = []
    elif change == 'unsupported':
        case['reviews'][0]['disposition'] = 'ignore_missing_provider'
    else:
        case['reviews'].append(case['reviews'][0])
    with pytest.raises(ValueError):
        compile_case(case)


def test_noncash_routing_keeps_real_feature_dates_blocked(case):
    original = [r for r in case['originals'] if 'AMC' in r['scoped_symbols']]
    review = [r for r in case['reviews'] if r['symbol'] == 'AMC']
    dispositions, pending = reviewed_dispositions(original, original, review, [], [], [])
    history = pd.DataFrame([dict(security_id='AMC-common', stock_ticker='AMC',
        source_date=d, source_status='observed') for d in ['2023-08-22','2023-08-23','2023-08-25']])
    coverage = coverage_with_dispositions(history, original, [], pending, dispositions,
        policy=case['coverage_policy'], other=[], renames=[], cash=[])
    assert coverage.history_admitted.tolist() == [True, False, False]
    assert coverage.coverage_status.iloc[1] == 'unresolved_noncash_distribution'
