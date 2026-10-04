"""Versioned VWAP successor of the immutable ETFE midpoint setup."""
import json
from pathlib import Path
import shutil

from nn_meta.etfe.preparation import ROOT, SCOPE as OLD_SCOPE, digest, file_sha, save_new, end_exclusive_utc
from nn_meta.etfe.verification import verify_setup
from nn_meta.etfe.vwap_reference import BASIS

SCOPE = ROOT/'docs/specs/ETFE_SCOPE_VWAP_20261003.json'
POLICY = dict(basis=BASIS, bar_minutes=1, field='vw', fallback=None,
    availability_lag_seconds=1, max_bar_end_age_seconds=60,
    availability_model='max(bar_end_plus_1s,captured_availability_if_present)',
    historical_revision_timing='unverified_requires_admission',
    minimum_volume_contracts=1, minimum_trade_count=1,
    missing_or_stale='no_reference_no_fill_no_forward_fill',
    latency_ns=1000000000, entry_deadline_ns=60000000000,
    fee=0.001, slippage=0.0005, multiplier=100,
    execution_status='reference_only_execution_model_requires_validation',
    quote_age_and_size_rules='superseded_by_bar_reference_rules')
FEATURES = dict(status='explicit_mapping_required_before_schema_admission',
    retained='all strategy families, parameters, signal timings and nonquote feature scopes',
    unavailable='historical bid/ask, spread, quote sizes, quote age and quote-derived fields',
    replacement='versioned trade/bar features; no fabricated quotes or zero-filled old columns',
    approval='user authorized trade/bar methodology; individual replacement semantics still require audit')


def expected_scope():
    scope = json.loads(OLD_SCOPE.read_text())
    scope['schema'] = 'etfe-research-scope-v2'
    scope['supersedes_scope_sha256'] = file_sha(OLD_SCOPE)
    scope.pop('quote_policy')
    scope['pricing_policy'] = POLICY.copy()
    scope['risk_policy']['price_basis'] = BASIS
    scope['feature_scope'] = FEATURES.copy()
    return scope


def validate_scope(scope):
    if scope != expected_scope():
        raise ValueError('VWAP scope differs from the accepted versioned amendment')


def prepare(output, predecessor):
    output, predecessor = Path(output).resolve(), Path(predecessor).resolve()
    if (output.parent != ROOT/'nn_meta/validation' or not output.name.startswith('etfe-')
            or predecessor.parent != ROOT/'nn_meta/validation'
            or not predecessor.name.startswith('etfe-')):
        raise ValueError('Expected isolated direct ETFE validation roots')
    if output.exists():
        raise FileExistsError(output)
    verify_setup(predecessor)
    old = json.loads((predecessor/'plan.json').read_text())
    scope = json.loads(SCOPE.read_text())
    validate_scope(scope)
    sources = sorted(set(old['source_bindings']) | {
        'nn_meta/etfe/vwap_reference.py', 'nn_meta/etfe/vwap_setup.py',
        'nn_meta/etfe/verification.py', 'scripts/prepare_etfe_vwap.py',
        'scripts/verify_etfe_vwap.py', str(OLD_SCOPE.relative_to(ROOT)),
        str(SCOPE.relative_to(ROOT))})
    catalog = json.loads((predecessor/'catalog.json').read_text())
    plan = dict(schema='etfe-setup-plan-v2', expert='etfe', scope=scope,
        scope_sha256=file_sha(SCOPE), catalog_sha256=catalog['catalog_sha256'],
        predecessor=dict(root=str(predecessor), plan_sha256=old['plan_sha256'],
            files={n:file_sha(predecessor/n) for n in ('scope.json','catalog.json','plan.json','PREPARED.json')}),
        catalog_reuse='Unchanged ETFE strategy identities only; new pricing plan, no rows/models reused.',
        runtime=dict(pool='etfe', state_root=str(output), provider='alpaca', feed='opra'),
        history_end_exclusive_utc=end_exclusive_utc(scope),
        source_bindings={n:file_sha(ROOT/n) for n in sources},
        readiness=dict(ready_for_build=False, ready_for_training=False,
            blockers=['exact_alpaca_history_boundary', 'minute_vwap_and_trade_coverage',
                'historical_bar_availability_and_revision_policy', 'dated_contract_reference_coverage',
                'trade_bar_feature_mapping_and_schema', 'strategy_timeframe_parity',
                'execution_cost_liquidity_stop_and_label_validation',
                'etfe_folds_and_trials', 'measured_resources_and_recovery']))
    plan['plan_sha256'] = digest(plan)
    output.mkdir()
    save_new(output/'scope.json', scope)
    shutil.copyfile(predecessor/'catalog.json', output/'catalog.json')
    save_new(output/'plan.json', plan)
    snapshot = output/'source-snapshot'
    for name, expected in plan['source_bindings'].items():
        target = snapshot/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, target)
        if file_sha(target) != expected:
            raise ValueError('Source changed during preparation; partial run preserved')
    receipt = dict(schema='etfe-preparation-receipt-v2', expert='etfe',
        status='prepared_not_admitted', plan_sha256=plan['plan_sha256'],
        files={n:file_sha(output/n) for n in ('scope.json','catalog.json','plan.json')},
        source_snapshot=plan['source_bindings'], ready_for_build=False, ready_for_training=False)
    save_new(output/'PREPARED.json', receipt)
    return verify(output)


