from datetime import datetime, timezone
import json

from scripts.watch_v7_demand import snapshot, render


def fixture(tmp_path):
    (tmp_path / 'declaration').mkdir()
    (tmp_path / 'declaration/plan.json').write_text(json.dumps({'securities': ['a', 'b', 'c']}))
    (tmp_path / 'kernel-recovery').mkdir()
    progress = dict(stage='v7-3-kernel-recovery', state='running', selected=3, completed=1,
                    running=['b'], failed={}, output_bytes=1024, max_output_bytes=2048,
                    updated_at='2026-09-26T05:00:00+00:00', full_scope_complete=False)
    (tmp_path / 'kernel-recovery/progress.json').write_text(json.dumps(progress))
    for sid in ('a', 'b', 'unrelated'):
        p = tmp_path / 'checkpoints' / sid
        p.mkdir(parents=True); (p / 'complete.json').write_text('{}')
    (tmp_path / 'checkpoints/c.partial-interrupted').mkdir()
    (tmp_path / 'progress.json').write_text(json.dumps(dict(progress, state='failed')))
    return tmp_path


def test_recovery_monitor_distinguishes_saved_from_revalidated_and_ignores_partials(tmp_path):
    output = fixture(tmp_path)
    value = snapshot(output, 'active', datetime(2026, 9, 26, 5, 0, 1, tzinfo=timezone.utc))
    assert (value['saved'], value['verified_this_run'], value['remaining']) == (2, 1, 1)
    assert value['state'] == 'running' and not value['stale']
    text = render(value)
    assert '2/3' in text and '1/3' in text and 'receipt presence' in text
    assert 'Training requires' in text


def test_monitor_does_not_present_stopped_stale_snapshot_as_running(tmp_path):
    value = snapshot(fixture(tmp_path), 'inactive', datetime(2026, 9, 26, 5, 5, tzinfo=timezone.utc))
    assert value['stale']
    assert value['state'].startswith('stopped')
    assert 'STALE' in render(value)
