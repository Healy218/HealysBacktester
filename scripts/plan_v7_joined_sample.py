#!/usr/bin/env python3
"""Predeclare a bounded, outcome-blind storage sample of the sealed entry union.

Strata: calendar year, security request-count quartile, joined-range duration.
Select the lowest seeded SHA256 priorities, uniformly over paired windows under
the hash-randomization assumption. Selection never reads provider tick results.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import as_completed
from datetime import datetime, timezone
import heapq
from itertools import groupby
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SEED = 'v7-joined-volume-20260926-v1'


def keep(heap, sample, maximum):
    entry = (-int(sample['priority'], 16), sample['pair_id'], sample)
    if len(heap) < maximum:
        heapq.heappush(heap, entry)
    elif entry > heap[0]:
        heapq.heapreplace(heap, entry)


def summarize(rows, *, security_id, quartile, maximum):
    from nn_meta.v7.quotes import capture_union
    from nn_meta.v7.storage import identity
    counts, seconds, heaps = Counter(), Counter(), {}
    requests = days = 0
    for (contract, day), records in groupby(rows, key=lambda r: (r[1], r[2])):
        group = {}
        for rid, symbol, date, kind, start, end in records:
            scope = dict(contract=symbol, kind=kind, start_ns=start, end_ns=end)
            if rid != identity(scope) or rid in group:
                raise ValueError('Changed or duplicate request identity')
            group[rid] = dict(request_id=rid, **scope)
            if len(group) > 10000:
                raise ValueError('Contract/day exceeds bounded union batch')
        requests += len(group)
        days += 1
        union = capture_union(group.values(), max_span_ns=86400*10**9)['captures']
        paired = {}
        for capture in union:
            key = (capture['start_ns'], capture['end_ns'])
            paired.setdefault(key, {})[capture['kind']] = capture
        for (start, end), captures in paired.items():
            if set(captures) != {'quotes', 'trades'}:
                raise ValueError('Quote/trade union windows do not match')
            if datetime.fromtimestamp(start // 10**9, timezone.utc).date().isoformat() != day:
                raise ValueError('Capture date differs from demand contract/day')
            duration = end - start
            bucket = 'le15m' if duration <= 900*10**9 else ('le60m' if duration <= 3600*10**9 else 'gt60m')
            stratum = f'{day[:4]}-q{quartile}-{bucket}'
            counts[stratum] += 1
            seconds[stratum] += duration
            scope = dict(contract=contract, start_ns=start, end_ns=end)
            pair_id = identity(scope)
            priority = identity(dict(seed=SEED, pair_id=pair_id))
            sample = dict(pair_id=pair_id, priority=priority, stratum=stratum,
                          security_id=security_id, date=day, captures=captures)
            keep(heaps.setdefault(stratum, []), sample, maximum)
    return dict(requests=requests, contract_days=days, population=dict(counts),
                seconds_ns=dict(seconds), samples={k: [r[2] for r in sorted(v, reverse=True)]
                                                  for k, v in heaps.items()})


def scan(arguments):
    sid, demand, quartile, maximum, work, parent_digest = arguments
    from nn_meta.v7.storage import verify, identity, sha, transaction, receipt
    from scripts.download_v7_data import save
    source = Path(demand) / 'demand' / sid
    binding = dict(security_id=sid, parent_sha256=parent_digest, quartile=quartile,
                   maximum=maximum, seed=SEED, source_sha256=sha(__file__),
                   union_sha256=sha(ROOT / 'nn_meta/v7/quotes.py'))
    destination = Path(work) / sid
    if sha(source / 'complete.json') != parent_digest:
        raise ValueError('Demand receipt changed since union audit')
    verify(source)
    if destination.exists():
        verify(destination, expected_identity=identity(binding))
        return sid, json.loads((destination / 'report.json').read_text())
    with sqlite3.connect((source / 'demand.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
        db.execute('PRAGMA query_only=ON')
        db.execute('PRAGMA cache_size=-512')
        rows = db.execute('SELECT request_id,contract,date,kind,start_ns,end_ns FROM requests '
                          'ORDER BY contract,date,kind,start_ns,end_ns')
        report = summarize(rows, security_id=sid, quartile=quartile, maximum=maximum)
    parent_report = json.loads((source / 'report.json').read_text())
    if report['requests'] != parent_report['requests'] or sha(source / 'complete.json') != parent_digest:
        raise ValueError('Demand census or receipt drift')
    with transaction(destination) as temporary:
        save(temporary / 'report.json', report)
        save(temporary / 'binding.json', binding)
        receipt(temporary, dict(identity=identity(binding)))
    return sid, report


def combine(reports, maximum):
    counts, seconds, heaps = Counter(), Counter(), {}
    for report in reports:
        counts.update(report['population'])
        seconds.update(report['seconds_ns'])
        for stratum, samples in report['samples'].items():
            for sample in samples:
                keep(heaps.setdefault(stratum, []), sample, maximum)
    samples = [r[2] for key in sorted(heaps) for r in sorted(heaps[key], reverse=True)]
    if len({s['pair_id'] for s in samples}) != len(samples):
        raise ValueError('Duplicate paired windows across securities')
    return dict(population=dict(counts), seconds_ns=dict(seconds), samples=samples)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--contiguous-audit', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, required=True)
    parser.add_argument('--per-stratum', type=int, default=12)
    args = parser.parse_args()
    from nn_meta.v7.runtime import configure_threads, worker_pool
    configure_threads(1)
    from nn_meta.v7.storage import verify, sha, identity, transaction, receipt
    from scripts.download_v7_data import save
    if not 2 <= args.per_stratum <= 32:
        parser.error('Use 2–32 samples per stratum')
    audit, output = args.audit.resolve(), args.output.resolve()
    if not output.is_relative_to(ROOT / 'nn_meta/validation'):
        parser.error('Use a separate validation output')
    verify(audit)
    contiguous = args.contiguous_audit.resolve()
    verify(contiguous)
    joined = json.loads((contiguous/'report.json').read_text())
    if json.loads((contiguous/'binding.json').read_text())['parent_sha256'] != sha(audit/'complete.json'):
        raise ValueError('Contiguous audit parent mismatch')
    parent = json.loads((audit / 'report.json').read_text())
    source = json.loads((audit / 'binding.json').read_text())
    if parent['input_requests'] != parent['unique_requests'] or parent['securities'] != 591:
        raise ValueError('Expected audited disjoint all-security entry demand')
    binding = dict(contiguous_sha256=sha(contiguous/'complete.json'), audit_sha256=sha(audit / 'complete.json'), source_sha256=sha(__file__),
                   union_sha256=sha(ROOT / 'nn_meta/v7/quotes.py'), seed=SEED,
                   per_stratum=args.per_stratum, stratum_definition='year/request-count-quartile/joined-duration-900-3600-seconds')
    if output.exists():
        verify(output, expected_identity=identity(binding))
        print('Verified existing sample plan', flush=True)
        return
    demand = Path(source['demand_root'])
    sizes = {}
    for sid in source['securities']:
        sizes[sid] = json.loads((demand / 'demand' / sid / 'report.json').read_text())['requests']
    ranked = sorted(sizes, key=lambda s: (sizes[s], s))
    quartiles = {sid: min(3, i*4//len(ranked)) for i, sid in enumerate(ranked)}
    work = output.with_suffix('.checkpoints')
    status_path = output.with_suffix('.status.json')
    def status(state, **fields):
        save(status_path, dict(state=state, updated_at=datetime.now(timezone.utc).isoformat(),
                               total=len(ranked), **fields))
    status('scanning', completed=0)
    reports = {}
    try:
        with worker_pool(args.workers, threads=1) as pool:
            futures = [pool.submit(scan, (sid, str(demand), quartiles[sid], args.per_stratum, str(work),
                        parent['inputs'][str(demand / 'demand' / sid / 'complete.json')])) for sid in ranked]
            for future in as_completed(futures):
                sid, report = future.result()
                reports[sid] = report
                status('scanning', completed=len(reports))
                print(f'Sample frame {len(reports)}/{len(ranked)}: {sid}', flush=True)
        total = combine([reports[s] for s in sorted(reports)], args.per_stratum)
        if (sum(total['population'].values())*2 != joined['contiguous_captures']
                or sum(r['requests'] for r in reports.values()) != parent['input_requests']
                or sum(r['contract_days'] for r in reports.values()) != parent['contract_days']
                or sum(total['seconds_ns'].values()) / 10**9 != parent['union_seconds_by_kind']['quotes']):
            raise ValueError('Sampling population differs from sealed full union')
        requests = [dict(request_id=c['capture_id'], **{k: v for k, v in c.items() if k != 'capture_id'})
                    for sample in total['samples'] for c in sample['captures'].values()]
        if len(requests) > 10000:
            raise ValueError('Sample exceeds bounded request list')
        verify(audit)
        report = dict(schema='v7-joined-volume-sample-plan-v1', **total,
                      securities=len(ranked), security_quartiles=quartiles, sample_requests=len(requests),
                      population_captures=joined['contiguous_captures'], provider_downloads=0,
                      acquisition_budget_bytes=8*1024**3, metadata_budget_bytes=64*1024**2,
                      project_baseline_ceiling_bytes=490000000000,
                      project_budget_bytes=640000000000, disk_reserve_bytes=20*1024**3,
                      statistical_note='Hash priorities approximate stratified random sampling without replacement. '
                      'Small strata samples do not bound tails; forecast is not launch permission.',
                      full_execution_coverage=False, research_ready=False)
        with transaction(output) as temporary:
            save(temporary / 'binding.json', binding)
            save(temporary / 'report.json', report)
            save(temporary / 'requests.json', requests)
            receipt(temporary, dict(identity=identity(binding), research_ready=False))
        status('complete', completed=len(reports), sample_requests=len(requests))
        print(json.dumps(dict(strata=len(total['population']), sample_requests=len(requests),
                              population_captures=joined['contiguous_captures'])), flush=True)
    except BaseException as exc:
        status('failed', completed=len(reports), error=type(exc).__name__)
        raise


if __name__ == '__main__':
    main()
