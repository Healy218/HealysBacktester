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


def test_pace_math_placement_and_stage_boundaries(tmp_path):
    from copy import deepcopy
    from scripts.watch_v6_progress import pace_line
    s = snapshot(tmp_path, 'wanted', [{'pid': 1, 'stage': 'freeze'}])
    s.update(time_utc='2026-09-07T12:00:00+00:00', total_symbols=100)
    s['counts']['freeze_shards'] = 20
    prior = deepcopy(s)
    prior['time_utc'] = '2026-09-07T10:00:00+00:00'
    prior['counts']['freeze_shards'] = 10
    assert pace_line(s, [prior]) == 'Average: 5.0/hour; ETA: ~Sep 08 04:00 UTC ⏲️'
    lines = render(s, prior, [prior]).splitlines()
    assert lines[lines.index('Freeze shards 20/100 🧊') + 1].startswith('Average: 5.0/hour')
    prior['counts']['freeze_shards'] = 20
    assert 'waiting for completions' in pace_line(s, [prior])
    prior['counts']['freeze_shards'] = 21
    assert 'collecting progress' in pace_line(s, [prior])
    prior['processes'] = []
    assert 'collecting progress' in pace_line(s, [prior])
    assert pace_line(dict(s, processes=[]), [prior]) is None


def test_training_pace_does_not_assume_symbol_total(tmp_path):
    from copy import deepcopy
    from scripts.watch_v6_progress import pace_line
    s = snapshot(tmp_path, 'wanted', [{'pid': 1, 'stage': 'training'}])
    s.update(time_utc='2026-09-07T12:00:00+00:00', total_symbols=453)
    s['counts']['training_registry_rows'] = 3
    prior = deepcopy(s)
    prior['time_utc'] = '2026-09-07T11:00:00+00:00'
    prior['counts']['training_registry_rows'] = 1
    assert pace_line(s, [prior]) == 'Average: 2.0/hour; ETA: awaiting total job count ⏲️'


def test_trial_preflight_reports_zero_workers_and_previous_baseline(tmp_path):
    s = snapshot(tmp_path, 'wanted', [{'pid': 1, 'stage': 'freeze trial supervisor'}])
    s['worker_trial'] = {'phase': 'preflight', 'target_workers': 5,
                         'baseline': {'average_per_hour': 12.024}}
    report = render(s, None)
    assert 'Freeze workers: 0/5' in report
    assert 'verifying inputs before five-worker trial' in report
    assert 'Previous four-worker average: 12.0/hour' in report
    assert 'two-hour clock has not started' in report
    assert 'ETA: recalculates after restart ⏲️' in report


def test_build_preflight_and_eligible_symbol_total(tmp_path):
    s = snapshot(tmp_path, 'wanted', [{'pid': 1, 'stage': 'build/assembly launcher'}])
    s['total_symbols'] = 453
    s['build_total_symbols'] = 449
    s['counts']['freeze_shards'] = 453
    s['evidence_present']['baseline_spec'] = True
    s['build_plan'] = {'resources': {'symbol_workers': 4}}
    report = render(s, None)
    assert 'Built symbols 0/449' in report
    assert 'Build workers: 0/4' in report
    assert 'verifying inputs before worker startup' in report
    assert 'waiting for freeze completion' not in report
    assert 'HALFWAY' not in report


def continuation_fixture(root, status='running'):
    base = root / 'nn_meta/campaigns/current/v6'
    run = base / 'runs/continuation'
    run.mkdir(parents=True)
    (base / 'continuation_scope.json').write_text(json.dumps(dict(
        campaign='current', parent='old', symbols=['AA'], training=dict(final_seeds=[0, 1]))))
    (run / 'latest.json').write_text(json.dumps(dict(campaign='current', stage='evaluate', status=status)))
    (run / 'assemble.json').write_text('{"returncode": 0}')
    return base


def test_continuation_supervisor_binds_arguments_and_seed_environment(tmp_path):
    for pid, module, campaign, bound_env in [(101, 'scripts.continue_v6_training', 'current', False),
                                            (102, 'scripts.continue_v6_training', 'old', False),
                                            (103, 'nn_meta.training_jobs', 'current', True)]:
        p = tmp_path / str(pid); p.mkdir()
        (p / 'cmdline').write_bytes(f'python\0-m\0{module}\0--campaign\0{campaign}\0'.encode())
        (p / 'environ').write_bytes(b'NN_META_CAMPAIGN=current\0NN_META_POOL=v6\0' if bound_env else b'')
        (p / 'stat').write_text(f'{pid} (python) S ' + ' '.join(['0'] * 18 + ['12345']))
    assert [p['stage'] for p in campaign_processes('current', tmp_path)] == ['training supervisor', 'seed training']


def test_continuation_evaluation_with_no_seed_workers_is_active(tmp_path):
    base = continuation_fixture(tmp_path)
    seed = base / 'runs/seed-jobs/fold1/nn-s0/complete.json'
    seed.parent.mkdir(parents=True); seed.write_text('{}')
    old = tmp_path / 'nn_meta/campaigns/old/v6/runs/next-stage'
    old.mkdir(parents=True); (old / 'build-result.json').write_text('{"returncode": 1}')
    s = snapshot(tmp_path, 'current', [{'pid': 123, 'stage': 'evaluation/training'}])
    report = render(s, None)
    assert 'evaluate: running' in report
    assert 'Active seed workers: 0' in report
    assert 'Selection seed jobs completed: 1' in report
    assert 'failed' not in report and 'STOPPED' not in report


def test_continuation_terminal_state_requires_receipts_and_manifest(tmp_path):
    base = continuation_fixture(tmp_path, 'complete')
    assert 'verification needed' in render(snapshot(tmp_path, 'current', []), None)
    for stage in ('experiments', 'evaluate', 'finalize'):
        (base / f'runs/continuation/{stage}.json').write_text('{"returncode": 0}')
    (base / 'model_final').mkdir(); (base / 'model_final/manifest.json').write_text('{}')
    assert 'Pipeline completed' in render(snapshot(tmp_path, 'current', []), None)


def test_continuation_missing_processes_does_not_claim_stopped(tmp_path):
    continuation_fixture(tmp_path)
    report = render(snapshot(tmp_path, 'current', []), None)
    assert 'verify the host service' in report
    assert 'STOPPED' not in report
