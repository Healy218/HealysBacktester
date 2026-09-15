"""Resumable, bounded V7 base-data acquisition. Does not declare data research-ready.

Raw provider pages/objects and completion hashes are retained. Observed-empty
stock responses remain distinct from verified listing/calendar coverage.
Full OPRA quote files are deliberately not part of this base-data job.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone, timedelta, date
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import uuid
import fcntl
import multiprocessing

for _thread_env in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
                    'NUMBA_NUM_THREADS', 'POLARS_MAX_THREADS', 'BLOSC_NTHREADS'):
    os.environ[_thread_env] = '1'

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests
from dotenv import load_dotenv

ROOT = Path(os.environ.get('V7_REPOSITORY_ROOT', Path(__file__).resolve().parents[1]))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(4 * 1024**2), b''):
            h.update(b)
    return h.hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp-' + uuid.uuid4().hex)
    with tmp.open('w') as f:
        json.dump(value, f, sort_keys=True, indent=2, allow_nan=False)
        f.write('\n'); f.flush(); os.fsync(f.fileno())
    tmp.replace(path)


def headers():
    load_dotenv(ROOT / '.env')
    key, secret = os.environ.get('ALPACA_API_KEY'), os.environ.get('ALPACA_API_SECRET')
    if not key or not secret:
        raise RuntimeError('Alpaca credentials missing')
    return {'APCA-API-KEY-ID': key, 'APCA-API-SECRET-KEY': secret}


def get_json(session, url, params):
    for attempt in range(5):
        try:
            response = session.get(url, params=params, headers=headers(), timeout=60, allow_redirects=False)
        except requests.RequestException:
            if attempt == 4:
                raise RuntimeError('Alpaca transport failed') from None
            time.sleep(min(2**attempt, 16)); continue
        if response.status_code == 200:
            return response.content, response.json()
        if response.status_code not in (429, 500, 502, 503, 504) or attempt == 4:
            raise RuntimeError(f'Alpaca HTTP {response.status_code}')
        time.sleep(min(2**attempt, 16))
    raise RuntimeError('Alpaca retries exhausted')


def disk_guard(root, reserve_gib):
    if shutil.disk_usage(root).free < reserve_gib * 1024**3:
        raise CapacityPause('Disk reserve reached; resume after freeing capacity')


class CapacityPause(RuntimeError):
    pass


TASK_RESERVATION = 1024**3


def tree_bytes(root):
    total, seen = 0, set()
    for path in root.rglob('*'):
        if path.is_file():
            stat = path.stat(); key = (stat.st_dev, stat.st_ino)
            if key not in seen:
                total += stat.st_size; seen.add(key)
    return total


def quota_update(root, *, initialize=None, reserve=None, finish=None):
    """One atomic capacity ledger shared by all worker reservations."""
    root = Path(root)
    with (root / '.quota.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = root / 'quota.json'
        if initialize is not None:
            # Controller owns the exclusive acquisition lock before recovery.
            doc = {'limit_bytes': initialize, 'used_bytes': tree_bytes(root) + 1024**2,
                   'reservations': {}, 'unit': 'decimal bytes; hardlinks counted once'}
        else:
            doc = json.loads(path.read_text())
        if reserve is not None:
            if doc['used_bytes'] + sum(doc['reservations'].values()) + TASK_RESERVATION > doc['limit_bytes']:
                raise CapacityPause('250 GB acquisition budget has insufficient unreserved space')
            doc['reservations'][reserve] = TASK_RESERVATION
        if finish is not None:
            key, used = finish
            if used > doc['reservations'][key]:
                raise RuntimeError('Task exceeded its storage reservation')
            doc['used_bytes'] += used
            del doc['reservations'][key]
        save(path, doc)
        return doc


def validate_bars(rows, start, end, previous=None):
    schema = pa.schema([('timestamp', pa.timestamp('ns', tz='UTC'))] +
                       [(c, pa.float64()) for c in ('Open', 'High', 'Low', 'Close', 'Volume')])
    if not rows:
        return pa.Table.from_batches([], schema=schema), previous
    frame = pd.DataFrame(rows).rename(columns={'t': 'timestamp', 'o': 'Open',
        'h': 'High', 'l': 'Low', 'c': 'Close', 'v': 'Volume'})
    frame['timestamp'] = pd.to_datetime(frame.timestamp, utc=True)
    stamps = frame.timestamp
    if (not stamps.is_monotonic_increasing or stamps.duplicated().any()
            or (previous is not None and stamps.iloc[0] <= previous)
            or (stamps < pd.Timestamp(start)).any() or (stamps >= pd.Timestamp(end)).any()
            or (stamps.dt.second != 0).any() or (stamps.dt.microsecond != 0).any()):
        raise ValueError('Stock page has invalid, duplicate, unordered or out-of-window minute timestamps')
    cols = ['Open', 'High', 'Low', 'Close', 'Volume']
    import numpy as np
    values = frame[cols].to_numpy(dtype=float)
    if (not np.isfinite(values).all() or (values[:, :4] <= 0).any()
            or (values[:, 4] < 0).any()
            or (frame.High < frame[['Open', 'Low', 'Close']].max(axis=1)).any()
            or (frame.Low > frame[['Open', 'High', 'Close']].min(axis=1)).any()):
        raise ValueError('Stock page OHLCV invalid')
    return pa.Table.from_pandas(frame[['timestamp', *cols]], schema=schema, preserve_index=False), stamps.iloc[-1]


def completed(root, task):
    path = root / task['key'] / 'complete.json'
    if not path.exists():
        return None
    doc = json.loads(path.read_text())
    if doc.get('task') != task or doc.get('complete') is not True or not doc.get('files'):
        raise RuntimeError('Completion receipt differs from requested task')
    for name, sha in doc['files'].items():
        if digest(path.parent / name) != sha:
            raise RuntimeError('Completed data hash mismatch')
    return doc


def acquire(root_text, task, reserve_gib):
    pa.set_cpu_count(1); pa.set_io_thread_count(1)
    root = Path(root_text)
    old = completed(root, task)
    if old:
        return {'key': task['key'], 'status': 'reused', 'rows': old.get('rows')}
    disk_guard(root, reserve_gib)
    reservation = uuid.uuid4().hex
    quota_update(root.parent, reserve=reservation)
    destination = root / task['key']
    before = tree_bytes(destination) if destination.exists() else 0
    try:
        return acquire_reserved(root, task, reserve_gib)
    finally:
        used = (tree_bytes(destination) if destination.exists() else 0) - before
        quota_update(root.parent, finish=(reservation, max(used, 0)))


def acquire_reserved(root, task, reserve_gib):
    dest = root / task['key']
    attempt = dest / ('attempt-' + uuid.uuid4().hex)
    attempt.mkdir(parents=True)
    files, count, upper_bound_bytes = {}, 0, 1024**2
    began = datetime.now(timezone.utc).isoformat()
    if task['kind'] == 'stock':
        params = {'symbols': task['symbol'], 'timeframe': '1Min', 'feed': 'sip',
            'adjustment': task['adjustment'], 'asof': '-', 'sort': 'asc', 'limit': 10000,
            'start': task['start'],
            'end': (pd.Timestamp(task['end']) - pd.Timedelta(nanoseconds=1)).isoformat()}
        seen, previous, writer = set(), None, None
        session = requests.Session()
        try:
            for page in range(1000):
                disk_guard(root, reserve_gib)
                raw, body = get_json(session, 'https://data.alpaca.markets/v2/stocks/bars', params)
                raw_path = attempt / f'page-{page:04d}.json.gz'
                compressed = gzip.compress(raw, mtime=0)
                bars = body.get('bars')
                if bars is not None and (not isinstance(bars, dict) or set(bars) - {task['symbol']}):
                    raise ValueError('Unexpected stock response symbols')
                table, previous = validate_bars((bars or {}).get(task['symbol'], []), task['start'], task['end'], previous)
                # Conservative bound includes both raw compressed pages and
                # decoded Parquet data/metadata before either is written.
                upper_bound_bytes += len(compressed) + 2 * table.nbytes + 1024**2
                if upper_bound_bytes > TASK_RESERVATION - 1024**2:
                    raise CapacityPause('Stock task needs smaller date shards to fit its reservation')
                raw_path.write_bytes(compressed)
                files[str(raw_path.relative_to(dest))] = digest(raw_path)
                if writer is None:
                    writer = pq.ParquetWriter(attempt / 'bars.parquet', table.schema, compression='zstd')
                writer.write_table(table); count += table.num_rows
                token = body.get('next_page_token')
                if not token:
                    break
                if token in seen:
                    raise ValueError('Repeated stock pagination token')
                seen.add(token); params['page_token'] = token
            else:
                raise ValueError('Stock pagination bound exceeded; capture incomplete')
        finally:
            if writer is not None:
                writer.close()
            session.close()
        files[str((attempt / 'bars.parquet').relative_to(dest))] = digest(attempt / 'bars.parquet')
    else:
        load_dotenv(ROOT / '.env')
        import boto3
        from botocore.config import Config
        client = boto3.client('s3', endpoint_url='https://files.massive.com',
            aws_access_key_id=os.environ['MASSIVE_FLAT_FILES_API_KEY'],
            aws_secret_access_key=os.environ['MASSIVE_FLAT_FILES_API_SECRET'],
            config=Config(signature_version='s3v4', retries={'max_attempts': 5}, read_timeout=60))
        try:
            response = client.get_object(Bucket='flatfiles', Key=task['object'])
            if response['ContentLength'] > TASK_RESERVATION - 1024**2:
                response['Body'].close()
                raise CapacityPause('Massive object exceeds one task storage reservation')
            target = attempt / 'data.csv.gz'
            body = response['Body']
            try:
                with target.open('wb') as f:
                    for block in body.iter_chunks(4 * 1024**2):
                        disk_guard(root, reserve_gib); f.write(block)
                    f.flush(); os.fsync(f.fileno())
            finally:
                body.close()
            if target.stat().st_size != response['ContentLength']:
                raise RuntimeError('Incomplete Massive object')
            # Read the complete gzip stream to verify its trailer/CRC, with bounded memory.
            with gzip.open(target, 'rb') as f:
                while f.read(4 * 1024**2):
                    pass
            files[str(target.relative_to(dest))] = digest(target)
        except CapacityPause:
            raise
        except Exception as exc:
            # Never leak SDK request URLs/credential fields into status.
            raise RuntimeError(f'Massive object download failed ({type(exc).__name__})') from None
    receipt = {'task': task, 'complete': True, 'files': files, 'rows': count if task['kind'] == 'stock' else None,
        'started_at': began, 'completed_at': datetime.now(timezone.utc).isoformat(),
        'coverage_validated': False, 'adjustment_vintage': 'provider values at capture time',
        'empty_policy': 'Observed empty is not evidence of pre-listing or verified coverage'}
    save(dest / 'complete.json', receipt)
    return {'key': task['key'], 'status': 'downloaded', 'rows': receipt['rows']}


def tasks(symbols, sessions, start, end, kinds):
    if 'stock' in kinds:
        # Recent and boundary examples arrive early for validation/benchmarks.
        years = sorted(range(date.fromisoformat(start).year, date.fromisoformat(end).year + 1),
                       key=lambda y: (y != 2022, y != date.fromisoformat(end).year, y))
        for symbol in sorted(set(symbols), key=lambda s: (s not in ('SPY', 'QQQ'), s)):
            if not symbol or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-' for c in symbol):
                raise ValueError('Invalid symbol')
            for year in years:
                lo, hi = max(start, f'{year}-01-01'), min(end, f'{year}-12-31')
                for adjustment in ('raw', 'all'):
                    yield {'kind': 'stock', 'key': f'stock_1m/{adjustment}/{symbol}/{year}',
                           'symbol': symbol, 'adjustment': adjustment,
                           'start': pd.Timestamp(lo, tz='America/New_York').isoformat(),
                           'end': pd.Timestamp(date.fromisoformat(hi) + timedelta(days=1), tz='America/New_York').isoformat()}
    for kind in ('day_aggs', 'minute_aggs'):
        if kind in kinds:
            for item in sessions:
                day = item['date']
                if start <= day <= end:
                    y, m, _ = day.split('-')
                    yield {'kind': kind, 'key': f'options/{kind}/{day}',
                        'object': f'us_options_opra/{kind}_v1/{y}/{m}/{day}.csv.gz'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--plan', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--workers', type=int, required=True)
    ap.add_argument('--reserve-gib', type=int, default=100)
    ap.add_argument('--budget-gb', type=int, default=250)
    ap.add_argument('--warmup-start', default='2021-01-01')
    ap.add_argument('--kinds', default='stock,day_aggs,minute_aggs')
    ap.add_argument('--limit', type=int)
    args = ap.parse_args()
    if not 1 <= args.workers <= 4 or args.reserve_gib < 20 or not 1 <= args.budget_gb <= 250 or (args.limit is not None and args.limit < 1):
        ap.error('Use 1–4 workers, at least 20 GiB reserve and a positive optional limit')
    kinds = args.kinds.split(',')
    if not set(kinds) <= {'stock', 'day_aggs', 'minute_aggs'}:
        ap.error('Invalid kinds')
    plan = json.loads(args.plan.read_text())['plan']
    if plan.get('version') != 'v7':
        ap.error('Expected a V7 plan')
    check = {k: v for k, v in plan.items() if k != 'plan_sha256'}
    if hashlib.sha256(json.dumps(check, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest() != plan['plan_sha256']:
        ap.error('V7 plan hash mismatch')
    start, end = plan['historical_window']
    if args.warmup_start > start:
        ap.error('Warmup must start on or before research history')
    output = args.output.absolute(); output.mkdir(parents=True, exist_ok=True)
    with (output.parent / '.acquisition.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        specification = {'schema': 'v7-base-acquisition-v1', 'plan_sha256': plan['plan_sha256'],
            'warmup_start': args.warmup_start, 'end': end, 'kinds': kinds,
            'source_sha256': digest(__file__), 'stock_mapping': 'asof=-; reconcile old roots separately',
            'research_ready': False}
        pinned = output / 'acquisition.json'
        if pinned.exists() and json.loads(pinned.read_text()) != specification:
            raise ValueError('Acquisition scope/source changed; use a new output directory')
        if not pinned.exists():
            save(pinned, specification)
        calendar_path = output / 'calendar.json'
        if not calendar_path.exists():
            with requests.Session() as session:
                raw, records = get_json(session, 'https://paper-api.alpaca.markets/v2/calendar',
                                        {'start': args.warmup_start, 'end': end})
            if not isinstance(records, list) or not records:
                raise ValueError('Calendar response invalid')
            (output / 'calendar.raw.json').write_bytes(raw)
            save(calendar_path, {'provider': 'alpaca_calendar', 'timezone': 'America/New_York',
                'coverage_start': args.warmup_start, 'coverage_end': end, 'sessions': records})
        calendar = json.loads(calendar_path.read_text())
        quota_update(output.parent, initialize=args.budget_gb * 1_000_000_000)
        # Include explicitly known old exchange roots without rewriting their history.
        symbols = sorted(set(plan['catalog']['symbols']) | {'SQ', 'FI', 'BITF', 'BRK.B'})
        symbols = [s for s in symbols if s != 'BRKB']
        pending_tasks = list(tasks(symbols, calendar['sessions'], args.warmup_start, end, kinds))
        # Start each data source early, then interleave deterministic shards.
        first = ['stock_1m/raw/SPY/2022', 'stock_1m/all/SPY/2022',
                 f'options/day_aggs/{start}', f'options/minute_aggs/{start}']
        pending_tasks.sort(key=lambda t: (first.index(t['key']) if t['key'] in first else len(first),
                                          hashlib.sha256(t['key'].encode()).hexdigest()))
        if args.limit:
            pending_tasks = pending_tasks[:args.limit]
        status = {'status': 'running', 'total': len(pending_tasks), 'completed': 0, 'failed': 0,
                  'workers': args.workers, 'budget_gb': args.budget_gb,
                  'research_ready': False, 'last_results': [], 'paused_capacity': False}
        save(output / 'status.json', status)
        # Bounded submission, not one future per entire universe.
        iterator = iter(pending_tasks)
        with ProcessPoolExecutor(max_workers=args.workers, mp_context=multiprocessing.get_context('spawn')) as pool:
            active = {}
            def submit():
                item = next(iterator, None)
                if item is not None:
                    active[pool.submit(acquire, str(output), item, args.reserve_gib)] = item
            for _ in range(args.workers):
                submit()
            while active:
                done, _ = wait(active, timeout=30, return_when=FIRST_COMPLETED)
                for future in done:
                    item = active.pop(future)
                    try:
                        result = future.result(); status['completed'] += 1
                    except CapacityPause as exc:
                        result = {'key': item['key'], 'status': 'paused_capacity', 'error': str(exc)}
                        status['paused_capacity'] = True
                    except Exception as exc:
                        result = {'key': item['key'], 'status': 'failed', 'error': str(exc)}
                        status['failed'] += 1
                    print(json.dumps(result), flush=True)
                    status['last_results'] = (status['last_results'] + [result])[-12:]
                    if status['failed'] < 20 and not status['paused_capacity']:
                        submit()
                status['active'] = [t['key'] for t in active.values()]
                status['updated_at'] = datetime.now(timezone.utc).isoformat()
                save(output / 'status.json', status)
        status['status'] = ('paused_capacity' if status['paused_capacity'] else
                            'complete' if not status['failed'] else 'incomplete')
        save(output / 'status.json', status)


if __name__ == '__main__':
    main()