def verify(folder, *, source_root=ROOT):
    folder, source_root = Path(folder), Path(source_root)
    receipt = json.loads((folder/'PREPARED.json').read_text())
    if (receipt.get('schema') != 'etfe-preparation-receipt-v2'
            or receipt.get('status') != 'prepared_not_admitted' or receipt.get('expert') != 'etfe'
            or receipt.get('ready_for_build') is not False or receipt.get('ready_for_training') is not False):
        raise ValueError('Expected unadmitted ETFE VWAP receipt')
    if set(receipt['files']) != {'scope.json', 'catalog.json', 'plan.json'}:
        raise ValueError('Unexpected preparation census')
    for name, sha in receipt['files'].items():
        if file_sha(folder/name) != sha:
            raise ValueError(f'Prepared artifact changed: {name}')
    plan = json.loads((folder/'plan.json').read_text())
    scope = json.loads((folder/'scope.json').read_text())
    catalog = json.loads((folder/'catalog.json').read_text())
    validate_scope(scope)
    if (plan['schema'] != 'etfe-setup-plan-v2' or plan['expert'] != 'etfe'
            or plan['scope'] != scope or plan['scope_sha256'] != file_sha(source_root/SCOPE.relative_to(ROOT))
            or plan['plan_sha256'] != digest({k:v for k,v in plan.items() if k != 'plan_sha256'})
            or plan['plan_sha256'] != receipt['plan_sha256']):
        raise ValueError('VWAP plan/scope binding mismatch')
    if (catalog['catalog_sha256'] != plan['catalog_sha256']
            or catalog['catalog_sha256'] != digest({k:v for k,v in catalog.items() if k != 'catalog_sha256'})
            or catalog['expert'] != 'etfe' or catalog['symbols'] != scope['symbols']
            or catalog['signal_minutes'] != scope['signal_minutes'] or catalog['ready_for_build'] is not False
            or plan['runtime'] != dict(pool='etfe',state_root=str(folder.resolve()),provider='alpaca',feed='opra')
            or plan['readiness']['ready_for_build'] is not False
            or plan['readiness']['ready_for_training'] is not False):
        raise ValueError('VWAP catalog/runtime/admission mismatch')
    if receipt['source_snapshot'] != plan['source_bindings']:
        raise ValueError('Snapshot binding mismatch')
    for name, sha in plan['source_bindings'].items():
        for root in (source_root, folder/'source-snapshot'):
            path = (root/name).resolve()
            if not path.is_relative_to(root.resolve()) or file_sha(path) != sha:
                raise ValueError(f'VWAP source changed: {name}')
    return dict(status='vwap_setup_integrity_verified_not_admitted', expert='etfe',
        plan_sha256=plan['plan_sha256'], basis=scope['pricing_policy']['basis'],
        ticker_variant_combinations=catalog['ticker_variant_combinations'],
        ready_for_build=False, ready_for_training=False)
