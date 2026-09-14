import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import v6_readiness as audit
from scripts import v6_training_pipeline as pipeline


def test_readiness_missing_campaign_reports_all_blockers_without_creating_files(tmp_path):
    missing = tmp_path / 'campaign/v6'
    report = audit.assess(missing)
    assert report['scanner_promotion'] is False
    assert len(report['blocked_checks']) == 8
    assert not missing.exists()


def test_receipts_reject_traversal_and_changed_artifacts(tmp_path):
    base = tmp_path / 'bundle'; base.mkdir()
    outside = tmp_path / 'other'; outside.write_text('secret')
    with pytest.raises(ValueError, match='mismatch'):
        audit.verified_files(base, {'../other': audit.sha(outside)})
    inside = base / 'model'; inside.write_text('weights')
    hashes = {'model': audit.sha(inside)}
    audit.verified_files(base, hashes)
    inside.write_text('changed')
    with pytest.raises(ValueError, match='mismatch'):
        audit.verified_files(base, hashes)


def health():
    h = dict(finite_losses=True, finite_weights=True, finite_predictions=True,
             val_loss=.3, validation_rows=200)
    return dict(val_loss=.3, validation=dict(classifier=dict(h), magnitude=dict(h)))


@pytest.mark.parametrize('head', ['classifier', 'magnitude'])
@pytest.mark.parametrize('field,value', [('val_loss', float('nan')), ('finite_weights', False),
                                       ('finite_predictions', False), ('validation_rows', 0)])
def test_neural_audit_requires_both_heads(head, field, value):
    receipt = health()
    audit.finite_health(receipt)
    receipt['validation'][head][field] = value
    with pytest.raises(ValueError):
        audit.finite_health(receipt)


def test_quote_audit_requires_all_scenarios_and_resolved_both_policies():
    metric = dict(n_positions=10, total_return=.05, max_drawdown=.1, independent_ledger_match=True)
    result = {'policies': {side: {'scenarios': {scenario: dict(metric)
              for scenario in ['quotes_base', 'quotes_stressed', 'quotes_severe']}}
              for side in ['candidate', 'baseline']}}
    audit.quote_metrics(result, 'scenarios')
    result['policies']['baseline']['unresolved_selections'] = 1
    with pytest.raises(ValueError, match='unresolved'):
        audit.quote_metrics(result, 'scenarios')


def test_report_rejects_other_model_even_with_valid_receipt(tmp_path):
    campaign = tmp_path / 'campaign/v6'
    model = campaign / 'model_final/ensemble_config.json'
    model.parent.mkdir(parents=True); model.write_text('{}')
    base = tmp_path / 'report'; base.mkdir()
    scope = dict(schema='v6-execution-validation-v1', inputs={str(model): audit.sha(model)},
                 sources={str(model): audit.sha(model)})
    result = dict(schema=scope['schema'], complete=True)
    for name, doc in [('scope.json', scope), ('results.json', result)]:
        (base / name).write_text(json.dumps(doc))
    (base / 'complete.json').write_text(json.dumps({'outputs': {
        p.name: audit.sha(p) for p in base.iterdir()}}))
    with pytest.raises(ValueError, match='another model'):
        audit.report_bundle(base, scope['schema'], campaign=campaign, model_sha='other')


@pytest.fixture
def pipeline_case(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, 'ROOT', tmp_path)
    for source in pipeline.SOURCES:
        path = tmp_path / source; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(source)
    monkeypatch.setattr(pipeline, 'environment', lambda *a: {})
    args = argparse.Namespace(parent='parent', campaign='new', reuse_completed='old', workers=2, threads=2)
    return args, tmp_path / 'nn_meta/campaigns/new/v6/runs/pipeline'


def test_pipeline_training_failure_prevents_validation_and_persists_status(pipeline_case, monkeypatch):
    args, records = pipeline_case
    called = []
    def fail(command, **kw):
        called.append(command)
        return SimpleNamespace(returncode=7)
    monkeypatch.setattr(pipeline.subprocess, 'run', fail)
    with pytest.raises(RuntimeError, match='training failed'):
        pipeline.run(args)
    status = audit.read(records / 'status.json')
    assert status['status'] == 'failed' and status['stage'] == 'training'
    assert len(called) == 1 and 'scripts.continue_v6_training' in called[0]
    assert not (records / 'execution.complete.json').exists()


def test_pipeline_completion_and_resume_verify_outputs(pipeline_case, monkeypatch):
    args, records = pipeline_case
    called = []
    def complete(command, **kw):
        called.append(command)
        if 'scripts.continue_v6_training' in command:
            base = records.parent / 'continuation'; base.mkdir()
            pipeline.write(base / 'latest.json', {'status': 'complete'})
            artifact = records.parent / 'test-artifact'
            artifact.write_text('weights')
            for stage in ('assemble', 'experiments', 'evaluate', 'finalize'):
                pipeline.write(base / f'{stage}.json', {'returncode': 0, 'outputs': {
                    str(artifact.relative_to(pipeline.ROOT)): audit.sha(artifact)}})
        elif 'scripts.validate_v6_execution' in command:
            base = Path(command[-1]); base.mkdir(parents=True)
            pipeline.write(base / 'results.json', {'complete': True})
            pipeline.write(base / 'complete.json', {'outputs': {'results.json': audit.sha(base / 'results.json')}})
        else:
            kw['stdout'].write(json.dumps({'schema': 'v6-readiness-v1', 'scanner_promotion': False}))
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(pipeline.subprocess, 'run', complete)
    pipeline.run(args)
    assert audit.read(records / 'status.json')['status'] == 'complete'
    assert audit.read(records / 'status.json')['promotion_status'] == 'blocked'
    pipeline.run(args)
    assert len(called) == 3
    (records / 'readiness.json').write_text('changed')
    with pytest.raises(ValueError, match='mismatch'):
        pipeline.run(args)
    assert audit.read(records / 'status.json')['status'] == 'failed'


def test_training_resume_rechecks_nested_model_hashes(pipeline_case):
    args, records = pipeline_case
    base = records.parent.parent
    stage_dir = base / 'runs/continuation'; stage_dir.mkdir(parents=True)
    pipeline.write(stage_dir / 'latest.json', {'status': 'complete'})
    model = base / 'model'; model.write_text('weights')
    for stage in ('assemble', 'experiments', 'evaluate', 'finalize'):
        pipeline.write(stage_dir / f'{stage}.json', {'returncode': 0, 'outputs': {
            str(model.relative_to(pipeline.ROOT)): audit.sha(model)}})
    pipeline.training_outputs(base)
    model.write_text('changed')
    with pytest.raises(ValueError, match='mismatch'):
        pipeline.training_outputs(base)


def test_service_uses_bounded_resources_and_foreground_pipeline(pipeline_case):
    args, _ = pipeline_case
    command = pipeline.service_command(args)
    assert '--property=MemoryMax=24G' in command
    assert '--property=MemorySwapMax=2G' in command
    assert '--property=AllowedCPUs=2-7,10-15' in command
    assert '--property=CPUQuota=600%' in command
    assert not any('MemoryHigh' in value for value in command)
    assert command[-1] == '--run'
    assert 'scripts.v6_training_pipeline' in command
