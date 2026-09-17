"""Compile the authorized ordinary-action policy over the full retained inventory."""
from pathlib import Path
from collections import Counter
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
    from nn_meta.session_calendar import SessionCalendar
    from nn_meta.v7.ordinary_actions import BASIS, compile_ordinary_actions
    from nn_meta.v7.storage import identity, receipt, sha, transaction, verify

    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('inventory', 'reviews', 'history', 'calendar', 'policy', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT / 'nn_meta'):
        raise ValueError('Repository artifact disk required')
    if shutil.disk_usage(ROOT).free < 100 * 1024**3:
        raise ValueError('Preserve the 100 GiB disk reserve')
    inputs = {}

    def merge(values):
        for path, digest in values.items():
            if path in inputs and inputs[path] != digest:
                raise ValueError('Conflicting action source bindings')
            inputs[path] = digest

    def bind(path):
        doc = verify(path)
        merge({str(path / 'complete.json'): sha(path / 'complete.json')})
        merge({str(path / name): digest for name, digest in doc['files'].items()})
        return doc

    bind(args.inventory)
    inventory = json.loads((args.inventory / 'declaration.json').read_text())
    merge(inventory['inputs']); merge(inventory['sources'])
    bind(args.history)
    merge(json.loads((args.history / 'inputs.json').read_text()))
    if bind(args.reviews).get('schema') != 'v7-cash-reviews-v1':
        raise ValueError('Sealed whole-event publication reviews required')
    merge(json.loads((args.reviews / 'inputs.json').read_text()))
    for path in [args.calendar, args.policy, Path(__file__),
                 *[ROOT / 'nn_meta/v7' / (name + '.py') for name in
                   ('ordinary_actions', 'cash_actions', 'action_inventory', 'causal_prices', 'storage', 'runtime')],
                 ROOT / 'nn_meta/session_calendar.py']:
        merge({str(path): sha(path)})
    if any(sha(path) != digest for path, digest in inputs.items()):
        raise ValueError('Ordinary-action parent bindings changed')
    policy = json.loads(args.policy.read_text())
    candidates = json.loads((args.inventory / 'candidates.json').read_text())
    reviews = json.loads((args.reviews / 'cash_reviews.json').read_text())
    events, pending, decisions = compile_ordinary_actions(candidates, reviews,
        pd.read_parquet(args.history / 'history.parquet'),
        SessionCalendar(json.loads(args.calendar.read_text())), policy)
    reconstructed = [e for e in events if e['admission_basis'] == BASIS]
    report = dict(candidate_records=len(candidates), compiled_events=len(events),
        reviewed_publication_events=len(events) - len(reconstructed),
        reconstructed_events=len(reconstructed),
        reconstructed_categories=dict(Counter(e['category'] for e in reconstructed)),
        consumed_provider_records=sum(len(e['replaces']) for e in events),
        unresolved_provider_records=len(pending), simple_group_treatments=dict(Counter(d['treatment'] for d in decisions)),
        unresolved_record_reasons=dict(Counter(r['compilation_reason'] for r in pending)),
        spy_reconstructed_events=sum(e['symbol'] == 'SPY' for e in reconstructed),
        event_securities=len({e['security_id'] for e in events}),
        policy_identity=identity(policy), full_security_admitted=False, research_ready=False,
        limitations=['Effective-session reconstruction availability is assumed, not verified publication',
                     'No complete no-event interval or full-security admission',
                     'No stock entitlements, payment clocks or option deliverables inferred'])
    with transaction(args.output) as temp:
        for name, value in [('policy', policy), ('actions', events), ('unresolved', pending),
                            ('groups', decisions), ('inputs', inputs), ('report', report)]:
            (temp / (name + '.json')).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
        if any(sha(path) != digest for path, digest in inputs.items()):
            raise ValueError('Action sources changed during compilation')
        receipt(temp, dict(identity=identity(inputs), research_ready=False))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
