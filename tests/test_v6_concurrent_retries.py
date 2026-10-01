import pytest
from scripts.v6_retry_failed_20260930 import TRANSIENT, check_binding, pending, resources_allow, safe_to_resume


def test_only_terminal_502_symbols_are_selected():
    run = {'errors': [{'symbol':'A', 'error':TRANSIENT}, {'symbol':'B', 'error':'invalid seal'},
                      {'symbol':'C', 'error':TRANSIENT}, {'symbol':'D', 'error':TRANSIENT}]}
    assert pending(run, {'D':3}, {'C'}) == ['A']


def test_changed_invocation_refuses_shared_writes():
    plan = {'run': {'started_at':'original', 'through':'2026-09-28', 'contract_identity':'one', 'run_dir':'r'}}
    check_binding(plan['run'], plan)
    with pytest.raises(ValueError):
        check_binding(plan['run'] | {'started_at':'new'}, plan)


def test_resume_requires_terminal_run_and_every_error_recovered():
    run = {'status':'running', 'errors':[{'symbol':'A', 'error':TRANSIENT}]}
    assert not safe_to_resume(run, {'A'})
    run['status'] = 'blocked'
    assert not safe_to_resume(run, set())
    assert safe_to_resume(run, {'A'})
    run['errors'].append({'symbol':'B', 'error':'invalid seal'})
    assert not safe_to_resume(run, {'A','B'})


def test_side_worker_respects_combined_budget():
    assert resources_allow(5, 8*1024**3, 2)
    assert not resources_allow(6, 8*1024**3, 2)
    assert not resources_allow(5, 24*1024**3, 2)
    assert not resources_allow(5, 8*1024**3, 0)
