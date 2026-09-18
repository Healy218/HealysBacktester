"""Compile finite matching cash groups whose common-share units were reviewed."""
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
    from nn_meta.session_calendar import SessionCalendar
    from nn_meta.v7.reviewed_cash_units import compile_unit_reviewed_cash
    from nn_meta.v7.storage import identity, sha, verify, transaction, receipt
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('actions', 'history', 'calendar', 'witnesses', 'reviews', 'policy', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT/'nn_meta') or shutil.disk_usage(ROOT).free < 100*1024**3:
        raise ValueError('Repository artifact disk and reserve required')
    inputs = {}

    def merge(values):
        for p, d in values.items():
            if p in inputs and inputs[p] != d:
                raise ValueError('Conflicting unit-review source bindings')
            inputs[p] = d

    for path in (args.actions, args.history, args.witnesses):
        doc = verify(path)
        merge({str(path/'complete.json'): sha(path/'complete.json')})
        merge({str(path/n): d for n, d in doc['files'].items()})
        merge(json.loads((path/'inputs.json').read_text()))
    for path in [Path(__file__), args.reviews, args.policy, args.calendar, ROOT/'nn_meta/session_calendar.py',
                 *[ROOT/'nn_meta/v7'/(n+'.py') for n in ('reviewed_cash_units', 'ordinary_actions',
                     'action_inventory', 'cash_actions', 'causal_prices', 'storage', 'runtime')]]:
        merge({str(path): sha(path)})
    document = json.loads(args.reviews.read_text())
    if document['schema'] != 'v7-finite-matching-cash-unit-reviews-v1':
        raise ValueError('Finite cash unit review document required')
    witness_doc = json.loads((args.witnesses/'reviews.json').read_text())
    if witness_doc['schema'] != 'v7-finite-primary-cash-reviews-v1':
        raise ValueError('Compiled primary common-share unit witnesses required')
    compiled = {e['action']['event_id'] for e in json.loads((args.witnesses/'actions.json').read_text())}
    witnesses = {r['event_id']: r for r in witness_doc['reviews']}
    if not witnesses.keys() <= compiled:
        raise ValueError('Every unit witness must already be compiled from primary evidence')
    new, pending = compile_unit_reviewed_cash(json.loads((args.actions/'unresolved.json').read_text()),
        document['reviews'], witnesses, pd.read_parquet(args.history/'history.parquet'),
        SessionCalendar(json.loads(args.calendar.read_text())), json.loads(args.policy.read_text()))
    base = json.loads((args.actions/'actions.json').read_text())
    events = base + new
    clocks = [(e['security_id'], e['action']['effective_at']) for e in events]
    if len(set(clocks)) != len(clocks):
        raise ValueError('Simultaneous actions require combined review')
    report = dict(compiled_events=len(events), preserved_existing_events=len(base),
        unit_reviewed_cash_events=len(new), unresolved_provider_records=len(pending),
        held_history_admitted=False, research_ready=False)
    if any(sha(p) != d for p, d in inputs.items()):
        raise ValueError('Cash unit source changed')
    with transaction(args.output) as temp:
        for name, value in [('inputs', inputs), ('report', report), ('actions', events),
                            ('unresolved', pending), ('reviews', document)]:
            (temp/(name+'.json')).write_text(json.dumps(value, indent=2)+'\n')
        receipt(temp, dict(identity=identity(inputs), research_ready=False))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
