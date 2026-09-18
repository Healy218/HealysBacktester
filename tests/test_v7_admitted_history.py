import json
from pathlib import Path

import pytest

from nn_meta.v7.action_coverage import coverage_panel
from nn_meta.v7.admitted_history import bind_history_coverage
from nn_meta.v7.storage import receipt, sha
from tests.test_v7_action_coverage import inputs


def artifact(tmp_path):
    history, candidates, events, pending = inputs()
    policy = json.loads((Path(__file__).resolve().parents[1] / 'docs/specs/V7_NO_EVENT_ADMISSION_20260917.json').read_text())
    source = tmp_path / 'original'; source.write_text('original source')
    path = tmp_path / 'coverage'; path.mkdir()
    panel = coverage_panel(history, candidates, events, pending, policy=policy)
    panel.to_parquet(path / 'coverage.parquet', index=False)
    (path / 'policy.json').write_text(json.dumps(policy))
    (path / 'inputs.json').write_text(json.dumps({str(source):sha(source)}))
    receipt(path, {'research_ready':False})
    return path, history, events, source


def test_actual_consumer_binds_the_assumption_original_sources_and_event_identity(tmp_path):
    path, history, events, source = artifact(tmp_path); bound = {}
    declaration = bind_history_coverage(path, history, events, security_id='security', inputs=bound)
    assert declaration['sessions'] == 2 and declaration['policy_identity']
    assert declaration['basis'] == 'retrospective_provider_union_completeness_assumption'
    assert not declaration['completeness_verified'] and not declaration['held_position_admitted']
    assert bound[str(source)] == sha(source)
    assert bound[str(path / 'complete.json')] == sha(path / 'complete.json')


@pytest.mark.parametrize('change', ['source_mutation', 'wrong_route', 'missing_action', 'wrong_policy', 'conflicting_parent'])
def test_consumer_cannot_use_unbound_sources_or_silently_drop_an_admitted_action(tmp_path, change):
    path, history, events, source = artifact(tmp_path); bound = {}
    if change == 'source_mutation': source.write_text('changed')
    if change == 'wrong_route': history.loc[0, 'stock_ticker'] = 'OTHER'
    if change == 'missing_action': events = []
    if change == 'wrong_policy': (path / 'policy.json').write_text('{}')
    if change == 'conflicting_parent': bound[str(source)] = 'different'
    with pytest.raises(ValueError): bind_history_coverage(path, history, events, security_id='security', inputs=bound)
