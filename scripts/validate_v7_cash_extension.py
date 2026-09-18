"""Verify a finite admitted cash extension against sources and actual consumers."""
from pathlib import Path
import argparse
from decimal import Decimal
import json
import shutil
import sys
from types import SimpleNamespace
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    from nn_meta.session_calendar import SessionCalendar
    from nn_meta.v7.physical import PhysicalPolicy
    from nn_meta.v7.portfolio import portfolio_replay
    from nn_meta.v7.settlement_schedule import ReportedSettlementSchedule
    from nn_meta.v7.stock_cash import validate_cash_event
    from nn_meta.v7.storage import identity, receipt, sha, transaction, verify
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('events', 'base-events', 'base-verification', 'actions', 'calendar', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT/'nn_meta') or shutil.disk_usage(ROOT).free < 100*1024**3:
        raise ValueError('Repository artifact disk and reserve required')
    inputs = {}

    def merge(values):
        for p, d in values.items():
            if p in inputs and inputs[p] != d:
                raise ValueError('Conflicting extension verification sources')
            inputs[p] = d

    for path in (args.events, args.base_events, args.base_verification, args.actions):
        doc = verify(path)
        merge({str(path/'complete.json'): sha(path/'complete.json')})
        merge({str(path/n): d for n, d in doc['files'].items()})
        merge(json.loads((path/'inputs.json').read_text()))
    for path in [Path(__file__), args.calendar, ROOT/'nn_meta/session_calendar.py',
                 *[ROOT/'nn_meta/v7'/(n+'.py') for n in ('physical', 'portfolio', 'execution',
                     'stock_cash', 'stock_cash_extension', 'stock_splits', 'stock_quotes',
                     'settlement_schedule', 'storage', 'runtime')]]:
        merge({str(path): sha(path)})
    events = json.loads((args.events/'events.json').read_text())
    base = json.loads((args.base_events/'events.json').read_text())
    if events[:len(base)] != base:
        raise ValueError('Existing authorized cash entitlements must be byte-equivalent objects')
    policy = json.loads((args.events/'policy.json').read_text())
    proposal = json.loads(Path(policy['proposal_path']).read_text())
    if (policy['status'] != 'user_authorized' or policy['proposal_identity'] != identity(proposal)
            or sha(policy['proposal_path']) != policy['proposal_sha256']):
        raise ValueError('Exact authorized extension required')
    original = {e['action']['event_id']: e for e in json.loads((args.actions/'actions.json').read_text())}
    trading = SessionCalendar(json.loads(args.calendar.read_text()))
    schedule = ReportedSettlementSchedule(json.loads((args.base_verification/'settlement_calendar.json').read_text()), trading)
    additional = events[len(base):]
    for e in events:
        validate_cash_event(e, trading, settlement_calendar=schedule)
        source = original[e['compiled_event_id']]
        if (e['source_identity'] != identity(source) or e['replaces'] != source['replaces']
                or Decimal(e['cash_per_share']) != Decimal(source['cash_amount'])
                or e['event_id'] != 'stock-cash:'+identity({k: v for k, v in e.items() if k != 'event_id'})):
            raise ValueError('Cash event differs from its actual compiled source')
    if any(e['policy_identity'] != identity(policy) for e in additional):
        raise ValueError('Additional cash events must bind the extension authorization')
    context = SimpleNamespace(settlement_calendar=schedule, policy=PhysicalPolicy(), stock_archive=None,
        cash_entitlements=events)
    clocks = sorted({e[k] for e in events for k in ('effective_ns', 'release_ns')})
    empty = portfolio_replay([], clocks, None, physical=context)
    if (not empty['complete'] or empty['cash'] != 100000. or len(empty['fills']) != len(events)
            or any(e['receivable'] for e in empty['fills'])):
        raise ValueError('Portfolio consumer created cash without beneficial stock holdings')
    inherited = json.loads((args.base_verification/'report.json').read_text())
    if inherited['verified_cash_events'] != len(base) or 'captured_funded_case' not in inherited:
        raise ValueError('Existing funded cash case and complete original census required')
    report = dict(verified_cash_events=len(events), verified_additional_cash_events=len(additional),
        preserved_existing_cash_events=len(base), no_inventory_portfolio_events=len(events),
        no_inventory_portfolio_cash=empty['cash'],
        funded_case_evidence=str(args.base_verification/'report.json'),
        settlement_coverage=[schedule.document['coverage_start'], schedule.document['coverage_end']],
        held_history_admitted=False, research_ready=False, broker_posting_verified=False)
    if any(sha(p) != d for p, d in inputs.items()):
        raise ValueError('Extension verification sources changed')
    with transaction(args.output) as temp:
        for name, value in [('inputs', inputs), ('report', report), ('no_inventory_portfolio', empty)]:
            (temp/(name+'.json')).write_text(json.dumps(value, indent=2)+'\n')
        receipt(temp, dict(identity=identity(inputs), research_ready=False))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
