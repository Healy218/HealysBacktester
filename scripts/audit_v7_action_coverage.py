"""Bind current history/action coverage and retain exact unresolved records."""
from pathlib import Path
import argparse
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import pandas as pd
    from nn_meta.v7.action_coverage import coverage_panel
    from nn_meta.v7.storage import identity, receipt, sha, transaction, verify
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('history', 'inventory', 'actions', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--policy', type=Path)
    parser.add_argument('--other-instruments', type=Path)
    parser.add_argument('--renames', type=Path)
    args = parser.parse_args()
    if (not args.output.resolve().is_relative_to(ROOT / 'nn_meta')
            or shutil.disk_usage(ROOT).free < 100 * 1024**3):
        raise ValueError('Repository artifact disk and 100 GiB reserve required')
    inputs = {}

    def merge(values):
        for path, digest in values.items():
            if path in inputs and inputs[path] != digest:
                raise ValueError('Conflicting action coverage input binding')
            inputs[path] = digest

    for path in (args.history, args.inventory, args.actions):
        doc = verify(path)
        merge({str(path / 'complete.json'): sha(path / 'complete.json')})
        merge({str(path / n): h for n, h in doc['files'].items()})
    for path in (args.history, args.actions):
        merge(json.loads((path / 'inputs.json').read_text()))
    declaration = json.loads((args.inventory / 'declaration.json').read_text())
    merge(declaration['inputs']); merge(declaration['sources'])
    policy, other, pending = None, [], json.loads((args.actions / 'unresolved.json').read_text())
    if args.policy:
        policy = json.loads(args.policy.read_text())
        merge({str(args.policy): sha(args.policy)})
    if args.other_instruments:
        doc = verify(args.other_instruments)
        merge({str(args.other_instruments / 'complete.json'): sha(args.other_instruments / 'complete.json')})
        merge({str(args.other_instruments / n): h for n, h in doc['files'].items()})
        merge(json.loads((args.other_instruments / 'inputs.json').read_text()))
        other = json.loads((args.other_instruments / 'treatments.json').read_text())
        pending = json.loads((args.other_instruments / 'unresolved.json').read_text())
    renames = []
    if args.renames:
        doc = verify(args.renames)
        merge({str(args.renames / 'complete.json'): sha(args.renames / 'complete.json')})
        merge({str(args.renames / n): h for n, h in doc['files'].items()})
        merge(json.loads((args.renames / 'inputs.json').read_text()))
        renames = json.loads((args.renames / 'events.json').read_text())
        pending = json.loads((args.renames / 'unresolved.json').read_text())
    for path in [Path(__file__), *[ROOT / 'nn_meta/v7' / (n + '.py') for n in
            ('action_coverage', 'renames', 'cash_actions', 'ordinary_actions', 'causal_prices', 'storage', 'runtime')]]:
        merge({str(path): sha(path)})
    if any(sha(p) != h for p, h in inputs.items()):
        raise ValueError('Action coverage source changed')
    panel = coverage_panel(pd.read_parquet(args.history / 'history.parquet'),
        json.loads((args.inventory / 'candidates.json').read_text()),
        json.loads((args.actions / 'actions.json').read_text()),
        pending, policy=policy, other_instruments=other, renames=renames)
    report = dict(schema='v7-action-coverage-audit-v1', rows=len(panel),
        securities=panel.security_id.nunique(), sessions=panel.source_date.nunique(),
        statuses=panel.coverage_status.value_counts().to_dict(),
        admitted_history_sessions=int(panel.history_admitted.sum()),
        coverage_policy_identity=identity(policy) if policy else None,
        history_admitted=bool(panel.history_admitted.all()), held_position_admitted=False, research_ready=False,
        limitations=['No-event completeness is assumed only under an explicit authorized policy',
                     'Alpaca capture filters process dates, not effective dates',
                     'Individual compiled chart factors do not admit complete histories or holdings'])
    with transaction(args.output) as temp:
        panel.to_parquet(temp / 'coverage.parquet', index=False)
        for name, value in [('inputs', inputs), ('report', report)]:
            (temp / (name + '.json')).write_text(json.dumps(value, indent=2) + '\n')
        if policy is not None:
            (temp / 'policy.json').write_text(json.dumps(policy, indent=2) + '\n')
        if any(sha(p) != h for p, h in inputs.items()):
            raise ValueError('Action coverage inputs changed during build')
        receipt(temp, dict(identity=identity(inputs), research_ready=False))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
