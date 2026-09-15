"""Prove exact-day rename coverage by unchanged security identity and observed bars.

This produces session-specific routing evidence, never a global ticker alias.
Action process dates alone cannot establish a trading-effective boundary.
"""
from pathlib import Path
import argparse
import gzip
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import pandas as pd
    from nn_meta.v7.coverage import receipt_frame
    from nn_meta.v7.storage import transaction, receipt, verify, identity, sha
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('candidates', 'universe', 'actions', 'references', 'calendar', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--stock-source', type=Path, action='append', required=True)
    args = parser.parse_args()
    verify(args.universe)
    verify(args.actions)
    members = pd.read_parquet(args.universe / 'membership.parquet')
    calendar = {s['date']: s for s in json.loads(args.calendar.read_text())['sessions']}
    sources = {str(p): sha(p) for p in
               (args.candidates, args.universe / 'complete.json', args.actions / 'complete.json',
                args.calendar, Path(__file__), ROOT / 'nn_meta/v7/coverage.py')}
    actions = {}
    for path in sorted(args.actions.glob('page-*.json.gz')):
        for row in json.loads(gzip.decompress(path.read_bytes()))['corporate_actions'].get('name_changes', []):
            if row['id'] in actions and actions[row['id']] != row:
                raise ValueError('Conflicting action identity')
            actions[row['id']] = row
    result, seen, frames = [], set(), {}
    for candidate in json.loads(args.candidates.read_text()):
        symbol, day, target = candidate['symbol'], candidate['date'], candidate['new_symbol']
        if (symbol, day) in seen or day not in calendar:
            raise ValueError('Duplicate gap or missing calendar day')
        seen.add((symbol, day))
        action = actions[candidate['action_id']]
        if (action['old_symbol'] != symbol or action['new_symbol'] != target
                or action['process_date'] != candidate['process_date']
                or not action['process_date'] <= day):
            raise ValueError('Candidate differs from captured action')
        prior = members[members.available_at.le(day)]
        active = prior[prior.month.eq(prior.month.max()) & prior.ticker.eq(symbol)]
        if len(active) != 1:
            raise ValueError('One currently eligible source security required')
        security_id = active.iloc[0].security_id
        response = args.references / target / day
        doc = verify(response)
        sources[str(response / 'complete.json')] = sha(response / 'complete.json')
        if doc['query'] != {'path': f'/v3/reference/tickers/{target}', 'params': {'date': day}}:
            raise ValueError('Reference date or symbol mismatch')
        record = json.loads((response / 'response.json').read_text()).get('results', {})
        if (doc['http_status'] != 200 or record.get('ticker') != target
                or record.get('composite_figi') != security_id):
            raise ValueError('Exact-day target is not the eligible security')
        paths = [root / f'stock_1m/raw/{target}/{day[:4]}/complete.json'
                 for root in args.stock_source]
        paths = [p for p in paths if p.exists()]
        if len(paths) != 1:
            raise ValueError(f'Exactly one raw source required for {target}/{day[:4]}')
        path = paths[0]
        if path not in frames:
            raw_doc, frame = receipt_frame(path.parents[4], path)
            if raw_doc['task']['symbol'] != target or raw_doc['task']['adjustment'] != 'raw':
                raise ValueError('Incorrect stock capture task')
            frames[path] = pd.DatetimeIndex(frame.timestamp)
            sources[str(path)] = sha(path)
        opening = pd.Timestamp(day + ' ' + calendar[day]['open'], tz='America/New_York')
        closing = pd.Timestamp(day + ' ' + calendar[day]['close'], tz='America/New_York')
        stamps = frames[path]
        observed = int(stamps.searchsorted(closing) - stamps.searchsorted(opening))
        if observed == 0:
            raise ValueError('Renamed ticker also lacks regular-session observations')
        result.append({'membership_ticker': symbol, 'date': day, 'stock_ticker': target,
                       'security_id': security_id, 'observed_minutes': observed,
                       'action_id': action['id'], 'stock_receipt': str(path),
                       'identity_receipt': str(response / 'complete.json')})
    if any(sha(Path(p)) != digest for p, digest in sources.items()):
        raise ValueError('Reconciliation inputs changed during the run')
    with transaction(args.output) as temp:
        pd.DataFrame(result).to_parquet(temp / 'session_aliases.parquet', index=False)
        (temp / 'report.json').write_text(json.dumps({'resolved_sessions': len(result),
            'sources': sources, 'research_ready': False,
            'scope': 'listed exact-day gaps only; no global alias or all-history continuity claim'}, indent=2) + '\n')
        receipt(temp, {'identity': identity(sources), 'research_ready': False})
    print(json.dumps({'resolved_sessions': len(result), 'research_ready': False}))


if __name__ == '__main__':
    main()
