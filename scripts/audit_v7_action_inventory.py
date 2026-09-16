"""Reconcile every captured action affecting active V7 source symbols.

Produces an immutable full-scope review queue, not admitted adjustment factors.
Original records and exact provider/date/role provenance are retained.
"""
from pathlib import Path
import argparse
from collections import Counter, defaultdict
import gzip
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import pandas as pd
    from nn_meta.v7.action_inventory import candidate, reconcile
    from nn_meta.v7.scope import HISTORY_START, HISTORY_END
    from nn_meta.v7.storage import identity, receipt, sha, transaction, verify
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('stock-daily', 'dividends', 'splits', 'alpaca', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT / 'nn_meta'):
        raise ValueError('Repository artifact disk required')
    summary = args.stock_daily / 'summary'
    parent = json.loads((summary / 'binding.json').read_text())
    verify(summary, expected_identity=identity(parent))
    inputs = {**parent['declaration']['inputs'], **parent['declaration']['sources']}
    inputs.update({str(summary / name): sha(summary / name) for name in ('complete.json', 'eligible_daily.parquet')})
    code = {str(p): sha(p) for p in (Path(__file__), ROOT / 'nn_meta/v7/action_inventory.py',
        ROOT / 'nn_meta/v7/storage.py', ROOT / 'nn_meta/v7/runtime.py', ROOT / 'nn_meta/v7/scope.py')}
    stock = pd.read_parquet(summary / 'eligible_daily.parquet',
        columns=['stock_ticker', 'membership_ticker', 'security_id', 'date'])
    scoped_symbols = set(stock.stock_ticker) | set(stock.membership_ticker)
    eligible = defaultdict(set)
    for row in stock.itertuples(index=False):
        for symbol in {row.stock_ticker, row.membership_ticker}:
            eligible[(symbol, row.date)].add(row.security_id)
    rows, capture_counts = [], {}
    for provider, kind, root in [('massive', 'dividends', args.dividends),
                                  ('massive', 'splits', args.splits), ('alpaca', None, args.alpaca)]:
        document = verify(root)
        query = document['query']
        if provider == 'massive':
            date_key = 'ex_dividend_date' if kind == 'dividends' else 'execution_date'
            if (query['path'] != '/stocks/v1/' + kind
                    or query['params'][date_key + '.gte'] > HISTORY_START
                    or query['params'][date_key + '.lte'] < HISTORY_END):
                raise ValueError('Full dated Massive action query required')
        elif (query['endpoint'] != 'https://data.alpaca.markets/v1/corporate-actions'
                or query['params']['start'] > HISTORY_START or query['params']['end'] < HISTORY_END
                or query['params'].get('data_quality') != 'all' or query['params'].get('region') != 'us'):
            raise ValueError('Full Alpaca process-date/all-quality capture required')
        inputs[str(root / 'complete.json')] = sha(root / 'complete.json')
        inputs.update({str(root / name): digest for name, digest in document['files'].items()})
        counts = Counter()
        for path in sorted(root.glob('*.gz')):
            page = json.loads(gzip.decompress(path.read_bytes()))
            categories = {kind: page['results']} if provider == 'massive' else page['corporate_actions']
            for category, records in categories.items():
                counts[category] += len(records)
                for record in records:
                    row = candidate(provider, category, record, scoped_symbols=scoped_symbols,
                        start=HISTORY_START, end=HISTORY_END,
                        source=dict(receipt=str(root / 'complete.json'), payload=str(path),
                                    payload_sha256=document['files'][path.name]))
                    if row is not None:
                        rows.append(row)
        expected = {kind: document['records']} if provider == 'massive' else document['counts']
        if dict(counts) != expected:
            raise ValueError('Original provider capture counts differ')
        capture_counts[provider + ':' + str(kind)] = dict(counts)
    reconciled = reconcile(rows, eligible)
    declaration = dict(schema='v7-full-action-review-inventory-v1', start=HISTORY_START, end=HISTORY_END,
        source_symbols=sorted(scoped_symbols), inputs=inputs, sources=code,
        scope='All source-symbol events in full history, including outside eligible sessions; no inferred identity',
        effective_date_policy='Explicit ex/execution/effective only; process-only records remain undated',
        alpaca_limit='Captured request is process-date bounded; absence is not no-event proof',
        research_ready=False)
    report = dict(source_symbols=len(scoped_symbols), security_ids=int(stock.security_id.nunique()),
        eligible_sessions=len(stock), candidate_records=len(rows), reconciled_groups=len(reconciled),
        candidate_kinds=dict(Counter(r['provider'] + ':' + r['kind'] for r in rows)),
        statuses=dict(Counter(r['status'] for r in reconciled)),
        eligible_identity_groups=sum(r['eligible_security_id'] is not None for r in reconciled),
        complex_records=sum(r['category'] == 'complex' for r in rows),
        missing_effective_dates=sum(r['effective_date'] is None for r in rows),
        combined_event_groups=sum(r['combined_event_day'] for r in reconciled),
        capture_counts=capture_counts, publication_verified=False, research_ready=False)
    if any(sha(path) != digest for path, digest in {**inputs, **code}.items()):
        raise ValueError('Action evidence changed during reconciliation')
    with transaction(args.output) as temporary:
        for name, value in [('declaration', declaration), ('report', report),
                            ('candidates', rows), ('reconciliation', reconciled)]:
            (temporary / (name + '.json')).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
        receipt(temporary, dict(identity=identity(declaration), research_ready=False))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
