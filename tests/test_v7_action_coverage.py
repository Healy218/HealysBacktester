from copy import deepcopy
import json
from pathlib import Path

import pandas as pd
import pytest

from nn_meta.v7.action_coverage import coverage_panel, require_history_coverage
from nn_meta.v7.ordinary_actions import compile_ordinary_actions
from tests.test_v7_ordinary_actions import fixture, make_candidate


def inputs():
    rows, reviews, history, calendar, policy = fixture()
    history['source_status'] = 'observed'
    events, unresolved, _ = compile_ordinary_actions(rows, reviews, history, calendar, policy)
    return history, rows, events, unresolved


def test_event_compilation_does_not_prove_no_event_intervals_or_held_entitlements():
    panel = coverage_panel(*inputs())
    assert panel.coverage_status.tolist() == ['no_event_not_established', 'compiled_event_only']
    assert not panel.history_admitted.any() and not panel.held_position_admitted.any()
    for held in (False, True):
        with pytest.raises(ValueError, match='unresolved'):
            require_history_coverage(panel, security_id='security', dates=panel.source_date.tolist(), held=held)


@pytest.mark.parametrize('change', ['missing_record', 'duplicate_pending', 'consumed_and_pending',
    'corrupt_pending', 'duplicate_event', 'wrong_event_identity', 'wrong_event_hash', 'missing_event_day'])
def test_record_partition_and_consumer_identity_are_exact(change):
    history, rows, events, pending = deepcopy(inputs())
    if change == 'missing_record': events = []
    if change in ('duplicate_pending', 'corrupt_pending'):
        events = []; pending = deepcopy(rows)
        if change == 'duplicate_pending': pending.append(pending[0])
        else: pending[0]['term'] = '999'
    if change == 'consumed_and_pending': pending = deepcopy(rows)
    if change == 'duplicate_event': events *= 2
    if change == 'wrong_event_identity': events[0]['security_id'] = 'other'
    if change == 'wrong_event_hash': events[0]['replaces'][0]['record_sha256'] = 'corrupt'
    if change == 'missing_event_day': history = history.iloc[:1]
    with pytest.raises(ValueError): coverage_panel(history, rows, events, pending)


def test_undated_events_block_alias_histories_without_invented_effective_date():
    history, rows, events, pending = inputs()
    undated = make_candidate('alpaca', 'name_changes', dict(id='rename', old_symbol='ABC',
        new_symbol='XYZ', process_date='2024-09-16'))
    rows.append(undated); pending.append(undated)
    history.loc[0, 'stock_ticker'] = 'XYZ'
    panel = coverage_panel(history, rows, events, pending)
    assert panel.coverage_status.eq('unresolved_action_records').all()
    assert all(len(x) == 1 for x in panel.unresolved_record_ids)


def test_dated_events_keep_other_dates_unknown_and_missing_identity_explicit():
    history, rows, events, pending = inputs()
    history.loc[0, ['stock_ticker', 'source_status']] = [pd.NA, 'no_listed_source']
    dated = make_candidate('alpaca', 'spin_offs', dict(id='spin', source_symbol='ABC', ex_date='2024-09-13'))
    rows.append(dated); pending.append(dated)
    panel = coverage_panel(history, rows, events, pending)
    assert panel.coverage_status.tolist() == ['unresolved_identity', 'unresolved_action_records']
    assert panel.event_id.notna().sum() == 1


def test_consumer_guard_rejects_missing_dates_even_when_available_dates_are_admitted():
    panel = coverage_panel(*inputs()); panel['history_admitted'] = True
    # Simulate a separately admitted table to exercise the guard's coverage join.
    assert len(require_history_coverage(panel, security_id='security', dates=panel.source_date.tolist())) == 2
    with pytest.raises(ValueError):
        require_history_coverage(panel, security_id='security', dates=['2024-09-12', '2024-09-13', '2024-09-16'])
    with pytest.raises(ValueError):
        require_history_coverage(panel, security_id='security', dates=panel.source_date.tolist(), held=True)


def test_authorized_assumption_admits_quiet_history_but_never_conflicts_or_holdings():
    args = inputs()
    policy = json.loads((Path(__file__).resolve().parents[1] / 'docs/specs/V7_NO_EVENT_ADMISSION_20260917.json').read_text())
    panel = coverage_panel(*args, policy=policy)
    assert panel.coverage_status.tolist() == ['assumed_no_event', 'compiled_event_with_assumed_coverage']
    assert panel.history_admitted.all() and not panel.completeness_verified.any()
    assert not panel.held_position_admitted.any()
    assert len(require_history_coverage(panel, security_id='security', dates=panel.source_date.tolist())) == 2
    pending = make_candidate('alpaca', 'spin_offs', dict(id='spin', source_symbol='ABC', ex_date='2024-09-13'))
    args[1].append(pending); args[3].append(pending)
    blocked = coverage_panel(*args, policy=policy)
    assert blocked.history_admitted.tolist() == [True, False]
    policy['status'] = 'pending_user_decision_not_admitted'
    with pytest.raises(ValueError): coverage_panel(*args, policy=policy)
