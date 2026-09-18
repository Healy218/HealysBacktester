"""Compile reviewed cash dates, retaining exact prior producer versions."""
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
    from nn_meta.v7.stock_cash_dates import compile_date_reviewed_cash
    from nn_meta.v7.producer_versions import historical_input_bindings, SNAPSHOTS
    from nn_meta.v7.cash_date_exceptions import NASDAQ_NOTICE_SHA
    from nn_meta.v7.storage import identity, sha, verify, transaction, receipt
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('actions', 'inventory', 'base-events', 'calendar', 'reviews', 'policy', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT/'nn_meta') or shutil.disk_usage(ROOT).free < 100*1024**3:
        raise ValueError('Repository artifact disk and reserve required')
    inputs = {}

    def merge(values):
        for p, d in historical_input_bindings(values).items():
            if p in inputs and inputs[p] != d:
                raise ValueError('Conflicting cash-date source bindings')
            inputs[p] = d

    def bind(path):
        doc = verify(path)
        merge({str(path/'complete.json'): sha(path/'complete.json')})
        merge({str(path/n): d for n, d in doc['files'].items()})
        return doc

    for path in (args.actions, args.inventory, args.base_events, args.calendar.parent):
        bind(path)
        if (path/'inputs.json').exists(): merge(json.loads((path/'inputs.json').read_text()))
    declaration = json.loads((args.inventory/'declaration.json').read_text())
    merge(declaration['inputs']); merge(declaration['sources'])
    policy = json.loads(args.policy.read_text()); proposal_path = Path(policy['proposal_path'])
    if sha(proposal_path) != policy['proposal_sha256']:
        raise ValueError('Authorized finite proposal changed')
    proposal = json.loads(proposal_path.read_text())
    for p, d in proposal['sources'].items():
        if sha(p) != d: raise ValueError('Approved proposal evidence changed')
        merge({p: d})
    for path in [Path(__file__), args.reviews, args.policy, proposal_path, args.calendar,
                 ROOT/'nn_meta/session_calendar.py', *[ROOT/'nn_meta/v7'/(n+'.py') for n in
                 ('stock_cash_dates', 'stock_cash', 'cash_date_exceptions', 'producer_versions', 'ordinary_actions', 'causal_prices',
                  'action_inventory', 'cash_actions', 'storage', 'runtime')]]:
        merge({str(path): sha(path)})
    document = json.loads(args.reviews.read_text())
    if document['schema'] != 'v7-finite-primary-cash-date-reviews-v1':
        raise ValueError('Exact finite primary date reviews required')
    reviews = []
    for original in document['reviews']:
        review = dict(original); evidence = review.pop('evidence')
        if not evidence: raise ValueError('Primary date source required')
        for e in evidence:
            path = Path(e['capture']); doc = bind(path)
            if (sha(path/'complete.json') != e['receipt_sha256']
                    or doc['files'].get('response.bin') != e['payload_sha256'] or not e['review']):
                raise ValueError('Retained primary date source changed')
        if review.get('record_date_exception') is not None and not any(
                e['payload_sha256'] == NASDAQ_NOTICE_SHA for e in evidence):
            raise ValueError('Original Nasdaq exception notice required alongside issuer date evidence')
        review['evidence_identity'] = identity(evidence); reviews.append(review)
    actions = json.loads((args.actions/'actions.json').read_text())
    originals = json.loads((args.inventory/'candidates.json').read_text())
    base = json.loads((args.base_events/'events.json').read_text())
    events = compile_date_reviewed_cash(actions, originals, base,
        SessionCalendar(json.loads(args.calendar.read_text())), policy, proposal, reviews)
    scope = {(r['symbol'], r['ex_date']) for r in proposal['eligible_groups']}
    done = {(e['symbol'], e['ex_date']) for e in events} & scope
    report = dict(compiled_cash_entitlements=len(events), preserved_existing_entitlements=len(base),
        added_date_reviewed_entitlements=len(events)-len(base), unresolved_extension_groups=len(scope-done),
        price_actions_changed=0, held_history_admitted=False, research_ready=False,
        retained_producer_snapshots=[dict(original=p, sha256=d, snapshot=a)
            for (p,d),a in SNAPSHOTS.items()])
    if any(sha(p) != d for p, d in inputs.items()): raise ValueError('Cash-date inputs changed')
    with transaction(args.output) as temp:
        for name, value in [('inputs', inputs), ('report', report), ('events', events),
                            ('policy', policy), ('reviews', document)]:
            (temp/(name+'.json')).write_text(json.dumps(value, indent=2)+'\n')
        receipt(temp, dict(identity=identity(inputs), research_ready=False))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
