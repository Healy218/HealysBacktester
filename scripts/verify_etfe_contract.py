"""Verify the ETFE-0 declaration inventory; never admit data or training."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(root=ROOT):
    receipt = json.loads((root/'docs/reviews/2026-10-03-etfe-contract.json').read_text())
    if receipt['gate_closed'] or receipt['ready_for_build'] or receipt['ready_for_training']:
        raise ValueError('This declaration has unresolved source gates')
    for name, expected in receipt['contract_files'].items():
        if sha(root/name) != expected:
            raise ValueError(f'Contract changed: {name}; declare a successor')
    mapping = json.loads((root/'docs/specs/ETFE_FEATURE_MAP_20261003.json').read_text())
    bundle_path = root/receipt['evidence_bundle']['path']
    if sha(bundle_path) != receipt['evidence_bundle']['sha256']:
        raise ValueError('Evidence bundle changed')
    with ZipFile(bundle_path) as bundle:
        inherited = bundle.read('inheritance/V7_MODEL_TRIALS_20260916.json')
    if hashlib.sha256(inherited).hexdigest() != mapping['inherited_schema_sha256']:
        raise ValueError('Inherited schema snapshot changed')
    old = json.loads(inherited)
    fields = mapping['fields']
    names = [f['name'] for f in fields]
    if ([f['inherited_name'] for f in fields] != old['feature_columns']
            or len(fields) != 221 or len(set(names)) != 221
            or mapping['model_order'] != names + ['missing__'+n for n in names]
            or mapping['model_input_count'] != 442
            or len({s['scope'] for s in mapping['tv_scopes']}) != 13):
        raise ValueError('Incomplete feature or source census')
    required = {'formula', 'source', 'available_at', 'window', 'warmup', 'missingness', 'dtype'}
    for f in fields:
        if not required.issubset(f) or any(not f[k] for k in required):
            raise ValueError('Incomplete field declaration')
    if (any(n.startswith('opt_tick_') for n in names) or 'timeframe_30' in names
            or not {'timeframe_1', 'timeframe_5', 'timeframe_15'}.issubset(names)):
        raise ValueError('Stale quote/timeframe schema')
    experiment = json.loads((root/'docs/specs/ETFE_EXPERIMENT_20261003.json').read_text())
    if (experiment['feature_schema_sha256'] != sha(root/'docs/specs/ETFE_FEATURE_MAP_20261003.json')
            or len(experiment['trials']) != 21 or len(set(experiment['fit_ids'])) != 84
            or experiment['required_fit_count'] != 84 or experiment['embargo_sessions'] != 10
            or experiment['ready_for_training'] or experiment['history_end_inclusive'] != '2026-10-02'):
        raise ValueError('Experiment census/binding mismatch')
    snapshot = root/receipt['artifact_root']/'source-snapshot'
    probe = receipt['boundary_probe']
    probe_root = root/receipt['boundary_probe_root']
    with ZipFile(bundle_path) as bundle:
        for name, expected in mapping['source_bindings'].items():
            if hashlib.sha256(bundle.read('source-snapshot/'+name)).hexdigest() != expected:
                raise ValueError(f'Portable source changed: {name}')
            if (snapshot/name).exists() and sha(snapshot/name) != expected:
                raise ValueError(f'Local source snapshot changed: {name}')
        for name, expected in probe['receipt_files'].items():
            if hashlib.sha256(bundle.read('boundary/'+name)).hexdigest() != expected:
                raise ValueError(f'Portable boundary evidence changed: {name}')
            if (probe_root/name).exists() and sha(probe_root/name) != expected:
                raise ValueError(f'Local boundary evidence changed: {name}')
    if probe['requests'] != 10 or probe['transport_failures'] or probe['provider_global_start_verified']:
        raise ValueError('Unexpected boundary control scope')
    return dict(status='contract_declarations_verified_source_gate_open',
                fields=221, model_inputs=442, tv_scopes=13, required_fits=84,
                blockers=receipt['blockers'], ready_for_build=False, ready_for_training=False)


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
