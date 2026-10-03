"""Verify ETFE setup integrity without treating preparation as data readiness."""
import json
from pathlib import Path

from nn_meta.etfe.preparation import ROOT, digest, file_sha, validate_scope


def verify_setup(folder, *, source_root=ROOT):
    folder = Path(folder)
    receipt = json.loads((folder/'PREPARED.json').read_text())
    if receipt.get('status') != 'prepared_not_admitted' or receipt.get('expert') != 'etfe':
        raise ValueError('Expected ETFE preparation receipt')
    required = {'scope.json', 'catalog.json', 'plan.json'}
    if set(receipt['files']) != required:
        raise ValueError('Preparation file census differs')
    for name, expected in receipt['files'].items():
        if file_sha(folder/name) != expected:
            raise ValueError(f'Prepared artifact changed: {name}')
    scope = json.loads((folder/'scope.json').read_text())
    plan = json.loads((folder/'plan.json').read_text())
    catalog = json.loads((folder/'catalog.json').read_text())
    validate_scope(scope)
    # The prepared copy is normalized JSON; scope_sha256 binds the original
    # declared specification bytes, while PREPARED binds the normalized copy.
    declared_scope = Path(source_root)/'docs/specs/ETFE_SCOPE_20261003.json'
    if plan['scope'] != scope or plan['scope_sha256'] != file_sha(declared_scope):
        raise ValueError('Scope binding mismatch')
    if (plan['plan_sha256'] != digest({k:v for k,v in plan.items() if k != 'plan_sha256'})
            or plan['plan_sha256'] != receipt['plan_sha256']):
        raise ValueError('Plan binding mismatch')
    if (catalog['catalog_sha256'] != digest({k:v for k,v in catalog.items() if k != 'catalog_sha256'})
            or catalog['catalog_sha256'] != plan['catalog_sha256']):
        raise ValueError('Catalog binding mismatch')
    if (catalog['expert'] != 'etfe' or catalog['symbols'] != scope['symbols']
            or catalog['signal_minutes'] != scope['signal_minutes']
            or plan['runtime']['pool'] != 'etfe' or plan['runtime']['provider'] != 'alpaca'):
        raise ValueError('ETFE runtime/catalog scope mismatch')
    if (catalog['ready_for_build'] is not False
            or plan['readiness']['ready_for_build'] is not False
            or plan['readiness']['ready_for_training'] is not False):
        raise ValueError('Preparation cannot claim admission')
    for name, expected in plan['source_bindings'].items():
        path = (Path(source_root)/name).resolve()
        if not path.is_relative_to(Path(source_root).resolve()) or file_sha(path) != expected:
            raise ValueError(f'Frozen setup source changed: {name}')
    return dict(status='setup_integrity_verified_not_admitted', expert='etfe',
        plan_sha256=plan['plan_sha256'], source_files=len(plan['source_bindings']),
        families=len(catalog['families']), variants_per_symbol=catalog['variants_per_symbol'],
        ticker_variant_combinations=catalog['ticker_variant_combinations'],
        ready_for_build=False, ready_for_training=False)
