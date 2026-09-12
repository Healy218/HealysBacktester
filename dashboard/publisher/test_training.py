from pathlib import Path
import hashlib
import json
import sys
import pytest
sys.path.insert(0, str(Path(__file__).parent))
import training
from collect import collect_home
from publish import envelope


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def fixture(root, monkeypatch, status='running', stage='evaluate'):
    monkeypatch.setattr(training, 'processes', lambda campaign: ['nn_meta.v4_evaluate'])
    base = root / 'nn_meta/campaigns/current/v6'
    write(base / 'continuation_scope.json', dict(campaign='current', parent='old', symbols=['AA'], feature_contract_version='research',
        training=dict(workers=2, threads=2, final_seeds=[0, 1], epochs=60, trees=600, label='label_excess', selection_seeds=[0], validation_days=40)))
    write(base / 'runs/continuation/latest.json', dict(campaign='current', status=status, stage=stage, returncode=1 if status=='failed' else 0))
    doc = root / 'docs/reviews/2026-09-12-v6-training.md'; doc.parent.mkdir(parents=True); doc.write_text('# Training review\n')
    return base


def bind(root, base, stage, files):
    outputs = {}
    for relative, value in files.items():
        path = base / relative
        write(path, value)
        outputs[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    write(base / f'runs/continuation/{stage}.json', dict(returncode=0, outputs=outputs))


def test_zero_seed_workers_does_not_mean_stopped(tmp_path, monkeypatch):
    fixture(tmp_path, monkeypatch)
    r, status = training.live(tmp_path, 'current')
    assert status['activeWorkers'] == 0 and status['activity'] == 'evaluate: running'
    assert r['status'] == 'Training'
    assert not r['folds']


def test_explicit_campaign_rejects_mismatched_receipt(tmp_path, monkeypatch):
    base = fixture(tmp_path, monkeypatch)
    write(base / 'runs/continuation/latest.json', dict(campaign='old', status='complete'))
    r = training.collect_training(tmp_path, 'current')
    assert r['status'] == 'Unavailable'
    assert r['versions'][-1]['folds'] == []
    assert 'v6: report unavailable or failed integrity check' in r['issues']


def test_changed_evaluation_is_not_published(tmp_path, monkeypatch):
    base = fixture(tmp_path, monkeypatch)
    bind(tmp_path, base, 'evaluate', {'reports/evaluate.json': []})
    write(base / 'reports/evaluate.json', {'tampered': True})
    with pytest.raises(ValueError, match='binding failed'):
        training.checked(tmp_path, base, 'evaluate', 'reports/evaluate.json')
    assert training.collect_training(tmp_path, 'current')['status'] == 'Unavailable'


def test_final_gate_rejection_is_distinct_from_operational_failure(tmp_path, monkeypatch):
    base = fixture(tmp_path, monkeypatch, 'failed', 'finalize')
    write(base / 'runs/continuation/finalize.json', dict(returncode=1))
    (base / 'runs/continuation/finalize.log').write_text('NO ELIGIBLE CONFIG — rejected\n')
    r, status = training.live(tmp_path, 'current')
    assert r['status'] == 'Gate rejected'
    assert 'Gate rejected during finalize' in status['activity']
    assert not (base / 'model_final').exists()
    (base / 'runs/continuation/finalize.log').write_text('Traceback: worker failed\n')
    assert training.live(tmp_path, 'current')[0]['status'] == 'Failed'


def test_complete_requires_bound_configuration_and_all_stage_receipts(tmp_path, monkeypatch):
    base = fixture(tmp_path, monkeypatch, 'complete', 'finalize')
    with pytest.raises(FileNotFoundError):
        training.live(tmp_path, 'current')
    # A bare bundle and complete marker are never enough.
    write(base / 'model_final/ensemble_config.json', dict(eligible=True))
    assert training.collect_training(tmp_path, 'current')['status'] == 'Unavailable'


def test_validation_baseline_is_never_used_as_test_baseline():
    r = training.report('v6', '', '')
    training.modern_folds(r, [dict(window=dict(val_start='2026-01-01', test_start='2026-03-01', test_end='2026-04-01'),
        winner=dict(family='gbt', mode='ev', threshold=.05, eligible=True, baseline_return=9.99,
            test=dict(total_return=.1, max_drawdown=.2, n_kept=0), marked=dict(total_return=.12, max_drawdown=.25)))])
    f = r['folds'][0]
    assert f['baseline'] is None and f['returnValue'] == .12 and f['drawdown'] == .25 and f['trades'] == 0
    assert '+999.0%' in r['tables'][0]['rows'][0]


def test_missing_versions_remain_visible_and_home_payload_bounded(tmp_path):
    h = collect_home(tmp_path, training_root=tmp_path, training_campaign='current')
    assert len(h['training']['versions']) == 6
    assert all(v['status'] == 'Unavailable' for v in h['training']['versions'])
    assert len(envelope(h)['fields']['payload']['stringValue']) < 750_000


def test_historical_percent_and_count_parser(tmp_path):
    p = tmp_path / 'nn_meta/reports/meta_report.md'; p.parent.mkdir(parents=True)
    p.write_text('## Walk-forward folds\n| 1 | 2025-07-08 | 2025-07-09→2025-10-31 | +2.0% (250) | -35.5% | -59.8% (252) | +28.5% | ✅❌ |')
    d = tmp_path / 'docs/EXPERIMENTS.md'; d.parent.mkdir(); d.write_text('## Backtest / walk-forward verdicts\nsource\n## Live experts')
    r = training.legacy(tmp_path, 'v2')
    assert r['folds'][0]['returnValue'] == .02
    assert r['folds'][0]['trades'] == 250
    assert r['folds'][0]['drawdown'] is None


def test_completed_report_includes_final_validation_without_claiming_deployment(tmp_path, monkeypatch):
    base = fixture(tmp_path, monkeypatch, 'complete', 'finalize')
    assembly = dict(input_rows=10, membership_rows=9, dataset_rows=8, mark_rows=50)
    bind(tmp_path, base, 'assemble', {'artifacts/meta_dataset.assembly.json': assembly})
    bind(tmp_path, base, 'experiments', {'reports/objective-comparisons/results.json': {'auc': .6}})
    bind(tmp_path, base, 'evaluate', {'reports/evaluate.json': [], 'reports/evaluate.manifest.json': {}})
    md = base / 'reports/evaluate.md'; md.write_text('# Evaluation\n')
    receipt = training.obj(base / 'runs/continuation/evaluate.json')
    receipt['outputs'][str(md.relative_to(tmp_path))] = hashlib.sha256(md.read_bytes()).hexdigest()
    write(base / 'runs/continuation/evaluate.json', receipt)
    config = dict(eligible=True, family='gbt', mode='ev', threshold=.05, final_seeds=[0,1], features=['x'],
                  val_return=.2, val_max_drawdown=.1, val_n_kept=20)
    bind(tmp_path, base, 'finalize', {'model_final/ensemble_config.json': config, 'model_final/manifest.json': {}})
    (base / 'runs/continuation/finalize.log').write_text('=== re-validating\neligible=True\n')
    r, status = training.live(tmp_path, 'current')
    assert r['status'] == 'Complete · research only'
    assert 'has not been deployed' in r['summary']
    assert any(t['title'] == 'Final ensemble · validation tail' for t in r['tables'])
    assert status['evidence']['final_model_manifest']
    config['eligible'] = False
    bind(tmp_path, base, 'finalize', {'model_final/ensemble_config.json': config, 'model_final/manifest.json': {}})
    with pytest.raises(ValueError, match='eligibility mismatch'):
        training.live(tmp_path, 'current')
