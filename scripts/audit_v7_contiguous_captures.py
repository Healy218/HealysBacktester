#!/usr/bin/env python3
"""Count exact contiguous entry ranges without adding gaps or changing requests."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import as_completed
from itertools import groupby
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def ranges(rows):
    """Rows sorted by contract/day/start; merge only touching/overlapping ranges."""
    for (contract, day), group in groupby(rows, key=lambda r: (r[0], r[1])):
        current = None
        for _, _, start, end in group:
            if start >= end:
                raise ValueError('Invalid source interval')
            if current is None:
                current = [start, end]
            elif start <= current[1]:
                current[1] = max(current[1], end)
            else:
                yield contract, day, *current
                current = [start, end]
        if current is not None:
            yield contract, day, *current


def scan(arguments):
    path, expected = arguments
    from nn_meta.v7.storage import verify, sha
    path = Path(path)
    if sha(path / 'complete.json') != expected:
        raise ValueError('Demand receipt drift')
    verify(path)
    stats, durations = Counter(), Counter()
    previous = None
    with sqlite3.connect((path / 'demand.sqlite3').as_uri()+'?mode=ro', uri=True) as db:
        db.execute('PRAGMA query_only=ON')
        db.execute('PRAGMA cache_size=-256')
        for kind in ('quotes', 'trades'):
            rows = db.execute('SELECT contract,date,start_ns,end_ns FROM requests WHERE kind=? '
                              'ORDER BY contract,date,kind,start_ns,end_ns', (kind,))
            for contract, day, start, end in ranges(rows):
                stats[kind+'_ranges'] += 1
                stats[kind+'_duration_ns'] += end-start
                if kind == 'quotes':
                    if (contract, day) != previous:
                        stats['contract_days'] += 1
                        previous = (contract, day)
                    minutes = (end-start)/60e9
                    durations['le15m' if minutes <= 15 else 'le60m' if minutes <= 60 else 'gt60m'] += 1
    if stats['quotes_ranges'] != stats['trades_ranges'] or stats['quotes_duration_ns'] != stats['trades_duration_ns']:
        raise ValueError('Quote/trade interval census differs')
    return dict(stats=stats, durations=durations)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, required=True)
    args = parser.parse_args()
    from nn_meta.v7.runtime import configure_threads, worker_pool
    configure_threads(1)
    from nn_meta.v7.storage import verify, sha, identity, transaction, receipt
    from scripts.download_v7_data import save
    args.audit, args.output = args.audit.resolve(), args.output.resolve()
    if not args.output.is_relative_to(ROOT / 'nn_meta/validation'):
        parser.error('Use a separate validation output')
    verify(args.audit)
    parent = json.loads((args.audit / 'report.json').read_text())
    source = json.loads((args.audit / 'binding.json').read_text())
    binding = dict(parent_sha256=sha(args.audit / 'complete.json'), source_sha256=sha(__file__))
    if args.output.exists():
        verify(args.output, expected_identity=identity(binding))
        return
    demand = Path(source['demand_root']) / 'demand'
    stats, durations = Counter(), Counter()
    with worker_pool(args.workers, threads=1) as pool:
        futures = [pool.submit(scan, (str(demand / sid), parent['inputs'][str(demand / sid / 'complete.json')]))
                   for sid in source['securities']]
        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()
            stats.update(result['stats']); durations.update(result['durations'])
            if i % 50 == 0:
                print(f'Exact contiguous union {i}/{len(futures)}', flush=True)
    if (stats['quotes_duration_ns']/1e9 != parent['union_seconds_by_kind']['quotes']
            or stats['trades_duration_ns']/1e9 != parent['union_seconds_by_kind']['trades']
            or stats['contract_days'] != parent['contract_days']):
        raise ValueError('Contiguous ranges changed audited coverage')
    report = dict(schema='v7-exact-contiguous-entry-union-v1', **stats, durations=dict(durations),
                  original_fixed_cell_captures=parent['captures'],
                  contiguous_captures=stats['quotes_ranges']+stats['trades_ranges'],
                  added_coverage_seconds=0, provider_downloads=0, research_ready=False,
                  caveat='Request-count optimization only; dense ranges may need bounded pagination splitting. '
                         'No changed download/storage format has been admitted.')
    with transaction(args.output) as temporary:
        save(temporary / 'binding.json', binding)
        save(temporary / 'report.json', report)
        receipt(temporary, dict(identity=identity(binding), research_ready=False))
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
