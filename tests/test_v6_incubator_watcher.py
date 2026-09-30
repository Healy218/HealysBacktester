import json

from scripts.watch_v6_incubator import render, snapshot


def observe(tmp_path, status='running', stage='candidates_and_labels', **extra):
    path = tmp_path / 'latest-run.json'
    path.write_text(json.dumps(dict(status=status, stage=stage, symbols_complete=449,
                                   symbols_required=449, training_started=False, **extra)))
    return snapshot(path, tmp_path / 'missing.json', {'ActiveState': 'activating'})


def test_data_complete_does_not_imply_training_complete(tmp_path):
    text = render(observe(tmp_path))
    assert '449/449 (100.0%)' in text
    assert 'Pending — starts automatically' in text
    assert 'Evaluation / final freeze: pending' in text


def test_training_and_evaluation_transition(tmp_path):
    s = observe(tmp_path, stage='training', members_complete=7, members_required=40)
    s['run']['training_started'] = True
    assert '7/40 (17.5%)' in render(s)
    s['run'].update(stage='evaluation', members_complete=40)
    assert 'Evaluation / final freeze: in progress' in render(s)


def test_inactive_service_does_not_show_saved_running_as_live(tmp_path):
    observe(tmp_path)
    s = snapshot(tmp_path / 'latest-run.json', tmp_path / 'missing.json', {'ActiveState': 'inactive'})
    assert s['state'].startswith('stopped')


def test_deadline_is_not_completed_candidate(tmp_path):
    text = render(observe(tmp_path, status='deadline_reached', stage='training', error='deadline'))
    assert 'candidate frozen' not in text
    assert 'Errors: "deadline"' in text
    text = render(observe(tmp_path, status='candidate_frozen', stage='done'))
    assert 'Evaluation / final freeze: complete' in text
