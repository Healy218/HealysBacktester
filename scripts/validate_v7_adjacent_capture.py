#!/usr/bin/env python3
"""Compare joined provider downloads with original fixed-window raw consumers.

Six outcome-independent/year and explicitly dense stress cases; not a storage
forecast or full-universe provider parity claim. Originals stay immutable.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
POLICY = ROOT / 'docs/specs/V7_CAPTURE_CAPACITY_20260926.json'


def same_records(left, right):
    from options.data.massive_ticks import canonical_bytes
    if canonical_bytes(left) != canonical_bytes(right):
        raise ValueError('Joined capture changed raw record content, order or multiplicity')


def prepare(output):
    from scripts.audit_v7_contiguous_captures import ranges
    from nn_meta.v7.storage import verify, identity, sha, transaction, receipt
    from nn_meta.v7.quotes import capture_union
    from scripts.download_v7_data import save
    sample = ROOT / 'nn_meta/validation/v7-entry-volume-sample-20260926'
    forecast = ROOT / 'nn_meta/validation/v7-entry-volume-forecast-20260926'
    audit = ROOT / 'nn_meta/validation/v7-3-entry-union-20260926'
    for root in (sample, forecast, audit):
        verify(root)
    plan = json.loads((sample / 'report.json').read_text())
    measured = json.loads((forecast / 'report.json').read_text())['measurements']
    parent = json.loads((audit / 'report.json').read_text())
    demand = Path(json.loads((audit / 'binding.json').read_text())['demand_root']) / 'demand'
    binding = dict(inputs={str(p): sha(p) for p in (sample/'complete.json', forecast/'complete.json',
                        audit/'complete.json', POLICY)}, source_sha256=sha(__file__))
    if output.exists():
        verify(output, expected_identity=identity(binding))
        return
    verified = set()
    def candidate(sample):
        store = demand / sample['security_id']
        if store not in verified:
            if sha(store / 'complete.json') != parent['inputs'][str(store / 'complete.json')]:
                raise ValueError('Parent demand receipt drift')
            verify(store); verified.add(store)
        selected = sample['captures']['quotes']
        with sqlite3.connect((store / 'demand.sqlite3').as_uri()+'?mode=ro', uri=True) as db:
            rows = db.execute('SELECT request_id,contract,date,kind,start_ns,end_ns FROM requests '
                'WHERE contract=? AND date=? ORDER BY kind,start_ns,end_ns',
                (selected['contract'], sample['date'])).fetchall()
        intervals = list(ranges([(r[1], r[2], r[4], r[5]) for r in rows if r[3] == 'quotes']))
        match = [r for r in intervals if r[2] <= selected['start_ns'] < selected['end_ns'] <= r[3]]
        if len(match) != 1:
            raise ValueError('Sample does not map to one exact contiguous demand interval')
        contract, day, start, end = match[0]
        requests = [dict(request_id=r[0], contract=r[1], kind=r[3], start_ns=r[4], end_ns=r[5])
                    for r in rows if start <= r[4] < r[5] <= end]
        fixed = capture_union(requests)
        joined = capture_union(requests, max_span_ns=86400*10**9)
        if len(joined['captures']) != 2:
            raise ValueError('Joined quote/trade scope mismatch')
        if len(fixed['captures']) <= 2:
            return None
        return dict(security_id=sample['security_id'], contract=contract, date=day,
                    start_ns=start, end_ns=end, requests=requests,
                    fixed_captures=len(fixed['captures']), joined_captures=2,
                    parent=str(store / 'complete.json'), parent_sha256=sha(store / 'complete.json'))
    cases = []
    for year in sorted({s['date'][:4] for s in plan['samples']}):
        for sample in sorted((s for s in plan['samples'] if s['date'].startswith(year)), key=lambda s: s['priority']):
            case = candidate(sample)
            if case:
                cases.append(dict(case, reason='First seeded-priority joinable sample in year'))
                break
        else:
            raise ValueError('No joinable case in a required year')
    for sample in sorted(plan['samples'], key=lambda s: (-measured[s['captures']['quotes']['capture_id']]['rows'], s['priority'])):
        case = candidate(sample)
        if case and (case['contract'], case['date']) not in {(c['contract'], c['date']) for c in cases}:
            cases.append(dict(case, reason='Densest prior sampled quote window; quality stress only'))
            break
    if len(cases) != 6:
        raise ValueError('Six quality cases required')
    requests = {r['request_id']: r for case in cases for r in case['requests']}
    if len(requests) > 10000:
        raise ValueError('Quality batch exceeds bounded scope')
    policy = json.loads(POLICY.read_text())
    report = dict(cases=cases, sample_budget_bytes=8*1024**3,
                  metadata_budget_bytes=64*1024**2, policy=policy,
                  project_baseline_ceiling_bytes=490000000000,
                  research_ready=False, full_scope_storage_forecast=False)
    with transaction(output) as temp:
        save(temp/'binding.json', binding); save(temp/'report.json', report)
        save(temp/'requests.json', list(requests.values()))
        receipt(temp, dict(identity=identity(binding), research_ready=False))
    print(json.dumps([{k: v for k, v in c.items() if k != 'requests'} for c in cases], indent=2), flush=True)


def run(plan, output, evidence, workers):
    from nn_meta.v7.runtime import worker_pool
    from nn_meta.v7.storage import verify, sha, identity, receipt, transaction
    from nn_meta.v7.quotes import capture_union
    from nn_meta.v7.quote_archive import QuoteArchive
    from scripts.download_v7_data import save, quota_update, tree_bytes, TASK_RESERVATION
    from scripts.capture_v7_volume_sample import capture, measure, guard
    verify(plan)
    declared = json.loads((plan/'binding.json').read_text())
    for path, digest in declared['inputs'].items():
        if sha(path) != digest:
            raise ValueError('Quality plan input drift')
    if declared['source_sha256'] != sha(__file__):
        raise ValueError('Quality plan producer changed')
    doc = json.loads((plan/'report.json').read_text())
    budget = ROOT / 'nn_meta/data_v7'
    if not output.is_relative_to(budget) or not evidence.is_relative_to(ROOT/'nn_meta/validation'):
        raise ValueError('Use acquisition output and a separate validation receipt')
    sources = [Path(__file__), ROOT/'scripts/capture_v7_volume_sample.py', ROOT/'scripts/capture_v7_quotes.py',
               ROOT/'scripts/download_v7_data.py', ROOT/'nn_meta/v7/quote_archive.py',
               ROOT/'nn_meta/v7/quotes.py', ROOT/'options/data/massive_ticks.py']
    binding = dict(plan_sha256=sha(plan/'complete.json'), sources={str(p): sha(p) for p in sources})
    if evidence.exists():
        verify(evidence, expected_identity=identity(binding))
        return
    requests = json.loads((plan/'requests.json').read_text())
    layouts = dict(fixed=capture_union(requests), joined=capture_union(requests, max_span_ns=86400*10**9))
    # Old writer retains its stricter 100 GiB guard for this small validation.
    # The newly authorized 20 GiB policy is checked with full in-flight capacity
    # too; frozen capture producers are deliberately not edited in place.
    policy = doc['policy']
    limits = dict(acquisition_budget_bytes=doc['sample_budget_bytes'], metadata_budget_bytes=doc['metadata_budget_bytes'],
                  disk_reserve_bytes=policy['disk_reserve_bytes'], project_budget_bytes=policy['project_limit_bytes'],
                  project_baseline_ceiling_bytes=doc['project_baseline_ceiling_bytes'])
    if policy['acquisition_limit_bytes'] != json.loads((budget/'quota.json').read_text())['limit_bytes']:
        raise ValueError('Shared acquisition ceiling differs from approved policy')
    status_path = evidence.with_suffix('.status.json')
    results = []
    def status(state):
        save(status_path, dict(state=state, completed=sum(r['ok'] for r in results), failed=sum(not r['ok'] for r in results),
             total=sum(len(p['captures']) for p in layouts.values()), updated_at=datetime.now(timezone.utc).isoformat()))
    output.mkdir(parents=True, exist_ok=True)
    import fcntl
    with (output/'.controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        bound = output/'binding.json'
        if bound.exists() and json.loads(bound.read_text()) != binding:
            raise ValueError('Existing quality attempt belongs to another binding')
        metadata_key = uuid.uuid4().hex
        quota_update(budget, reserve=metadata_key)
        before = tree_bytes(output)
        try:
            save(bound, binding)
            for name, layout in layouts.items():
                (output/name).mkdir(exist_ok=True)
                target = output/name/'requests.json'
                if target.exists() and json.loads(target.read_text()) != layout:
                    raise ValueError('Existing archive layout changed')
                save(target, layout)
        finally:
            quota_update(budget, finish=(metadata_key, max(0, tree_bytes(output)-before)))
        try:
            with worker_pool(workers, threads=1) as pool:
                for name, layout in layouts.items():
                    for offset in range(0, len(layout['captures']), workers):
                        group = layout['captures'][offset:offset+workers]
                        guard(limits, used_bytes=tree_bytes(output), pending=len(group), task_reservation=TASK_RESERVATION,
                              free_bytes=shutil.disk_usage(output).free, quota=json.loads((budget/'quota.json').read_text()))
                        # Reuse exact previously captured shards by immutable
                        # hardlinks; no duplicated raw acquisition charge.
                        for item in group:
                            destination = output/name/item['capture_id']
                            if destination.exists():
                                continue
                            for prior in ('entry-volume-sample-20260926', 'entry-first-actual-20260926'):
                                source = budget/prior/item['capture_id']
                                if source.exists():
                                    measure(item, budget/prior)
                                    with transaction(destination) as temp:
                                        for file in source.iterdir():
                                            if file.is_file():
                                                os.link(file, temp/file.name)
                                    break
                        group_results = list(pool.map(capture, [(c, str(output/name), str(budget)) for c in group]))
                        results.extend(dict(r, layout=name) for r in group_results)
                        attempt = evidence.with_suffix('.attempts')/uuid.uuid4().hex
                        with transaction(attempt) as temp:
                            save(temp/'results.json', group_results)
                            receipt(temp, dict(identity=identity(group_results)))
                        status('capturing')
                        print(f'Quality captures {len(results)}/{sum(len(p["captures"]) for p in layouts.values())}', flush=True)
                        if any(not r['ok'] for r in group_results):
                            raise ValueError('Quality download failed; preserve attempts and investigate')
            fixed, joined = QuoteArchive(output/'fixed', cache_shards=2), QuoteArchive(output/'joined', cache_shards=2)
            checks = []
            for request in requests:
                scope = [request[k] for k in ('contract', 'kind', 'start_ns', 'end_ns')]
                left, lm = fixed.window(*scope); right, rm = joined.window(*scope)
                same_records(left, right)
                if lm['records_sha256'] != rm['records_sha256']:
                    raise ValueError('Causal archive result hash mismatch')
                checks.append(dict(request_id=request['request_id'], records=len(left), records_sha256=lm['records_sha256']))
            whole = []
            for item in layouts['joined']['captures']:
                scope = [item[k] for k in ('contract', 'kind', 'start_ns', 'end_ns')]
                left, lm = fixed.window(*scope); right, rm = joined.window(*scope)
                same_records(left, right)
                whole.append(dict(capture_id=item['capture_id'], records=len(left), records_sha256=lm['records_sha256']))
            for path, digest in binding['sources'].items():
                if sha(path) != digest:
                    raise ValueError('Bound source changed during quality run')
            if sha(plan/'complete.json') != binding['plan_sha256']:
                raise ValueError('Quality plan changed during run')
            report = dict(raw_record_parity=True, causal_request_parity=True, cases=doc['cases'],
                          request_checks=checks, full_range_checks=whole, capture_results=results,
                          original_request_count=len(requests), fixed_captures=len(layouts['fixed']['captures']),
                          joined_captures=len(layouts['joined']['captures']),
                          fixed_logical_bytes=tree_bytes(output/'fixed'), joined_logical_bytes=tree_bytes(output/'joined'),
                          quality_cases_only=True, full_scope_storage_forecast=False, research_ready=False)
            with transaction(evidence) as temp:
                save(temp/'binding.json', binding); save(temp/'report.json', report)
                receipt(temp, dict(identity=identity(binding), research_ready=False))
            status('complete')
            print(json.dumps({k: v for k,v in report.items() if k not in ('cases','request_checks','full_range_checks','capture_results')}), flush=True)
        except BaseException:
            status('failed')
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare','run'))
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--evidence', type=Path)
    parser.add_argument('--workers', type=int)
    args = parser.parse_args()
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    if not args.plan.resolve().is_relative_to(ROOT/'nn_meta/validation'):
        parser.error('Use a separate validation plan')
    if args.action == 'prepare':
        prepare(args.plan.resolve())
    else:
        if args.output is None or args.evidence is None or args.workers is None:
            parser.error('run requires --output, --evidence and --workers')
        run(args.plan.resolve(), args.output.resolve(), args.evidence.resolve(), args.workers)


if __name__ == '__main__':
    main()
