#!/usr/bin/env python3
"""Download the predeclared joined sample directly into immutable indexed packs.

No bulk acquisition or training. Complete sample, exact raw roundtrip and actual
SQLite/index/receipt overhead are required before publishing a forecast.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import re
import shutil
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def capture_split(client, item, failures, depth=0):
    from options.data.massive_ticks import TickDataError
    from nn_meta.v7.storage import identity
    try:
        rows, manifest = client.capture(**{k: item[k] for k in ('contract','kind','start_ns','end_ns')}, max_pages=4)
        yield item, rows, manifest
    except TickDataError as exc:
        if str(exc) != 'page budget exhausted; capture incomplete':
            raise
        failures.append(dict(capture_id=item['capture_id'], reason='page budget exhausted; capture incomplete', depth=depth))
        if depth >= 16 or item['end_ns']-item['start_ns'] <= 1:
            raise ValueError('Dense capture cannot be split within bounds') from None
        middle = (item['start_ns']+item['end_ns'])//2
        for start, end in ((item['start_ns'],middle),(middle,item['end_ns'])):
            scope = dict(contract=item['contract'],kind=item['kind'],start_ns=start,end_ns=end)
            yield from capture_split(client, dict(scope,capture_id=identity(scope)), failures, depth+1)


def measure_pack(destination, items, binding):
    from nn_meta.v7.packed_quotes import PackedQuoteArchive
    from nn_meta.v7.storage import verify, identity, sha
    from scripts.download_v7_data import tree_bytes
    doc = verify(destination, expected_identity=identity(binding))
    measurements = {}
    payload_total = sum(doc['payload_bytes'].values())
    total = tree_bytes(destination)
    overhead = total-payload_total
    with PackedQuoteArchive(destination) as archive:
        for item in items:
            rows, manifest = archive.window(*[item[k] for k in ('contract','kind','start_ns','end_ns')])
            ids = [s['capture_id'] for s in manifest['derived_from_captures']]
            payload = sum(doc['payload_bytes'][cid] for cid in ids)
            measurements[item['capture_id']] = dict(ok=True, rows=len(rows),
                logical_bytes=payload+overhead/len(items), payload_bytes=payload,
                records_sha256=manifest['records_sha256'], leaf_captures=len(ids),
                pack_receipt_sha256=sha(destination/'complete.json'))
    if abs(sum(m['logical_bytes'] for m in measurements.values())-total)>0.01:
        raise ValueError('Packed measurements do not reconcile')
    return dict(measurements=measurements, logical_bytes=total, overhead_bytes=overhead,
                leaf_captures=doc['captures'])


def worker(arguments):
    items, destination, budget, binding = arguments
    from dotenv import load_dotenv
    from options.data.massive_ticks import MassiveTicks
    from nn_meta.v7.packed_quotes import write_pack
    from scripts.download_v7_data import quota_update, tree_bytes
    destination, budget = Path(destination), Path(budget)
    failures = []
    started = time.monotonic()
    try:
        reused = destination.exists()
        if not reused:
            load_dotenv(ROOT/'.env')
            client = MassiveTicks()
            reservation = uuid.uuid4().hex
            quota_update(budget, reserve=reservation)
            try:
                def entries():
                    for item in items:
                        yield from capture_split(client,item,failures)
                write_pack(destination, entries(), binding=binding)
            finally:
                used = tree_bytes(destination) if destination.exists() else 0
                used += sum(tree_bytes(p) for p in destination.parent.glob(destination.name+'.partial-*'))
                # Previously charged partials are excluded by the controller's
                # per-attempt destination: a retry receives a fresh attempt ID.
                quota_update(budget, finish=(reservation,used))
        return dict(ok=True, reused=reused, pack=str(destination), split_attempts=failures,
                    elapsed_seconds=time.monotonic()-started, **measure_pack(destination,items,binding))
    except Exception as exc:
        reason = str(exc) if re.fullmatch(r'Massive ticks HTTP [0-9]{3}',str(exc)) else 'Capture or verification failed; no coverage inferred'
        return dict(ok=False, pack=str(destination), error_type=type(exc).__name__, reason=reason,
                    split_attempts=failures, elapsed_seconds=time.monotonic()-started)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('plan','output','evidence'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--workers',type=int,required=True)
    args=parser.parse_args()
    from nn_meta.v7.runtime import configure_threads, worker_pool
    configure_threads(1)
    from nn_meta.v7.storage import verify, identity, sha, receipt, transaction
    from scripts.download_v7_data import save, tree_bytes, TASK_RESERVATION, quota_update
    from scripts.capture_v7_volume_sample import forecast, guard
    for name in ('plan','output','evidence'):
        setattr(args,name,getattr(args,name).resolve())
    budget=ROOT/'nn_meta/data_v7'
    if not args.output.is_relative_to(budget) or not args.evidence.is_relative_to(ROOT/'nn_meta/validation'):
        parser.error('Use acquisition output and validation evidence')
    verify(args.plan)
    plan=json.loads((args.plan/'report.json').read_text())
    if plan['schema']!='v7-joined-volume-sample-plan-v1' or plan['securities']!=591:
        raise ValueError('Complete predeclared joined sampling frame required')
    policy_path=ROOT/'docs/specs/V7_CAPTURE_CAPACITY_20260926.json'
    policy=json.loads(policy_path.read_text())
    if (plan['disk_reserve_bytes']!=policy['disk_reserve_bytes'] or
            plan['project_budget_bytes']!=policy['project_limit_bytes']):
        raise ValueError('Sampling plan differs from approved capacity policy')
    sources=[Path(__file__),ROOT/'nn_meta/v7/packed_quotes.py',ROOT/'nn_meta/v7/quote_archive.py',
        ROOT/'nn_meta/v7/storage.py',ROOT/'options/data/massive_ticks.py',ROOT/'scripts/download_v7_data.py',
        ROOT/'scripts/capture_v7_volume_sample.py',policy_path]
    binding=dict(plan_sha256=sha(args.plan/'complete.json'),sources={str(p):sha(p) for p in sources})
    if args.evidence.exists():
        verify(args.evidence,expected_identity=identity(binding))
        report=json.loads((args.evidence/'report.json').read_text())
        for result in report['packs']:
            path=Path(result['pack'])
            verify(path)
        print('Verified sealed packed forecast; no downloads',flush=True)
        return
    items=sorted([c for sample in plan['samples'] for c in sample['captures'].values()],key=lambda c:c['capture_id'])
    if len({c['capture_id'] for c in items})!=len(items):
        raise ValueError('Duplicate sample captures')
    args.output.mkdir(parents=True,exist_ok=True)
    started=time.monotonic()
    with (args.output/'.controller.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        bound=args.output/'binding.json'
        if bound.exists() and json.loads(bound.read_text())!=binding:
            raise ValueError('Packed capture source changed; preserve attempt')
        reservation=uuid.uuid4().hex
        quota_update(budget,reserve=reservation)
        before=tree_bytes(args.output)
        try:
            save(bound,binding)
        finally:
            quota_update(budget,finish=(reservation,max(0,tree_bytes(args.output)-before)))
        batches=[items[i:i+24] for i in range(0,len(items),24)]
        results=[]
        def status(state):
            save(args.evidence.with_suffix('.status.json'),dict(state=state,completed_packs=len(results),
                total_packs=len(batches),elapsed_seconds=time.monotonic()-started,
                updated_at=datetime.now(timezone.utc).isoformat()))
        status('capturing')
        try:
            with worker_pool(args.workers,threads=1) as pool:
                for offset in range(0,len(batches),args.workers):
                    tasks=[]
                    for batch in batches[offset:offset+args.workers]:
                        pack_binding=dict(parent=binding,captures=batch)
                        key=identity(pack_binding)
                        candidates=sorted(args.output.glob(key+'-*'))
                        complete=[p for p in candidates if '.partial-' not in p.name and (p/'complete.json').exists()]
                        if len(complete)>1:
                            raise ValueError('Ambiguous completed pack attempts')
                        destination=complete[0] if complete else args.output/(key+'-'+uuid.uuid4().hex)
                        tasks.append((batch,str(destination),str(budget),pack_binding))
                    quota=json.loads((budget/'quota.json').read_text())
                    if quota['limit_bytes']!=policy['acquisition_limit_bytes']:
                        raise ValueError('Acquisition ceiling drift')
                    guard(plan,used_bytes=tree_bytes(args.output),pending=len(tasks),task_reservation=TASK_RESERVATION,
                          free_bytes=shutil.disk_usage(args.output).free,quota=quota)
                    group=list(pool.map(worker,tasks))
                    results.extend(group)
                    with transaction(args.evidence.with_suffix('.attempts')/uuid.uuid4().hex) as temp:
                        save(temp/'results.json',group); receipt(temp,dict(identity=identity(group)))
                    status('capturing')
                    print(f'Packed captures: {len(results)}/{len(batches)} packs',flush=True)
                    if any(not r['ok'] for r in group):
                        raise ValueError('Sample failure; all attempts preserved; no forecast')
            measurements={key:value for r in results for key,value in r['measurements'].items()}
            report=forecast(plan,measurements)
            for path,digest in binding['sources'].items():
                if sha(path)!=digest:
                    raise ValueError('Packed producer changed during capture')
            verify(args.plan)
            report.update(schema='v7-joined-packed-volume-forecast-v1',measurements=measurements,packs=results,
                sample_captures=len(items),sample_records=sum(m['rows'] for m in measurements.values()),
                measured_pack_bytes=sum(r['logical_bytes'] for r in results),
                measured_pack_overhead_bytes=sum(r['overhead_bytes'] for r in results),
                sample_seconds=time.monotonic()-started,production_archive_implemented=True,
                population_captures=plan['population_captures'],
                excludes='Additional pack routing/mappings, dated references, held execution paths, assembly and training arrays',
                full_execution_coverage=False,research_ready=False)
            with transaction(args.evidence) as temp:
                save(temp/'binding.json',binding); save(temp/'report.json',report)
                receipt(temp,dict(identity=identity(binding),research_ready=False))
            status('complete')
            print(json.dumps({k:v for k,v in report.items() if k not in ('packs','measurements','strata')}),flush=True)
        except BaseException:
            status('failed_or_capacity_paused')
            raise


if __name__=='__main__':
    main()
