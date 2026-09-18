"""Resolve finite erroneous, canceled, alias and noncash dividend records."""
from pathlib import Path
import argparse
import json
import shutil
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import pandas as pd
    from nn_meta.session_calendar import SessionCalendar
    from nn_meta.v7.dividend_producer_versions import historical_input_bindings
    from nn_meta.v7.dividend_dispositions import reviewed_dispositions, coverage_with_dispositions
    from nn_meta.v7.dividend_components import validate_components
    from nn_meta.v7.dividend_closure import dividend_census
    from nn_meta.v7.cash_actions import record_key
    from nn_meta.v7.ordinary_actions import price_action
    from nn_meta.v7.causal_daily import returns
    from nn_meta.v7.portfolio import portfolio_replay
    from nn_meta.v7.physical import PhysicalPolicy
    from nn_meta.v7.settlement_schedule import ReportedSettlementSchedule
    from nn_meta.v7.storage import identity, sha, verify, receipt, transaction
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('inventory', 'actions', 'base-cash', 'history', 'calendar', 'settlement',
                 'other-instruments', 'renames', 'reviews', 'policy', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT/'nn_meta') or shutil.disk_usage(ROOT).free < 100*1024**3:
        raise ValueError('Repository artifact disk and reserve required')
    inputs = {}

    def merge(values):
        for p, d in historical_input_bindings(values).items():
            if p in inputs and inputs[p] != d:
                raise ValueError('Conflicting dividend source versions')
            inputs[p] = d

    def bind(path):
        doc = verify(path)
        merge({str(path/'complete.json'): sha(path/'complete.json')})
        merge({str(path/n): d for n, d in doc['files'].items()})
        if (path/'inputs.json').exists(): merge(json.loads((path/'inputs.json').read_text()))
        return doc

    for path in (args.inventory, args.actions, args.base_cash, args.history,
                 args.calendar.parent, args.settlement.parent, args.other_instruments, args.renames):
        bind(path)
    declaration = json.loads((args.inventory/'declaration.json').read_text())
    merge(declaration['inputs']); merge(declaration['sources'])
    policy = json.loads(args.policy.read_text()); proposal_path = Path(policy['proposal_path'])
    if sha(proposal_path) != policy['proposal_sha256']:
        raise ValueError('Original finite proposal changed')
    proposal = json.loads(proposal_path.read_text())
    merge(proposal['sources'])
    for path in [Path(__file__), args.policy, args.reviews, proposal_path,
                 ROOT/'nn_meta/session_calendar.py', *[ROOT/'nn_meta/v7'/(n+'.py') for n in
                 ('dividend_producer_versions', 'dividend_resolution', 'dividend_dispositions', 'action_coverage', 'dividend_components',
                  'dividend_closure', 'ordinary_actions', 'cash_actions', 'action_inventory',
                  'causal_prices', 'causal_daily', 'stock_cash', 'cash_date_exceptions',
                  'physical', 'portfolio', 'stock_splits', 'stock_quotes', 'execution',
                  'settlement_schedule', 'storage', 'runtime')]]:
        merge({str(path): sha(path)})
    document = json.loads(args.reviews.read_text())
    if document['schema'] != 'v7-dividend-disposition-reviews-v1':
        raise ValueError('Finite primary review document required')
    for review in document['reviews']:
        for e in review['evidence']:
            path = Path(e['capture']); doc = bind(path)
            if sha(path/'complete.json') != e['receipt_sha256'] or doc['files'].get('response.bin') != e['payload_sha256']:
                raise ValueError('Retained primary terms source changed')

    def read(path, name): return json.loads((path/(name+'.json')).read_text())

    originals = read(args.inventory, 'candidates')
    base_actions = read(args.actions, 'actions'); base_cash = read(args.base_cash, 'events')
    history = pd.read_parquet(args.history/'history.parquet')
    calendar = SessionCalendar(json.loads(args.calendar.read_text()))
    schedule = ReportedSettlementSchedule(json.loads(args.settlement.read_text()), calendar)
    actions = base_actions; events = base_cash
    grouped = validate_components(actions, events, calendar, schedule)
    other = read(args.other_instruments, 'treatments'); renames = read(args.renames, 'events')
    treatments, pending = reviewed_dispositions(originals, read(args.actions, 'unresolved'),
        document['reviews'], actions, events, renames)
    prior_dispositions = [t for t in other if t.get('schema') == 'v7-reviewed-dividend-disposition-v1']
    legacy_other = [t for t in other if t not in prior_dispositions]
    dispositions = prior_dispositions + treatments
    other = legacy_other + dispositions
    # The historical census counts one representative per price event; grouped
    # validation above separately proves every payment is present exactly once.
    census, uncompiled, missing = dividend_census(originals, actions, other, renames,
        [v[0] for v in grouped.values()], pending)
    coverage_policy_path = ROOT/'docs/specs/V7_NO_EVENT_ADMISSION_20260917.json'
    merge({str(coverage_policy_path):sha(coverage_policy_path)})
    coverage = coverage_with_dispositions(history, originals, actions, pending, dispositions,
        policy=json.loads(coverage_policy_path.read_text()), other=legacy_other, renames=renames, cash=events)
    context = SimpleNamespace(settlement_calendar=schedule, policy=PhysicalPolicy(), stock_archive=None,
        cash_entitlements=events)
    clocks = sorted({e[k] for e in events for k in ('effective_ns', 'release_ns')})
    empty = portfolio_replay([], clocks, None, physical=context)
    if not empty['complete'] or empty['cash'] != 100000. or len(empty['fills']) != len(events) or any(e['receivable'] for e in empty['fills']):
        raise ValueError('Portfolio created cash without beneficial holdings')
    report = dict(census, new_dispositions=len(treatments), added_price_events=0, added_cash_payments=0,
        total_cash_payments=len(events), admitted_history_sessions=int(coverage.history_admitted.sum()),
        no_inventory_portfolio_cash=empty['cash'], settlement_coverage=[schedule.document['coverage_start'],schedule.document['coverage_end']])
    if any(sha(p) != d for p,d in inputs.items()): raise ValueError('Dividend input bytes changed')
    with transaction(args.output) as temp:
        for name, value in [('inputs',inputs),('actions',actions),('events',events),('unresolved',pending),
                ('report',report),('uncompiled',uncompiled),('missing_held',missing),('policy',policy),
                ('reviews',document),('treatments',other),('dispositions',dispositions),('no_inventory_portfolio',empty)]:
            (temp/(name+'.json')).write_text(json.dumps(value,indent=2)+'\n')
        coverage.to_parquet(temp/'coverage.parquet',index=False)
        receipt(temp,dict(identity=identity(inputs),research_ready=False))
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
