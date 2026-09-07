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


def test_freeze_report_does_not_reuse_stale_tick_worker_count(tmp_path):
    s = snapshot(tmp_path, 'wanted', [{'pid': 123, 'stage': 'freeze'}])
    s['parallel'] = {'active': {'GM': 456}, 'symbol_workers': 4, 'download_workers_per_symbol': 16}
    s['parallel_result'] = {'complete': True}
    s['freeze_resource_plan'] = {'symbol_workers': 4, 'planned_symbol_ram_gib': 20,
                                 'ram_reserve_gib': 4, 'reserved_cpus': [3, 4, 11, 12]}
    report = render(s, None)
    assert 'Freeze workers: 1/4' in report
    assert 'Symbol workers:' not in report
    s['processes'] = []
    assert 'Symbol workers:' not in render(s, None)
