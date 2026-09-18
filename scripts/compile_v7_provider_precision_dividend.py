"""Compile finite primary terms, verify price/cash consumers, and seal their census."""
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
    from nn_meta.v7.dividend_provider_precision import compile_provider_precision
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
                 'other-instruments', 'renames', 'reviews', 'policy', 'precision-policy', 'output'):
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
    for path in [Path(__file__), args.policy, args.precision_policy, args.reviews, proposal_path,
                 ROOT/'nn_meta/session_calendar.py', *[ROOT/'nn_meta/v7'/(n+'.py') for n in
                 ('dividend_producer_versions', 'dividend_resolution', 'dividend_provider_precision', 'dividend_components',
                  'dividend_closure', 'ordinary_actions', 'cash_actions', 'action_inventory',
                  'causal_prices', 'causal_daily', 'stock_cash', 'cash_date_exceptions',
                  'physical', 'portfolio', 'stock_splits', 'stock_quotes', 'execution',
                  'settlement_schedule', 'storage', 'runtime')]]:
        merge({str(path): sha(path)})
    document = json.loads(args.reviews.read_text())
    if document['schema'] != 'v7-primary-dividend-resolutions-v1':
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
    added, leaves, _ = compile_provider_precision(originals, document['reviews'], history,
        calendar, policy, proposal, json.loads(args.precision_policy.read_text()))
    existing = {record_key(r) for a in base_actions for r in a['replaces']}
    used = {record_key(r) for a in added for r in a['replaces']}
    if existing & used: raise ValueError('Cannot replace existing admitted price actions')
    actions = base_actions + added; events = base_cash + leaves
    grouped = validate_components(actions, events, calendar, schedule)
    other = read(args.other_instruments, 'treatments'); renames = read(args.renames, 'events')
    resolved_other = {record_key(r) for a in [*other, *renames] for r in a['replaces']}
    pending = [r for r in read(args.actions, 'unresolved') if record_key(r) not in used | resolved_other]
    # The historical census counts one representative per price event; grouped
    # validation above separately proves every payment is present exactly once.
    census, uncompiled, missing = dividend_census(originals, actions, other, renames,
        [v[0] for v in grouped.values()], pending)
    boundary_checks = []
    for event in added:
        boundary = history[history.security_id.eq(event['security_id']) &
            history.source_date.between(event['prior_source_date'], event['effective_date'])].copy()
        boundary['observed_minutes'] = boundary.observed_minutes.astype('int64')
        result = returns(boundary, [price_action(event)], calendar, security_id=event['security_id'],
            start=event['prior_source_date'], end=event['effective_date'], action_evidence_identity=identity(event))
        if len(result) != 2 or not pd.notna(result.simple_return.iloc[-1]):
            raise ValueError('Real dividend feature boundary did not resolve')
        boundary_checks.append(dict(event_id=event['action']['event_id'], simple_return=float(result.simple_return.iloc[-1])))
    context = SimpleNamespace(settlement_calendar=schedule, policy=PhysicalPolicy(), stock_archive=None,
        cash_entitlements=events)
    clocks = sorted({e[k] for e in events for k in ('effective_ns', 'release_ns')})
    empty = portfolio_replay([], clocks, None, physical=context)
    if not empty['complete'] or empty['cash'] != 100000. or len(empty['fills']) != len(events) or any(e['receivable'] for e in empty['fills']):
        raise ValueError('Portfolio created cash without beneficial holdings')
    report = dict(census, added_price_events=len(added), added_cash_payments=len(leaves),
        total_cash_payments=len(events), primary_feature_boundaries=len(boundary_checks),
        no_inventory_portfolio_cash=empty['cash'], settlement_coverage=[schedule.document['coverage_start'],schedule.document['coverage_end']])
    if any(sha(p) != d for p,d in inputs.items()): raise ValueError('Dividend input bytes changed')
    with transaction(args.output) as temp:
        for name, value in [('inputs',inputs),('actions',actions),('events',events),('unresolved',pending),
                ('report',report),('uncompiled',uncompiled),('missing_held',missing),('policy',policy),
                ('reviews',document),('feature_boundaries',boundary_checks),('no_inventory_portfolio',empty)]:
            (temp/(name+'.json')).write_text(json.dumps(value,indent=2)+'\n')
        receipt(temp,dict(identity=identity(inputs),research_ready=False))
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
