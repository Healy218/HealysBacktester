"""Preview or compile an explicitly authorized finite cash-model extension."""
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
    from nn_meta.session_calendar import SessionCalendar
    from nn_meta.v7.stock_cash_extension import extension_candidates, compile_cash_extension
    from nn_meta.v7.storage import identity, sha, verify, transaction, receipt
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('actions', 'inventory', 'base-events', 'calendar', 'proposal', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preview', action='store_true')
    mode.add_argument('--policy', type=Path)
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT/'nn_meta') or shutil.disk_usage(ROOT).free < 100*1024**3:
        raise ValueError('Repository artifact disk and reserve required')
    inputs = {}

    def merge(values):
        for p, d in values.items():
            if p in inputs and inputs[p] != d:
                raise ValueError('Conflicting cash extension source bindings')
            inputs[p] = d

    for path in (args.actions, args.inventory, args.base_events, args.calendar.parent):
        doc = verify(path)
        merge({str(path/'complete.json'): sha(path/'complete.json')})
        merge({str(path/n): d for n, d in doc['files'].items()})
        if (path/'inputs.json').exists():
            merge(json.loads((path/'inputs.json').read_text()))
    declaration = json.loads((args.inventory/'declaration.json').read_text())
    merge(declaration['inputs']); merge(declaration['sources'])
    for path in [Path(__file__), args.proposal, args.calendar, ROOT/'nn_meta/session_calendar.py',
                 *[ROOT/'nn_meta/v7'/(n+'.py') for n in ('stock_cash_extension', 'stock_cash',
                     'action_inventory', 'cash_actions', 'storage', 'runtime')]]:
        merge({str(path): sha(path)})
    proposal = json.loads(args.proposal.read_text())
    for path, digest in proposal['sources'].items():
        if sha(path) != digest:
            raise ValueError('Finite proposal source changed')
        merge({path: digest})
    values = [json.loads((path/name).read_text()) for path, name in
        [(args.actions, 'actions.json'), (args.inventory, 'candidates.json'), (args.base_events, 'events.json')]]
    calendar = SessionCalendar(json.loads(args.calendar.read_text()))
    if args.preview:
        prepared, pending = extension_candidates(*values, calendar, proposal)
        outputs = [('planned_events', prepared)]
        report = dict(preview_only=True, ready_events=len(prepared), unresolved_groups=len(pending),
            admitted_additional_entitlements=0, research_ready=False)
    else:
        policy = json.loads(args.policy.read_text())
        merge({str(args.policy): sha(args.policy)})
        if policy['proposal_path'] != str(args.proposal) or policy['proposal_sha256'] != sha(args.proposal):
            raise ValueError('Authorized extension proposal differs')
        events, pending = compile_cash_extension(*values, calendar, policy, proposal)
        outputs = [('events', events), ('policy', policy)]
        report = dict(compiled_cash_entitlements=len(events), preserved_existing_entitlements=len(values[2]),
            added_cash_entitlements=len(events)-len(values[2]), unresolved_groups=len(pending),
            broker_posting_verified=False, held_history_admitted=False, research_ready=False)
    if any(sha(p) != d for p, d in inputs.items()):
        raise ValueError('Cash extension source changed')
    with transaction(args.output) as temp:
        for name, value in [*outputs, ('inputs', inputs), ('report', report), ('unresolved', pending)]:
            (temp/(name+'.json')).write_text(json.dumps(value, indent=2)+'\n')
        receipt(temp, dict(identity=identity(inputs), preview_only=args.preview, research_ready=False))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
