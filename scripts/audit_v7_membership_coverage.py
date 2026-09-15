"""Intersect available monthly memberships with receipt-verified session counts.

This is a missing-session inventory, not a listing/identity/feature admission gate.
"""
from pathlib import Path
import argparse
import bisect
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import pandas as pd
    from nn_meta.v7.storage import verify, sha, receipt, transaction, identity
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('universe', 'calendar', 'aliases', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--audit', type=Path, action='append', required=True)
    parser.add_argument('--start', required=True)
    parser.add_argument('--end', required=True)
    args = parser.parse_args()
    calendar = json.loads(args.calendar.read_text())
    if not calendar['coverage_start'] <= args.start <= args.end <= calendar['coverage_end']:
        raise ValueError('Scope lies outside captured calendar')
    verify(args.universe)
    verify(args.aliases)
    sources = {str(p): sha(p) for p in (args.universe / 'complete.json', args.calendar,
               args.aliases / 'complete.json', Path(__file__))}
    # Recheck the transitive receipts/source bytes used by alias reconciliation.
    for p, digest in json.loads((args.aliases / 'report.json').read_text())['sources'].items():
        if sha(Path(p)) != digest:
            raise ValueError('Alias reconciliation source changed')
        sources[p] = digest
    membership = pd.read_parquet(args.universe / 'membership.parquet')
    snapshots = {}
    for available, group in membership.groupby('available_at'):
        if group.month.nunique() != 1 or group.security_id.duplicated().any() or group.ticker.duplicated().any():
            raise ValueError('Ambiguous monthly membership')
        snapshots[available] = list(group[['ticker', 'security_id']].itertuples(index=False, name=None))
    available_dates = sorted(snapshots)
    observations = {}
    symbols = set(membership.ticker)
    for audit in args.audit:
        for path in sorted((audit / 'stock').glob('*/*/complete.json')):
            if path.parents[1].name not in symbols:
                continue
            doc = verify(path.parent)
            if doc.get('kind') != 'stock':
                raise ValueError('Incorrect audit kind')
            sources[str(path)] = sha(path)
            frame = pd.read_parquet(path.parent / 'sessions.parquet')
            for row in frame.itertuples(index=False):
                key = row.symbol, row.date
                if key in observations:
                    raise ValueError('Overlapping audit sessions require explicit reconciliation')
                observations[key] = int(row.observed_minutes)
    aliases = pd.read_parquet(args.aliases / 'session_aliases.parquet')
    mapping = {}
    for row in aliases.to_dict('records'):
        key = row['membership_ticker'], row['date']
        if key in mapping:
            raise ValueError('Duplicate exact-day alias')
        mapping[key] = row
    rows, used = [], set()
    for session in calendar['sessions']:
        day = session['date']
        if not args.start <= day <= args.end:
            continue
        position = bisect.bisect_right(available_dates, day) - 1
        if position < 0:
            raise ValueError('No available membership for requested session')
        for symbol, security_id in snapshots[available_dates[position]]:
            key = symbol, day
            if key not in observations:
                raise ValueError(f'Missing captured session audit: {key}')
            count, target, status = observations[key], symbol, 'observed'
            if count == 0:
                status = 'unresolved_zero_observation'
                if key in mapping:
                    alias = mapping[key]
                    if alias['security_id'] != security_id or alias['observed_minutes'] <= 0:
                        raise ValueError('Alias security/count conflicts with current membership')
                    target, count, status = alias['stock_ticker'], alias['observed_minutes'], 'verified_session_alias'
                    used.add(key)
            rows.append({'date': day, 'membership_available_at': available_dates[position],
                         'membership_ticker': symbol, 'stock_ticker': target,
                         'security_id': security_id, 'original_observed_minutes': observations[key],
                         'observed_minutes': count, 'status': status})
    expected_aliases = {key for key in mapping if args.start <= key[1] <= args.end}
    if used != expected_aliases:
        raise ValueError('Alias mappings do not match the eligible gap inventory')
    frame = pd.DataFrame(rows)
    missing = frame[frame.observed_minutes.eq(0)]
    report = {'start': args.start, 'end': args.end, 'eligible_sessions': len(frame),
              'original_zero_sessions': int(frame.original_observed_minutes.eq(0).sum()),
              'resolved_alias_sessions': len(used), 'remaining_zero_sessions': len(missing),
              'sources': sources, 'research_ready': False,
              'limits': 'Observed minutes do not establish complete feed, listing, causal prices, or full history identity.'}
    if any(sha(Path(p)) != digest for p, digest in sources.items()):
        raise ValueError('Coverage audit source changed')
    with transaction(args.output) as temp:
        frame.to_parquet(temp / 'sessions.parquet', index=False)
        missing.to_csv(temp / 'missing-sessions.csv', index=False)
        (temp / 'stock-tickers.txt').write_text('\n'.join(sorted(set(frame.stock_ticker))) + '\n')
        (temp / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        receipt(temp, {'identity': identity(report), 'research_ready': False})
    print(json.dumps({k: v for k, v in report.items() if k != 'sources'}))


if __name__ == '__main__':
    main()
