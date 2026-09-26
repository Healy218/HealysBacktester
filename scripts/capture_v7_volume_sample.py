#!/usr/bin/env python3
"""Capture a sealed volume sample under explicit disk/project/acquisition caps.

Never launches full acquisition or training. Failures remain explicit and prevent
a complete forecast. Re-running reuses receipts without replacing any capture.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import fcntl
import gzip
import json
import math
from pathlib import Path
import re
import shutil
import statistics
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def measure(item, output):
    from nn_meta.v7.storage import verify
    from options.data.massive_ticks import verify_capture
    root = Path(output) / item['capture_id']
    receipt = verify(root, expected_identity=item['capture_id'])
    if receipt['capture'] != item:
        raise ValueError('Capture scope drift')
    records = json.loads(gzip.decompress((root / 'records.json.gz').read_bytes()))
    manifest = json.loads((root / 'capture.json').read_text())
    verify_capture(records, manifest, **{k: item[k] for k in ('contract', 'kind', 'start_ns', 'end_ns')})
    if receipt['rows'] != len(records):
        raise ValueError('Capture receipt count mismatch')
    files = list(root.iterdir())
    return dict(capture_id=item['capture_id'], rows=len(records), pages=manifest['pages'],
                logical_bytes=sum(p.stat().st_size for p in files if p.is_file()),
                allocated_bytes=sum(p.stat().st_blocks*512 for p in files if p.is_file()),
                records_gzip_bytes=(root / 'records.json.gz').stat().st_size,
                receipt_sha256=__import__('hashlib').sha256((root / 'complete.json').read_bytes()).hexdigest())


def capture(arguments):
    item, output, budget = arguments
    from scripts.capture_v7_quotes import capture_one
    started = time.monotonic()
    try:
        result = capture_one((item, output, budget))
        return dict(ok=True, reused=result['reused'], elapsed_seconds=time.monotonic()-started,
                    **measure(item, output))
    except Exception as exc:
        # Provider exceptions are deliberately sanitized: never persist request
        # URLs, environment, response bodies or credentials in a failure receipt.
        reason = str(exc) if re.fullmatch(r'Massive ticks HTTP [0-9]{3}', str(exc)) else 'Capture or verification failed; no coverage inferred'
        return dict(ok=False, capture_id=item['capture_id'], error_type=type(exc).__name__,
                    elapsed_seconds=time.monotonic()-started,
                    reason=reason)


def forecast(plan, measurements):
    by_stratum = defaultdict(list)
    expected = {c['capture_id'] for s in plan['samples'] for c in s['captures'].values()}
    if set(measurements) != expected or any(not r['ok'] for r in measurements.values()):
        raise ValueError('Every predeclared sample must pass; failed samples cannot be dropped')
    for sample in plan['samples']:
        pair = [measurements[c['capture_id']] for c in sample['captures'].values()]
        by_stratum[sample['stratum']].append(sum(r['logical_bytes'] for r in pair))
    total = variance = 0.0
    strata = {}
    for stratum, population in sorted(plan['population'].items()):
        values = by_stratum[stratum]
        n = len(values)
        if n > population or (n < 2 and n != population):
            raise ValueError('Insufficient or invalid stratum sample')
        mean = statistics.mean(values)
        component = 0 if n == population else population**2*(1-n/population)*statistics.variance(values)/n
        total += population*mean
        variance += component
        strata[stratum] = dict(population_pairs=population, sample_pairs=n,
                              mean_pair_bytes=mean, min_pair_bytes=min(values), max_pair_bytes=max(values),
                              estimated_bytes=population*mean)
    return dict(estimated_capture_bytes=math.ceil(total), standard_error_bytes=math.sqrt(variance),
                mean_plus_three_se_bytes=math.ceil(total+3*math.sqrt(variance)), strata=strata,
                excludes='Request mappings, directory metadata, dated references and execution paths',
                caveat='Design-based estimate under hash randomization; three SE is not a tail guarantee. '
                       'The finite sample cannot establish a hard upper capacity bound.',
                full_acquisition_authorized=False, research_ready=False)


def guard(plan, *, used_bytes, pending, task_reservation, free_bytes, quota):
    reserve = pending*task_reservation
    if used_bytes+reserve > plan['acquisition_budget_bytes']:
        raise ValueError('Sample acquisition ceiling cannot cover next worker group')
    if free_bytes-reserve-plan['metadata_budget_bytes'] < plan['disk_reserve_bytes']:
        raise ValueError('Next worker group would violate disk reserve')
    if (plan['project_baseline_ceiling_bytes']+plan['acquisition_budget_bytes']
            +plan['metadata_budget_bytes'] > plan['project_budget_bytes']):
        raise ValueError('Sample exceeds total-project ceiling')
    if quota['used_bytes']+sum(quota['reservations'].values())+reserve > quota['limit_bytes']:
        raise ValueError('Shared acquisition budget cannot cover worker group')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--budget-root', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--workers', type=int, required=True)
    args = parser.parse_args()
    from nn_meta.v7.runtime import configure_threads, worker_pool
    configure_threads(1)
    from nn_meta.v7.storage import verify, identity, sha, transaction, receipt
    from nn_meta.v7.quotes import capture_union
    from scripts.download_v7_data import save, tree_bytes, TASK_RESERVATION, quota_update
    for name in ('plan', 'output', 'budget_root', 'evidence'):
        setattr(args, name, getattr(args, name).resolve())
    if not args.output.is_relative_to(args.budget_root) or not args.evidence.is_relative_to(ROOT / 'nn_meta/validation'):
        parser.error('Capture output must be inside its acquisition budget; evidence in validation')
    verify(args.plan)
    plan = json.loads((args.plan / 'report.json').read_text())
    union = capture_union(json.loads((args.plan / 'requests.json').read_text()))
    expected = {c['capture_id']: c for s in plan['samples'] for c in s['captures'].values()}
    if {c['capture_id']: c for c in union['captures']} != expected:
        raise ValueError('Sampling selection changed through request union')
    binding = dict(plan_sha256=sha(args.plan / 'complete.json'), output=str(args.output),
                   sources={str(p): sha(p) for p in (Path(__file__), ROOT / 'scripts/capture_v7_quotes.py',
                       ROOT / 'options/data/massive_ticks.py', ROOT / 'scripts/download_v7_data.py',
                       ROOT / 'nn_meta/v7/quotes.py', ROOT / 'nn_meta/v7/storage.py')})
    if args.evidence.exists():
        verify(args.evidence, expected_identity=identity(binding))
        for item in expected.values():
            measure(item, args.output)
        print('Verified completed sample and forecast; no downloads', flush=True)
        return
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / '.controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        binding_path = args.output / 'sample-binding.json'
        if binding_path.exists() and json.loads(binding_path.read_text()) != binding:
            raise ValueError('Sample consumer/source identity changed; preserve this attempt')
        metadata = [binding_path, args.output / 'requests.json']
        before = sum(p.stat().st_size for p in metadata if p.exists())
        reservation = uuid.uuid4().hex
        quota_update(args.budget_root, reserve=reservation)
        try:
            save(binding_path, binding)
            save(args.output / 'requests.json', union)
        finally:
            after = sum(p.stat().st_size for p in metadata if p.exists())
            quota_update(args.budget_root, finish=(reservation, max(0, after-before)))
        progress_path = args.evidence.with_suffix('.status.json')
        attempts = args.evidence.with_suffix('.attempts')
        attempts.mkdir(parents=True, exist_ok=True)
        measurements = {}
        started = time.monotonic()
        def status(state):
            save(progress_path, dict(state=state, total=len(expected),
                completed=sum(r['ok'] for r in measurements.values()),
                failed=sum(not r['ok'] for r in measurements.values()),
                elapsed_seconds=time.monotonic()-started,
                captured_bytes=sum(r.get('logical_bytes', 0) for r in measurements.values()),
                updated_at=datetime.now(timezone.utc).isoformat(), output=str(args.output)))
        status('capturing')
        ordered = sorted(expected.values(), key=lambda c: c['capture_id'])
        try:
            with worker_pool(args.workers, threads=1) as pool:
                for offset in range(0, len(ordered), args.workers):
                    group = ordered[offset:offset+args.workers]
                    quota = json.loads((args.budget_root / 'quota.json').read_text())
                    guard(plan, used_bytes=tree_bytes(args.output),
                          pending=sum(not (args.output / c['capture_id']).exists() for c in group),
                          task_reservation=TASK_RESERVATION, free_bytes=shutil.disk_usage(args.output).free, quota=quota)
                    results = list(pool.map(capture, [(c, str(args.output), str(args.budget_root)) for c in group]))
                    for result in results:
                        measurements[result['capture_id']] = result
                        destination = attempts / (result['capture_id']+'-'+uuid.uuid4().hex)
                        with transaction(destination) as temporary:
                            save(temporary / 'result.json', result)
                            receipt(temporary, dict(identity=identity(dict(binding=binding, result=result))))
                    status('capturing')
                    print(f"Captures {len(measurements)}/{len(expected)}; "
                          f"failed={sum(not r['ok'] for r in measurements.values())}", flush=True)
                    if sum(not r['ok'] for r in measurements.values()) >= 8:
                        raise ValueError('Eight sample failures; preserve attempts and investigate before resuming')
            status('verifying')
            for item in expected.values():
                result = measurements[item['capture_id']]
                if result['ok'] and measure(item, args.output) != {k: v for k, v in result.items()
                                                                 if k not in ('ok', 'reused', 'elapsed_seconds')}:
                    raise ValueError('Sample changed during measurement')
            report = forecast(plan, measurements)
            for path, digest in binding['sources'].items():
                if sha(path) != digest:
                    raise ValueError('Capture source changed during run')
            verify(args.plan)
            quota = json.loads((args.budget_root / 'quota.json').read_text())
            free = shutil.disk_usage(args.output).free
            report.update(schema='v7-entry-volume-forecast-v1',
                sample_captures=len(expected), sample_rows=sum(r['rows'] for r in measurements.values()),
                sample_bytes=tree_bytes(args.output), measurements=measurements,
                acquisition_remaining_bytes=quota['limit_bytes']-quota['used_bytes']-sum(quota['reservations'].values()),
                disk_additional_capacity_bytes=free-plan['disk_reserve_bytes'],
                current_layout_fits_disk=report['mean_plus_three_se_bytes'] <= free-plan['disk_reserve_bytes'],
                elapsed_seconds=time.monotonic()-started,
                full_execution_coverage=False)
            with transaction(args.evidence) as temporary:
                save(temporary / 'binding.json', binding)
                save(temporary / 'report.json', report)
                receipt(temporary, dict(identity=identity(binding), research_ready=False))
            status('complete')
            print(json.dumps({k: v for k, v in report.items() if k not in ('measurements', 'strata')}), flush=True)
        except BaseException:
            status('failed_or_capacity_paused')
            raise


if __name__ == '__main__':
    main()
