"""Seal one complete dividend work list from existing captures; no downloads."""
from pathlib import Path
import argparse
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from nn_meta.v7.cash_actions import record_key
    from nn_meta.v7.dividend_closure import dividend_census
    from nn_meta.v7.storage import identity, receipt, sha, transaction, verify
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('inventory', 'actions', 'other-instruments', 'renames', 'stock-cash', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if (not args.output.resolve().is_relative_to(ROOT / 'nn_meta')
            or shutil.disk_usage(ROOT).free < 100 * 1024**3):
        raise ValueError('Repository artifact disk and reserve required')
    inputs = {}

    def merge(values):
        for path, digest in values.items():
            if path in inputs and inputs[path] != digest:
                raise ValueError('Conflicting dividend source binding')
            inputs[path] = digest

    for path in (args.inventory, args.actions, args.other_instruments, args.renames, args.stock_cash):
        doc = verify(path)
        merge({str(path / 'complete.json'): sha(path / 'complete.json')})
        merge({str(path / name): digest for name, digest in doc['files'].items()})
        if (path / 'inputs.json').exists():
            merge(json.loads((path / 'inputs.json').read_text()))
    declaration = json.loads((args.inventory / 'declaration.json').read_text())
    merge(declaration['inputs']); merge(declaration['sources'])
    for path in (Path(__file__), ROOT / 'nn_meta/v7/dividend_closure.py',
                 ROOT / 'nn_meta/v7/cash_actions.py', ROOT / 'nn_meta/v7/storage.py'):
        merge({str(path): sha(path)})

    def read(path, name):
        return json.loads((path / (name + '.json')).read_text())

    other, renames = read(args.other_instruments, 'treatments'), read(args.renames, 'events')
    resolved = {record_key(r) for e in [*other, *renames] for r in e['replaces']}
    pending = [r for r in read(args.actions, 'unresolved') if record_key(r) not in resolved]
    report, uncompiled, missing_held = dividend_census(read(args.inventory, 'candidates'),
        read(args.actions, 'actions'), other, renames, read(args.stock_cash, 'events'), pending)
    if any(sha(path) != digest for path, digest in inputs.items()):
        raise ValueError('Dividend sources changed')
    with transaction(args.output) as temp:
        for name, value in [('inputs', inputs), ('report', report), ('uncompiled', uncompiled),
                            ('missing_held', missing_held)]:
            (temp / (name + '.json')).write_text(json.dumps(value, indent=2) + '\n')
        receipt(temp, dict(identity=identity(inputs), research_ready=False))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
