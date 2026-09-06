import json
from scripts.watch_v6_progress import campaign_processes, snapshot, render


def test_process_binding_and_pid_reuse(tmp_path):
    for pid, campaign in [(101, 'wanted'), (102, 'other')]:
        p = tmp_path / str(pid)
        p.mkdir()
        (p / 'cmdline').write_bytes(b'python\0-m\0nn_meta.train_meta\0')
        (p / 'environ').write_bytes(f'NN_META_CAMPAIGN={campaign}\0NN_META_POOL=v6\0'.encode())
        (p / 'stat').write_text(f'{pid} (python) S ' + ' '.join(['0'] * 18 + ['12345']))
    assert campaign_processes('wanted', tmp_path) == [
        {'pid': 101, 'start_ticks': '12345', 'stage': 'training'}]


def test_no_completion_from_old_or_partial_artifacts(tmp_path):
    prep = tmp_path / 'nn_meta/expanded_inputs/wanted/inventory-r4'
    prep.mkdir(parents=True)
    (prep / 'scope.json').write_text(json.dumps({'symbols': ['AA', 'AAL']}))
    (prep / 'AA').mkdir()
    (prep / 'AA/manifest.json').write_text('{}')
    old = tmp_path / 'nn_meta/campaigns/other/v6/model_final'
    old.mkdir(parents=True)
    (old / 'manifest.json').write_text('{}')
    s = snapshot(tmp_path, 'wanted', [])
    assert s['counts']['inventory_symbols'] == 1
    assert not s['evidence_present']['final_model_manifest']
    assert 'IDLE/STOPPED' in render(s, None)
    assert 'watcher remains active' in render(s, None)


def test_failure_and_no_progress_are_visible(tmp_path):
    p = tmp_path / 'nn_meta/expanded_inputs/wanted/full-run'
    p.mkdir(parents=True)
    (p / 'freeze-launcher-result.json').write_text('{"returncode": 1}')
    s = snapshot(tmp_path, 'wanted', [])
    text = render(s, s)
    assert 'failed (exit 1)' in text
    assert 'No observed count/log progress' in text


def test_halfway_reminder_uses_freeze_not_inventory(tmp_path):
    s = snapshot(tmp_path, 'wanted', [])
    s['total_symbols'] = 453
    s['counts']['inventory_symbols'] = 453
    s['counts']['freeze_shards'] = 226
    assert 'HALFWAY FREEZE' not in render(s, None)
    s['counts']['freeze_shards'] = 227
    assert 'HALFWAY FREEZE' in render(s, None)
