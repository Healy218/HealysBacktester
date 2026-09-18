from copy import deepcopy

import pytest

from nn_meta.v7.dividend_closure import dividend_census
from nn_meta.v7.storage import identity


def fixture():
    rows = [dict(provider='provider', kind='dividends', action_id=str(i),
        category='cash', subject_symbol='ABC', effective_date=f'2024-01-0{i+2}',
        term='1', term_issues=[], record={'amount': 1}, record_sha256=identity({'amount': 1}))
        for i in range(3)]
    refs = [{k: r[k] for k in ('provider', 'kind', 'action_id', 'record_sha256')} for r in rows]
    actions = [dict(category='cash', symbol='ABC', security_id='sid', cash_amount='1',
        action={'event_id': str(i), 'effective_at': rows[i]['effective_date'] + 'T14:30:00Z'},
        replaces=[refs[i]]) for i in range(2)]
    held = [dict(compiled_event_id='0', event_id='held-0', security_id='sid')]
    return rows, actions, [], [], held, [rows[-1]]


def test_disjoint_price_and_held_work_and_complete_record_partition():
    report, uncompiled, missing = dividend_census(*fixture())
    assert report['remaining_dividend_review_items'] == 2
    assert report['compiled_held_cash_events'] == 1
    assert uncompiled[0]['effective_date'] == '2024-01-04'
    assert missing[0]['effective_date'] == '2024-01-03'
    assert not report['dividends_complete'] and not report['step_1_complete']


@pytest.mark.parametrize('change', ['missing', 'duplicate_original', 'duplicate_resolved',
    'changed_original', 'changed_pending', 'overlap', 'wrong_held', 'duplicate_held', 'wrong_identity'])
def test_audit_rejects_incomplete_or_changed_evidence(change):
    rows, actions, other, renames, held, pending = deepcopy(fixture())
    if change == 'missing': pending.clear()
    if change == 'duplicate_original': rows.append(deepcopy(rows[0]))
    if change == 'duplicate_resolved': actions.append(deepcopy(actions[0]))
    if change == 'changed_original': rows[0]['record']['amount'] = 2
    if change == 'changed_pending': pending[0] = dict(pending[0], term='2')
    if change == 'overlap': pending.append(rows[0])
    if change == 'wrong_held': held[0]['compiled_event_id'] = 'missing'
    if change == 'duplicate_held': held.append(deepcopy(held[0]))
    if change == 'wrong_identity': held[0]['security_id'] = 'different'
    with pytest.raises(ValueError):
        dividend_census(rows, actions, other, renames, held, pending)
