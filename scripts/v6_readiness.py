"""Audit a V6 campaign and its actual promotion evidence without loading models.

This is an evidence inventory, not a shipping authorization. A successful
research gate cannot stand in for external parity or forward execution review.
No model files, scanner settings, notifications or historical results change.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    def invalid(value):
        raise ValueError(f'non-finite JSON value: {value}')
    return json.loads(Path(path).read_text(), parse_constant=invalid)


def verified_files(base, records):
    """Relative receipts cannot escape their evidence directory."""
    base = Path(base).resolve()
    if not isinstance(records, dict) or not records:
        raise ValueError('receipt contains no files')
    for name, digest in records.items():
        path = base / name
        if (Path(name).is_absolute() or not path.resolve().is_relative_to(base)
                or any(p.is_symlink() for p in (path, *path.parents))
                or sha(path) != digest):
            raise ValueError(f'receipt mismatch: {name}')


def report_bundle(directory, schema, *, campaign, model_sha):
    directory = Path(directory)
    receipt = read(directory / 'complete.json')
    records = receipt.get('outputs', {})
    if not {'scope.json', 'results.json'} <= set(records):
        raise ValueError('report receipt does not cover its scope and results')
    verified_files(directory, records)
    scope, result = read(directory / 'scope.json'), read(directory / 'results.json')
    if scope.get('schema') != schema or result.get('schema') != schema:
        raise ValueError('unexpected evidence schema')
    for group in ('inputs', 'sources'):
        if not scope.get(group):
            raise ValueError(f'report does not bind {group}')
        for path, digest in scope[group].items():
            if not Path(path).is_absolute() or sha(path) != digest:
                raise ValueError(f'report {group} changed: {path}')
    if schema == 'v6-execution-validation-v1':
        model_path = str((campaign / 'model_final/ensemble_config.json').resolve())
        if scope['inputs'].get(model_path) != model_sha:
            raise ValueError('execution report belongs to another model/campaign')
        if result.get('complete') is not True:
            raise ValueError('execution report is incomplete')
    elif scope.get('shadow_scope', {}).get('artifacts', {}).get('ensemble_config.json') != model_sha:
        raise ValueError('forward report belongs to another model')
    return scope, result


def finite_health(receipt):
    if not isinstance(receipt.get('val_loss'), (float, int)) or not math.isfinite(receipt['val_loss']):
        raise ValueError('neural loss is not finite')
    for head in ('classifier', 'magnitude'):
        health = receipt.get('validation', {}).get(head, {})
        if (not all(health.get(k) is True for k in ('finite_losses', 'finite_weights', 'finite_predictions'))
                or not isinstance(health.get('val_loss'), (float, int))
                or not math.isfinite(health['val_loss']) or health.get('validation_rows', 0) <= 0):
            raise ValueError(f'{head} lacks finite validation evidence')


def quote_metrics(result, key):
    """Both policies and every frozen stress scenario must have ledger evidence."""
    names = {'quotes_base', 'quotes_stressed', 'quotes_severe'}
    for side in ('candidate', 'baseline'):
        section = result['policies'][side]
        if section.get('unresolved_selections', 0) != 0:
            raise ValueError(f'{side} has unresolved forward selections')
        scenarios = section.get(key, {})
        if set(scenarios) != names:
            raise ValueError(f'{side} lacks all frozen quote cost scenarios')
        for name, metrics in scenarios.items():
            if (metrics.get('independent_ledger_match') is not True
                    or metrics.get('n_positions', 0) <= 0
                    or any(not isinstance(metrics.get(k), (float, int))
                           or not math.isfinite(metrics[k]) for k in ('total_return', 'max_drawdown'))):
                raise ValueError(f'{side}/{name} lacks finite matched quote-ledger results')


def assess(campaign, *, execution=None, forward=None):
    campaign = Path(campaign).resolve()
    checks = []
    facts = {}

    def check(name, function, next_step):
        try:
            detail = function()
            checks.append(dict(name=name, status='passed', detail=detail))
            return detail
        except (ValueError, OSError, KeyError, TypeError, AttributeError) as exc:
            checks.append(dict(name=name, status='blocked', detail=str(exc), next_step=next_step))
            return None

    def training():
        status = read(campaign / 'runs/continuation/latest.json')
        if status.get('status') != 'complete':
            raise ValueError(f"training is {status.get('status')} at {status.get('stage')}")
        scope = read(campaign / 'continuation_scope.json')
        if scope.get('repair_neural') is not True:
            raise ValueError('campaign predates the repaired neural training scope')
        for stage in ('assemble', 'experiments', 'evaluate', 'finalize'):
            receipt = read(campaign / 'runs/continuation' / f'{stage}.json')
            if receipt.get('returncode') != 0:
                raise ValueError(f'{stage} did not complete successfully')
            verified_files(ROOT, receipt.get('outputs'))
        return {'status': 'complete', 'scope_sha256': sha(campaign / 'continuation_scope.json')}

    check('corrected_training', training, 'Finish the corrected continuation and retain all four stage receipts.')

    def neural():
        scope = read(campaign / 'continuation_scope.json')
        expected = (scope['training']['folds'] + 1) * len(scope['training']['selection_seeds'])
        receipts = []
        groups = {}
        for path in sorted((campaign / 'runs/seed-jobs').glob('*/*/complete.json')):
            receipt = read(path)
            if receipt.get('settings', {}).get('family') != 'nn':
                continue
            finite_health(receipt)
            verified_files(path.parent, receipt.get('hashes'))
            groups.setdefault(path.parent.parent.name, []).append(receipt['settings']['seed'])
            receipts.append(path)
        if (len(receipts) != expected or len(groups) != scope['training']['folds'] + 1
                or any(sorted(seeds) != sorted(scope['training']['selection_seeds']) for seeds in groups.values())):
            raise ValueError(f'{len(receipts)}/{expected} expected finite neural selection receipts present')
        return {'finite_selection_seeds': len(receipts), 'prepared_groups': len(groups)}

    check('neural_health', neural, 'Complete every NN fold/final-selection seed with finite losses, weights and predictions.')

    def bundle():
        manifest = read(campaign / 'model_final/manifest.json')
        artifacts = manifest.get('output_artifacts', {})
        if 'ensemble_config.json' not in artifacts:
            raise ValueError('manifest does not cover ensemble configuration')
        verified_files(campaign / 'model_final', artifacts)
        cfg = read(campaign / 'model_final/ensemble_config.json')
        scope = read(campaign / 'continuation_scope.json')
        if (cfg.get('eligible') is not True or len(cfg['run_ids']) != len(scope['training']['final_seeds'])
                or sorted(cfg['final_seeds']) != sorted(scope['training']['final_seeds'])
                or len(set(cfg['run_ids'])) != len(cfg['run_ids'])):
            raise ValueError('final ensemble did not meet the frozen seed budget and research gate')
        for run in cfg['run_ids']:
            receipt = read(campaign / 'model_final' / run / 'complete.json')
            verified_files(campaign / 'model_final' / run, receipt.get('hashes'))
            if cfg['family'] == 'nn':
                finite_health(receipt)
        facts.update(model_sha256=artifacts['ensemble_config.json'], family=cfg['family'],
                     feature_contract=cfg['feature_contract_version'], final_seeds=len(cfg['run_ids']))
        return dict(facts)

    check('final_bundle', bundle, 'Finalize and verify the full ensemble; the previous model cannot substitute.')

    def execution_check():
        if not execution:
            raise ValueError('no execution report supplied')
        scope, result = report_bundle(execution, 'v6-execution-validation-v1', campaign=campaign,
                                      model_sha=facts['model_sha256'])
        for side in ('candidate', 'baseline'):
            cases = result['policies'][side]['aggregate']
            if len(cases) != 4 or any(len(v['costs']) != 4 for v in cases.values()):
                raise ValueError('incomplete aggregate cost/latency grid')
            if any(m.get('independent_ledger_match') is not True for v in cases.values() for m in v['costs'].values()):
                raise ValueError('aggregate independent ledger mismatch')
        return {'matched_comparisons': 32, 'basis': scope['frozen_policy']['basis']}

    check('aggregate_execution', execution_check, 'Run validate_v6_execution against this completed campaign.')

    def quotes():
        if not execution:
            raise ValueError('no quote execution report supplied')
        _, result = report_bundle(execution, 'v6-execution-validation-v1', campaign=campaign,
                                  model_sha=facts['model_sha256'])
        quote_metrics(result, 'quotes')
        return 'Both policies have three finite quote-cost scenarios and matched independent ledgers.'

    check('quote_execution', quotes, 'Capture actual executable quotes and complete frozen roll legs; rerun quote validation.')

    def forward_check():
        if not forward:
            raise ValueError('no completed forward replay supplied')
        _, result = report_bundle(forward, 'v6-shadow-replay-v1', campaign=campaign,
                                  model_sha=facts['model_sha256'])
        quote_metrics(result, 'scenarios')
        return 'Resolved forward quote-ledger evidence exists; prospective period and performance still require review.'

    check('forward_execution', forward_check, 'Collect fresh sealed shadow observations, quotes and frozen exits; replay both policies.')

    # Neither report format certifies these facts. Do not turn research fields
    # or a user-supplied boolean into scanner authorization.
    contract = facts.get('feature_contract', 'unavailable')
    checks.append(dict(name='external_feature_and_feed_parity', status='blocked',
        detail=f'Bundle contract: {contract}. Training/report receipts do not certify TradingView or receipt/SIP parity.',
        next_step='Retain actual reviewed TradingView captures and compare live receipt/condition features to the historical contract.'))
    checks.append(dict(name='scanner_operating_review', status='blocked',
        detail='Forward performance, frozen selection/sizing, executable contracts and scanner state need a release review.',
        next_step='Review the model-bound forward period, failures, costs and scanner behavior before enabling alerts.'))
    return {'schema': 'v6-readiness-v1', 'campaign': campaign.parent.name,
        'generated_at': datetime.now(timezone.utc).isoformat(), 'facts': facts, 'checks': checks,
        'scanner_promotion': False, 'research_only': True,
        'blocked_checks': [c['name'] for c in checks if c['status'] == 'blocked']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--campaign-root', type=Path, required=True)
    p.add_argument('--execution-root', type=Path)
    p.add_argument('--forward-root', type=Path)
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    report = assess(a.campaign_root, execution=a.execution_root, forward=a.forward_root)
    payload = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + '\n'
    if a.output:
        with a.output.open('x') as stream:
            stream.write(payload)
    print(payload, end='')


if __name__ == '__main__':
    main()
