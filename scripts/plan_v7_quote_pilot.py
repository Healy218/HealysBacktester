"""Outcome-independent quote superset for every minute selector in a bounded pilot.

Captures all five target choices and both rights before inspecting strategy
outcomes. Retained contracts remain covered through expiry or pilot end.
"""
from pathlib import Path
import argparse
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import pandas as pd
    import polars as pl
    from nn_meta.v7.bars import aggregate_lazy
    from nn_meta.v7.chain import ObservedChain
    from nn_meta.v7.coverage import receipt_frame
    from nn_meta.v7.storage import transaction, receipt, identity, verify, sha
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'calendar', 'chain', 'output'):
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--symbol', required=True)
    ap.add_argument('--start', required=True)
    ap.add_argument('--end', required=True)
    ap.add_argument('--close-extension-minutes', type=int, required=True,
                    help='Explicit provisional option-class session policy, 0 or 15')
    args = ap.parse_args()
    from nn_meta.v7.scope import require_active_inputs, require_research_window
    require_active_inputs(args.source)
    require_research_window(args.start, args.end)
    if args.close_extension_minutes not in (0, 15):
        raise ValueError('Explicit supported option session policy required')
    calendar = json.loads(args.calendar.read_text())
    verify(args.chain.parent)
    chain = ObservedChain(args.chain, args.symbol)
    paths, sources = [], {}
    for year in range(int(args.start[:4]), int(args.end[:4]) + 1):
        path = args.source / 'stock_1m/raw' / args.symbol / str(year) / 'complete.json'
        doc, frame = receipt_frame(args.source, path)
        del frame
        sources[str(path)] = sha(path)
        paths.extend(path.parent / p for p in doc['files'] if p.endswith('bars.parquet'))
    begin = pd.Timestamp(args.start, tz='America/New_York')
    end = pd.Timestamp(args.end, tz='America/New_York') + pd.DateOffset(days=1)
    raw = aggregate_lazy(paths, calendar, 1).filter((pl.col('timestamp').cast(pl.Int64) >= begin.value) &
              (pl.col('timestamp').cast(pl.Int64) < end.value)).collect(engine='streaming').to_pandas()
    selections, held, rejected = [], {}, 0
    for row in raw.itertuples():
        decision = row.available_at
        day = decision.tz_convert('America/New_York').date()
        for right in ('C', 'P'):
            for target in (1, 2, 4, 5, 7):
                selected = chain.select(day, row.Close, right, target)
                if selected is None:
                    rejected += 1
                    continue
                contract = selected['ticker'].removeprefix('O:')
                selections.append({'decision_ns': decision.value, 'right': right, 'target_dte': target,
                                   'contract': contract, 'raw_spot': row.Close,
                                   'chain_first_seen': selected['first_seen'].isoformat()})
                held.setdefault(contract, {'start': day.isoformat(), 'expiry': selected['expiry'].isoformat()})
    requests, references = [], []
    for contract, dates in sorted(held.items()):
        for session in calendar['sessions']:
            day = session['date']
            if not dates['start'] <= day <= min(dates['expiry'], args.end):
                continue
            opening = pd.Timestamp(day + ' ' + session['open'], tz='America/New_York')
            closing = pd.Timestamp(day + ' ' + session['close'], tz='America/New_York')
            closing += pd.Timedelta(minutes=args.close_extension_minutes)
            references.append({'contract': contract, 'date': day})
            for kind in ('quotes', 'trades'):
                request = {'contract': contract, 'kind': kind,
                           'start_ns': opening.value, 'end_ns': closing.value}
                requests.append({'request_id': identity(request), **request})
    with transaction(args.output) as temp:
        pd.DataFrame(selections).to_parquet(temp / 'selections.parquet', index=False)
        (temp / 'requests.json').write_text(json.dumps(requests, indent=2) + '\n')
        (temp / 'contracts.json').write_text(json.dumps(references, indent=2) + '\n')
        report = {'contracts': len(held), 'contract_days': len(references), 'requests': len(requests),
                  'selector_events': len(selections), 'no_eligible_contract': rejected,
                  'close_extension_minutes': args.close_extension_minutes, 'research_ready': False,
                  'scope': 'complete pilot selector superset; not full-universe coverage',
                  'weekly_eligibility_verified': False, 'dated_session_policy_verified': False}
        (temp / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        receipt(temp, {'identity': identity({'raw': sources, 'calendar': sha(args.calendar),
                    'chain': sha(args.chain), 'code': sha(__file__), 'scope': [args.start, args.end]}),
                    'research_ready': False})
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
