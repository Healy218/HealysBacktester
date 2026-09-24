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
    from nn_meta.v7.cash_actions import record_key
    from nn_meta.v7.storage import identity, receipt, sha, transaction, verify
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('history', 'inventory', 'actions', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--policy', type=Path)
    parser.add_argument('--other-instruments', type=Path)
    parser.add_argument('--renames', type=Path)
    parser.add_argument('--noncash', type=Path,
                        help='Explicit 7-1 noncash boundary treatments')
    args = parser.parse_args()
    if (not args.output.resolve().is_relative_to(ROOT / 'nn_meta')
            or shutil.disk_usage(ROOT).free < 100 * 1024**3):
        raise ValueError('Repository artifact disk and 100 GiB reserve required')
    inputs = {}
    historical_source_bindings = {}

    def merge(values, *, sealed_review=False):
        for path, digest in values.items():
            if path in inputs and inputs[path] != digest:
                # The sealed September 17 relevance/rename reviews were made
                # before ordinary_actions.py changed. Their output receipts
                # bind those reviews; keep the historical implementation hash
                # explicitly, while the current action parent and executable
                # implementation retain the current source binding.
                if (sealed_review and Path(path).resolve() ==
                        (ROOT / 'nn_meta/v7/ordinary_actions.py').resolve()):
                    historical_source_bindings[path] = digest
                    continue
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
    policy, other, noncash, pending = None, [], [], json.loads((args.actions / 'unresolved.json').read_text())
    if args.policy:
        policy = json.loads(args.policy.read_text())
        merge({str(args.policy): sha(args.policy)})
    if args.other_instruments:
        doc = verify(args.other_instruments)
        merge({str(args.other_instruments / 'complete.json'): sha(args.other_instruments / 'complete.json')})
        merge({str(args.other_instruments / n): h for n, h in doc['files'].items()})
        merge(json.loads((args.other_instruments / 'inputs.json').read_text()),
              sealed_review=True)
        other = json.loads((args.other_instruments / 'treatments.json').read_text())
        pending = json.loads((args.other_instruments / 'unresolved.json').read_text())
    renames = []
    if args.renames:
        doc = verify(args.renames)
        merge({str(args.renames / 'complete.json'): sha(args.renames / 'complete.json')})
        merge({str(args.renames / n): h for n, h in doc['files'].items()})
        merge(json.loads((args.renames / 'inputs.json').read_text()),
              sealed_review=True)
        renames = json.loads((args.renames / 'events.json').read_text())
        pending = json.loads((args.renames / 'unresolved.json').read_text())
    if args.noncash:
        doc = verify(args.noncash)
        merge({str(args.noncash / 'complete.json'): sha(args.noncash / 'complete.json')})
        merge({str(args.noncash / name): digest for name, digest in doc['files'].items()})
        noncash = json.loads((args.noncash / 'treatments.json').read_text())
    # The sealed cash-action parent predates the boundary-treatment consumer;
    # retain its data files, but bind this rebuilt coverage audit to the
    # current coverage implementation below.
    for legacy in ('nn_meta/v7/action_coverage.py', 'nn_meta/v7/portfolio.py'):
        inputs.pop(legacy, None)
        inputs.pop(str(ROOT / legacy), None)
    for path in [Path(__file__), *[ROOT / 'nn_meta/v7' / (n + '.py') for n in
            ('action_coverage', 'renames', 'cash_actions', 'ordinary_actions', 'causal_prices', 'storage', 'runtime')]]:
        merge({str(path): sha(path)})
    # Treatment artifacts can share ancestors. Compute the remaining original
    # records from their explicit references, independent of artifact order.
    # coverage_panel below checks missing, overlapping and altered references.
    candidates = json.loads((args.inventory / 'candidates.json').read_text())
    candidate_by_key = {record_key(r): r for r in candidates}
    resolved = {record_key(r) for t in [*other, *renames, *noncash] for r in t['replaces']}
    pending = [r for r in json.loads((args.actions / 'unresolved.json').read_text())
               if record_key(r) not in resolved]
    # A finalized action parent can contain a reconstruction whose effective
    # session is no longer usable in the selected identity history. Demote that
    # event to its exact original records instead of binding it to a missing or
    # mismatched security/date row.
    history = pd.read_parquet(args.history / 'history.parquet')
    facts = history.set_index(['security_id', 'source_date'])
    valid_events, demoted = [], []
    for event in json.loads((args.actions / 'actions.json').read_text()):
        action = event['action']
        day = pd.Timestamp(action['effective_at']).tz_convert('America/New_York').date().isoformat()
        key = (event['security_id'], day)
        if (key in facts.index and pd.notna(facts.loc[key].stock_ticker)
                and facts.loc[key].stock_ticker == event['symbol']):
            valid_events.append(event)
        else:
            demoted.extend(candidate_by_key[record_key(r)] for r in event['replaces'])
    pending.extend(demoted)
    pending.extend(candidate_by_key[key] for key in set(candidate_by_key) -
                   (set(record_key(r) for r in pending) |
                    {record_key(r) for event in valid_events for r in event['replaces']} |
                    {record_key(r) for t in [*other, *renames, *noncash] for r in t['replaces']}))
    pending = list({record_key(r): r for r in pending}.values())
    if any(sha(p) != h for p, h in inputs.items()):
        raise ValueError('Action coverage source changed')
    panel = coverage_panel(history, candidates, valid_events,
        pending, policy=policy, other_instruments=other, renames=renames, noncash=noncash)
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
        if historical_source_bindings:
            report['historical_source_bindings'] = historical_source_bindings
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
