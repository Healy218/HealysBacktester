from copy import deepcopy

import pytest

from nn_meta.v7.stock_cash import POLICY_ID, validate_cash_event
from nn_meta.v7.stock_cash_extension import extension_candidates, compile_cash_extension
from nn_meta.v7.reviewed_cash import compile_reviewed_cash
from nn_meta.v7.storage import identity
from tests.test_v7_reviewed_cash import fixture


def inputs():
    rows, reviews, history, calendar = fixture()
    reviews[0]['pay_date'] = '2024-06-12'
    actions, _ = compile_reviewed_cash(rows, reviews, history, calendar)
    proposal = dict(schema='v7-remaining-stock-cash-extension-proposal-v1', model_policy_id=POLICY_ID,
        scope_change=False, research_ready=False, finite_remaining_groups=1,
        eligible_groups=[dict(symbol='ABC', ex_date='2024-06-12', replaces=actions[0]['replaces'])])
    policy = dict(schema='v7-remaining-stock-cash-extension-admission-v1', status='user_authorized',
        authorization='Test fixture authorization', proposal_identity=identity(proposal), model_policy_id=POLICY_ID)
    return actions, rows, [], calendar, policy, proposal


def test_preview_does_not_admit_and_primary_dates_reach_existing_cash_contract():
    actions, rows, base, calendar, policy, proposal = inputs()
    ready, pending = extension_candidates(actions, rows, base, calendar, proposal)
    assert len(ready) == 1 and not pending and 'schema' not in ready[0]
    events, pending = compile_cash_extension(actions, rows, base, calendar, policy, proposal)
    assert len(events) == 1 and not pending
    e = events[0]
    validate_cash_event(e, calendar)
    assert e['cash_per_share'] == '0.15' and e['pay_date'] == '2024-06-12'
    assert e['date_basis'] == 'compiled_primary_date_review'
    assert e['withholding_fraction'] == 0 and not e['broker_posting_verified']


@pytest.mark.parametrize('change', ['unapproved', 'changed_proposal', 'changed_source',
    'changed_reference', 'already_admitted', 'duplicate_scope', 'partial_group', 'unreviewed_dates'])
def test_finite_authorization_and_original_source_guards(change):
    actions, rows, base, calendar, policy, proposal = inputs()
    if change == 'unapproved': policy['status'] = 'proposed_not_authorized'
    if change == 'changed_proposal': proposal['research_ready'] = True
    if change == 'changed_source': rows[0]['record']['cash_amount'] = 2
    if change == 'changed_reference': proposal['eligible_groups'][0]['replaces'][0]['record_sha256'] = 'changed'
    if change == 'already_admitted': base = [{'compiled_event_id': actions[0]['action']['event_id']}]
    if change == 'duplicate_scope':
        proposal['eligible_groups'].append(deepcopy(proposal['eligible_groups'][0])); proposal['finite_remaining_groups'] = 2
        policy['proposal_identity'] = identity(proposal)
    if change == 'partial_group': actions[0]['replaces'] = actions[0]['replaces'][:-1]
    if change == 'unreviewed_dates': actions[0]['admission_basis'] = 'matching_provider_historical_reconstruction'
    with pytest.raises(ValueError): compile_cash_extension(actions, rows, base, calendar, policy, proposal)


def test_unresolved_source_groups_stay_counted_without_invented_cash():
    actions, rows, base, calendar, policy, proposal = inputs()
    events, pending = compile_cash_extension([], rows, base, calendar, policy, proposal)
    assert not events and pending[0]['reason'] == 'cash_action_uncompiled'
    for field in ('reviewed_record_date', 'reviewed_pay_date'): actions[0].pop(field)
    events, pending = compile_cash_extension(actions, rows, base, calendar, policy, proposal)
    assert not events and pending[0]['reason'] == 'unresolved_record_or_pay_date'
