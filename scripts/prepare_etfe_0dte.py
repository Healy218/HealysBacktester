"""Seal or verify the fresh-Alpaca, 0–5 DTE ETFE setup successor."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nn_meta.etfe.acquisition import digest, save, sha, write_new
from nn_meta.etfe.purchase_policy_v2 import SCOPE, load_scope

SOURCES = ('nn_meta/etfe/purchase_policy_v2.py','scripts/prepare_etfe_0dte.py',
    'nn_meta/etfe/acquisition.py','nn_meta/etfe/expansion.py','scripts/expand_etfe_alpaca.py',
    'nn_meta/etfe/normalization.py','scripts/normalize_etfe.py',
    'docs/specs/ETFE_SCOPE_0DTE_20261004.json','docs/specs/ETFE_0DTE_NORMALIZATION_20261004.md')


def verify(root):
    root = Path(root)
    plan = json.loads((root/'PLAN.json').read_text())
    if digest({k:v for k,v in plan.items() if k!='sha256'}) != plan['sha256']:
        raise ValueError('Setup plan checksum mismatch')
    if (plan['scope'] != load_scope() or plan['ready_for_build'] or plan['ready_for_training']
            or plan['schema'] != 'etfe-setup-plan-v4'):
        raise ValueError('Current scope/admission mismatch')
    for name, expected in plan['sources'].items():
        if sha((root/'source'/name).read_bytes()) != expected or sha((ROOT/name).read_bytes()) != expected:
            raise ValueError('Current setup source changed')
    catalog = json.loads((root/'catalog.json').read_text())
    if sha((root/'catalog.json').read_bytes()) != plan['catalog_file_sha256']:
        raise ValueError('Catalog checksum mismatch')
    if (catalog['expert']!='etfe' or catalog['ticker_variant_combinations']!=25353
            or catalog['symbols']!=['SPY','QQQ','VOO'] or catalog['signal_minutes']!=[1,5,15]):
        raise ValueError('Catalog scope mismatch')
    return dict(status='current_setup_verified_not_admitted',plan_sha256=plan['sha256'],
        actual_calendar_dte=plan['scope']['actual_calendar_dte'],
        targets=plan['scope']['dte_targets'],ready_for_build=False,ready_for_training=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['prepare','verify'])
    p.add_argument('--root',type=Path,required=True)
    args=p.parse_args(); root=args.root.resolve()
    if root.parent != ROOT/'nn_meta/validation' or not root.name.startswith('etfe-'):
        p.error('Isolated direct ETFE validation root required')
    if args.command=='prepare':
        predecessor=ROOT/'nn_meta/validation/etfe-setup-20261004-alpaca-r0'
        from scripts.prepare_etfe_current import verify as verify_predecessor
        old=verify_predecessor(predecessor)
        scope=load_scope()
        raw=(predecessor/'catalog.json').read_bytes()
        plan=dict(schema='etfe-setup-plan-v4',scope=scope,
            predecessor_plan_sha256=old['plan_sha256'],
            catalog_reuse='ETFE mathematical strategy identities only; no market data/features/labels/models',
            catalog_file_sha256=sha(raw),sources={n:sha((ROOT/n).read_bytes()) for n in SOURCES},
            ready_for_build=False,ready_for_training=False)
        plan['sha256']=digest(plan)
        root.mkdir(exist_ok=False)
        save(root/'PLAN.json',plan)
        write_new(root/'catalog.json',raw)
        for n in SOURCES:
            target=root/'source'/n;target.parent.mkdir(parents=True,exist_ok=True)
            write_new(target,(ROOT/n).read_bytes())
    print(json.dumps(verify(root),indent=2))


if __name__=='__main__':
    main()
