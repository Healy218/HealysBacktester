#!/usr/bin/env python3
"""Bounded full-scope entry-window union census. No provider requests or training.

Streams immutable demand databases without copying their request tables. The
small result is a capture-planning input, not a complete option-path verdict.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import ExitStack, closing
from datetime import datetime, timezone
from heapq import merge
from itertools import groupby
import json
from pathlib import Path
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def census(rows, on_group=None):
    from nn_meta.v7.quotes import capture_union
    from nn_meta.v7.storage import identity
    totals = Counter(input_requests=0, unique_requests=0, captures=0, contract_days=0)
    seconds = Counter()
    contracts = 0
    last_contract = None
    for (contract, day), records in groupby(rows, key=lambda r: (r[1], r[2])):
        group = {}
        for rid, symbol, date, kind, start, end in records:
            scope = dict(contract=symbol, kind=kind, start_ns=start, end_ns=end)
            if rid != identity(scope):
                raise ValueError('Request identity differs from content')
            totals['input_requests'] += 1
            group[rid] = dict(request_id=rid, **scope)
            if len(group) > 10000:
                raise ValueError('Contract/day exceeds bounded capture batch size')
        result = capture_union(group.values())
        captures = {c['capture_id']: c for c in result['captures']}
        for rid, request in group.items():
            cursor = request['start_ns']
            for c in sorted((captures[cid] for cid in result['request_captures'][rid]),
                            key=lambda c: c['start_ns']):
                if c['contract'] != contract or c['kind'] != request['kind'] or c['start_ns'] > cursor:
                    raise ValueError('Union dropped or misrouted a requested interval')
                cursor = max(cursor, min(request['end_ns'], c['end_ns']))
            if cursor != request['end_ns']:
                raise ValueError('Union leaves a request gap')
        totals['unique_requests'] += len(group)
        totals['captures'] += len(captures)
        totals['contract_days'] += 1
        if contract != last_contract:
            contracts += 1
            last_contract = contract
        for c in captures.values():
            totals[c['kind'] + '_captures'] += 1
            seconds[c['kind']] += (c['end_ns'] - c['start_ns']) / 1e9
        if on_group is not None:
            on_group(dict(totals))
    return dict(totals, contracts=contracts, union_seconds_by_kind=dict(seconds))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demand', type=Path, required=True)
    parser.add_argument('--completion', type=Path, required=True)
    parser.add_argument('--kernel-proof', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--wait', action='store_true', help='Wait for full demand completion; never start captures')
    args = parser.parse_args()
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    from nn_meta.v7.storage import sha, verify, identity, receipt, transaction
    from scripts.resume_v7_entry_demand import KernelCatalogProof, runtime_allowed, runtime_manifest
    from scripts import run_v7_entry_demand as original
    for name in ('demand', 'completion', 'kernel_proof', 'output'):
        setattr(args, name, getattr(args, name).resolve())
    if not args.output.is_relative_to(ROOT / 'nn_meta/validation') or args.output == args.demand:
        parser.error('Use a separate validation output')
    status_path = args.output.with_suffix('.status.json')
    def status(state, **fields):
        original.write(status_path, dict(stage='v7-3-entry-request-union', state=state,
                       updated_at=datetime.now(timezone.utc).isoformat(), **fields))
    while True:
        progress = original.read(args.demand / 'kernel-recovery/progress.json')
        if progress['failed']:
            status('blocked', reason='Demand recovery failed', failures=progress['failed'])
            return 1
        if progress.get('full_scope_complete') and progress['completed'] == progress['selected'] == 591:
            break
        status('waiting_for_full_demand', completed=progress['completed'], total=591)
        if not args.wait:
            print('Full 591-security entry demand is not complete; no union/capture started.', flush=True)
            return 2
        time.sleep(30)
    proof = KernelCatalogProof(args.completion, args.kernel_proof)
    binding = dict(completion_sha256=sha(args.completion / 'complete.json'),
                   kernel_proof_sha256=sha(args.kernel_proof / 'complete.json'),
                   audit_source_sha256=sha(__file__), union_source_sha256=sha(ROOT / 'nn_meta/v7/quotes.py'),
                   demand_root=str(args.demand), securities=proof.security_ids)
    if args.output.exists():
        verify(args.output, expected_identity=identity(binding))
        status('complete', reused=True)
        return 0
    inputs = dict(proof.bindings)
    inputs[str(Path(__file__).resolve())] = sha(__file__)
    inputs[str(ROOT / 'nn_meta/v7/quotes.py')] = binding['union_source_sha256']
    cache = {}
    source_reports = []
    last_status = 0
    def union_progress(counts):
        nonlocal last_status
        if time.monotonic() - last_status >= 15:
            status('unioning', **counts)
            last_status = time.monotonic()
    try:
        with ExitStack() as stack:
            streams = []
            for number, sid in enumerate(proof.security_ids, 1):
                checkpoint = args.demand / 'checkpoints' / sid
                checkpoint_doc = verify(checkpoint)
                active = ROOT / 'docs/specs/V7_ACTIVE_INPUTS_20220315_OPTION_RISK.json'
                legacy = dict(security_id=sid, completion_sha256=sha(args.completion / 'complete.json'),
                              active_sha256=sha(active), scheduler_sha256=sha(original.__file__))
                recovered = dict(legacy, recovery_source_sha256=sha(ROOT / 'scripts/resume_v7_entry_demand.py'),
                                 kernel_proof_sha256=sha(args.kernel_proof / 'complete.json'))
                if checkpoint_doc['identity'] not in (identity(legacy), identity(recovered)):
                    raise ValueError('Foreign demand checkpoint identity')
                result = original.read(checkpoint / 'result.json')
                if result['security_id'] != sid or any(sha(p) != h for p, h in result['receipts'].items()):
                    raise ValueError('Demand checkpoint receipts changed')
                inputs[str(checkpoint / 'complete.json')] = sha(checkpoint / 'complete.json')
                inputs.update(result['receipts'])
                demand = args.demand / 'demand' / sid
                declaration = original.read(demand / 'declaration.json')
                verify(demand, expected_identity=identity(declaration))
                runtime_allowed(declaration['runtime'], runtime_manifest())
                if declaration['security_id'] != sid or declaration['schema'] != 'v7-proposal-entry-demand-v1':
                    raise ValueError('Foreign demand declaration')
                for path, digest in declaration['inputs'].items():
                    if path not in cache:
                        cache[path] = sha(path)
                    if cache[path] != digest:
                        raise ValueError('Demand parent drift')
                export = args.demand / 'requests' / sid
                export_binding = dict(parent=str(demand), parent_sha256=sha(demand / 'complete.json'),
                                      maximum=10000, scope=declaration['scope'])
                verify(export, expected_identity=identity(export_binding))
                export_report = original.read(export / 'report.json')
                report = original.read(demand / 'report.json')
                if export_report['requests'] != report['requests'] or report != result['report']:
                    raise ValueError('Demand/export/checkpoint census differs')
                source_reports.append(report)
                db = stack.enter_context(closing(sqlite3.connect(
                    (demand / 'demand.sqlite3').as_uri() + '?mode=ro', uri=True)))
                db.execute('PRAGMA query_only=ON')
                db.execute('PRAGMA cache_size=-128')
                streams.append(db.execute('SELECT request_id,contract,date,kind,start_ns,end_ns FROM requests '
                                          'ORDER BY contract,date,kind,start_ns,end_ns'))
                status('verifying_inputs', completed=number, total=591)
            rows = merge(*streams, key=lambda r: (r[1], r[2], r[3], r[4], r[5]))
            totals = census(rows, union_progress)
        expected = sum(r['requests'] for r in source_reports)
        if totals['input_requests'] != expected:
            raise ValueError('Union input census differs from sealed demand')
        if any(sha(p) != h for p, h in inputs.items()):
            raise ValueError('Demand receipts changed during union audit')
        proof.check_evidence()
        report = dict(schema='v7-full-entry-union-census-v1', **totals, securities=591,
                      proposals=sum(r['proposals'] for r in source_reports),
                      selection_statuses=dict(sum((Counter(r['selection_statuses']) for r in source_reports), Counter())),
                      input_bindings_checked=len(cache), inputs=inputs,
                      scope='Entry-feature windows only; no execution-path completeness',
                      capture_volume_forecast_available=False, provider_downloads=0, research_ready=False)
        with transaction(args.output) as temp:
            original.write(temp / 'binding.json', binding)
            original.write(temp / 'report.json', report)
            receipt(temp, dict(identity=identity(binding), research_ready=False))
        status('complete', **totals)
        print(json.dumps({k: v for k, v in report.items() if k != 'inputs'}), flush=True)
    except BaseException as exc:
        status('failed', error=type(exc).__name__, reason=str(exc))
        raise
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
