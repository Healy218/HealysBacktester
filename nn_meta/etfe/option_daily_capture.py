"""Isolated daily option-bar capture establishing dated contract existence for ETFE selection."""
from collections import Counter
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shutil
import time
import uuid

import pandas as pd
import psutil
import requests

ROOT = Path(__file__).resolve().parents[2]
SYMBOLS = ('SPY', 'QQQ', 'VOO')
END = '2026-10-03T04:00:00Z'
ROUTES = {'option_daily_bars': ('https://data.alpaca.markets/v1beta1/options/bars', 'data', 'bars')}
OCC = re.compile(r'(SPY|QQQ|VOO)\d{6}[CP]\d{8}')
SOURCES = ('nn_meta/etfe/option_daily_capture.py', 'nn_meta/etfe/existence_census.py',
           'scripts/capture_etfe_existence.py', 'docs/specs/ETFE_EXISTENCE_CENSUS_20261006.md')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(value):
    return sha(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode())


def write_new(path, raw):
    """Publish a complete immutable file; orphan temporary files are not commits."""
    path = Path(path)
    temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    with temporary.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.link(temporary, path)  # fails rather than replacing an existing artifact
    temporary.unlink()
    descriptor = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def save(path, value):
    write_new(path, (json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n').encode())


def job(route, params, purpose):
    if route != 'option_daily_bars' or set(params) != {'symbols','timeframe','start','end','sort','limit'}:
        raise ValueError('Explicit daily option bar route and parameters required')
    symbols = params['symbols'].split(',')
    if (not 1 <= len(symbols) <= 100 or len(set(symbols)) != len(symbols)
            or not all(OCC.fullmatch(x) for x in symbols)):
        raise ValueError('One to one hundred distinct ETF option symbols required')
    if params['timeframe'] != '1Day' or params['sort'] != 'asc' or not 1 <= params['limit'] <= 10000:
        raise ValueError('Ascending daily bars with bounded page size required')
    start, end = pd.Timestamp(params['start']), pd.Timestamp(params['end'])
    if start.tzinfo is None or end.tzinfo is None or not start <= end < pd.Timestamp(END):
        raise ValueError('Aware bar interval within fixed end required')
    value = dict(route=route, params=dict(params), purpose=purpose)
    return dict(value, id=digest(value))


def prepare(root, jobs, *, parent=None, max_total_requests=256):
    root = Path(root)
    if len({j['id'] for j in jobs}) != len(jobs) or not jobs:
        raise ValueError('Unique nonempty request inventory required')
    for item in jobs:
        if job(item['route'], item['params'], item['purpose']) != item:
            raise ValueError('Request identity mismatch')
    plan = dict(schema='etfe-option-daily-capture-v1', expert='etfe', provider='alpaca',
        jobs=jobs, parent=parent, end_exclusive_utc=END, verified_start_utc=None,
        legacy_data_inputs=[], ready_for_build=False, ready_for_training=False,
        sources={n:sha((ROOT/n).read_bytes()) for n in SOURCES},
        limits=dict(max_requests_per_run=128, max_total_requests=max_total_requests, max_elapsed_seconds=1800,
                    max_root_bytes=4*2**30, max_page_bytes=32*2**20,
                    min_request_interval_seconds=1.0, max_attempts_per_page=5))
    plan['sha256'] = digest(plan)
    root.mkdir(parents=True, exist_ok=False)
    save(root/'PLAN.json', plan)
    for name in SOURCES:
        target = root/'source'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        write_new(target, (ROOT/name).read_bytes())
    return plan


def load_plan(root):
    root = Path(root)
    plan = json.loads((root/'PLAN.json').read_text())
    if digest({k:v for k,v in plan.items() if k != 'sha256'}) != plan['sha256']:
        raise ValueError('Plan checksum changed')
    if (plan['schema'] != 'etfe-option-daily-capture-v1' or plan['provider'] != 'alpaca'
            or plan['legacy_data_inputs'] or plan['ready_for_build'] or plan['ready_for_training']):
        raise ValueError('Fresh unadmitted Alpaca plan required')
    for name, expected in plan['sources'].items():
        if sha((root/'source'/name).read_bytes()) != expected or sha((ROOT/name).read_bytes()) != expected:
            raise ValueError('Capture source changed; prepare a successor')
    for item in plan['jobs']:
        if job(item['route'], item['params'], item['purpose']) != item:
            raise ValueError('Request identity mismatch')
    return plan


def rows(body, item):
    """Check shape without turning absent fields or error bodies into empty history."""
    field = ROUTES[item['route']][2]
    if not isinstance(body, dict) or field not in body or 'next_page_token' not in body:
        raise ValueError('Missing response schema fields')
    token = body['next_page_token']
    if token is not None and (not isinstance(token, str) or not token):
        raise ValueError('Invalid continuation token')
    value = body[field]
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ValueError('Invalid bar map')
    for symbol, records in value.items():
        if symbol not in item['params']['symbols'].split(',') or not isinstance(records, list):
            raise ValueError('Unexpected bar identity')
        for row in records:
            if not isinstance(row, dict) or not all(k in row for k in ('t','o','h','l','c','v','n','vw')):
                raise ValueError('Missing bar fields')
            stamp = pd.Timestamp(row['t'])
            if stamp.tzinfo is None or not pd.Timestamp(item['params']['start']) <= stamp <= pd.Timestamp(item['params']['end']):
                raise ValueError('Bar outside requested interval')
            yield symbol, row


def committed(root, item):
    """Reconstruct cursor only from hash-verified, contiguous committed pages."""
    folder = Path(root)/'jobs'/item['id']
    token, seen, complete = None, set(), False
    pages = []
    for ordinal, path in enumerate(sorted(folder.glob('page-*.json'))):
        if complete or path.name != f'page-{ordinal:06d}.json':
            raise ValueError('Broken page chain')
        page = json.loads(path.read_text())
        expected = dict(item['params'])
        if token is not None:
            expected['page_token'] = token
        attempt = Path(root)/page['attempt']
        if not attempt.resolve().is_relative_to(Path(root).resolve()):
            raise ValueError('Invalid receipt path')
        receipt = json.loads((attempt/'receipt.json').read_text())
        raw = (attempt/'body.json').read_bytes()
        if (page['receipt_sha256'] != sha((attempt/'receipt.json').read_bytes())
                or receipt['body_sha256'] != sha(raw) or receipt['params'] != expected
                or receipt['route'] != item['route'] or receipt['status'] != 200):
            raise ValueError('Committed response checksum/identity mismatch')
        body = json.loads(raw)
        list(rows(body, item))
        token = body['next_page_token']
        if token is not None and token in seen:
            raise ValueError('Repeated page token')
        seen.add(token)
        complete = token is None
        pages.append((receipt, body, page['attempt']))
    return pages, token, complete


class HTTP:
    def __init__(self, credentials):
        self.credentials = credentials
        self.session = requests.Session()

    def get(self, route, params, max_bytes):
        url, role, _ = ROUTES[route]
        key, secret = self.credentials[role]
        try:
            with self.session.get(url, params=params, headers={
                    'APCA-API-KEY-ID':key, 'APCA-API-SECRET-KEY':secret},
                    timeout=(10,20), stream=True, allow_redirects=False) as response:
                raw = bytearray()
                for block in response.iter_content(65536):
                    raw.extend(block)
                    if len(raw) > max_bytes:
                        return None, b'', {}, 'page_byte_limit'
                if any(v.encode() in raw for pair in self.credentials.values() for v in pair if v):
                    return None, b'', {}, 'credential_echo'
                allowed = {'retry-after','x-request-id','x-ratelimit-limit','x-ratelimit-remaining','x-ratelimit-reset'}
                headers = {k.lower():v for k,v in response.headers.items() if k.lower() in allowed}
                # Whitelisted headers must not echo secrets either.
                if any(v in json.dumps(headers) for pair in self.credentials.values() for v in pair if v):
                    return None, b'', {}, 'credential_echo'
                return response.status_code, bytes(raw), headers, None
        except requests.RequestException:
            return None, b'', {}, 'transport_error'


def resources(root):
    disk, ram = shutil.disk_usage(root), psutil.virtual_memory()
    return dict(disk_free=disk.free, disk_total=disk.total, ram_available=ram.available,
                ram_total=ram.total, rss=psutil.Process().memory_info().rss)


def guard(root, limits):
    measured = resources(root)
    if measured['disk_free'] < max(100*2**30, measured['disk_total']*.2)+limits['max_page_bytes']:
        raise RuntimeError('disk_reserve')
    if measured['ram_available'] < max(2*2**30, measured['ram_total']*.2)+256*2**20:
        raise RuntimeError('memory_reserve')
    size = sum(p.stat().st_size for p in Path(root).rglob('*') if p.is_file())
    if size+limits['max_page_bytes'] > limits['max_root_bytes']:
        raise RuntimeError('storage_budget')


def capture(root, http, *, request_budget=None, sleep=time.sleep, check_resources=guard):
    root = Path(root)
    plan = load_plan(root)
    limits = plan['limits']
    budget = min(request_budget if request_budget is not None else limits['max_requests_per_run'],
                 limits['max_requests_per_run'])
    started, last_request, calls, reason = time.monotonic(), 0.0, 0, None
    before = resources(root)
    with (root/'writer.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            waits = [json.loads(p.read_text())['not_before_epoch'] for p in (root/'waits').glob('*.json')]
            if waits and max(waits) > time.time():
                raise RuntimeError('provider_wait_pending')

            def provider_wait(delay):
                wait_root = root/'waits'
                wait_root.mkdir(exist_ok=True)
                save(wait_root/(uuid.uuid4().hex+'.json'), dict(not_before_epoch=time.time()+delay))
                if delay > 60:
                    raise RuntimeError('provider_wait_required')
                sleep(delay)

            for item in plan['jobs']:
                history, token, done = committed(root, item)
                folder = root/'jobs'/item['id']
                folder.mkdir(parents=True, exist_ok=True)
                failures = 0
                seen = {b['next_page_token'] for _,b,_ in history}
                while not done:
                    if calls >= budget:
                        raise RuntimeError('request_budget')
                    if time.monotonic()-started >= limits['max_elapsed_seconds']:
                        raise RuntimeError('elapsed_budget')
                    check_resources(root, limits)
                    sleep(max(0, limits['min_request_interval_seconds']-(time.monotonic()-last_request)))
                    params = dict(item['params'])
                    if token is not None:
                        params['page_token'] = token
                    observed_at = datetime.now(timezone.utc).isoformat()
                    last_request = time.monotonic()
                    reservations = root/'request_reservations'
                    reservations.mkdir(exist_ok=True)
                    spent = len(list(reservations.glob('*.json')))
                    if spent >= limits['max_total_requests']:
                        raise RuntimeError('study_request_budget')
                    save(reservations/f'{spent:06d}.json', dict(route=item['route'], params=params))
                    status, raw, headers, error = http.get(item['route'], params, limits['max_page_bytes'])
                    calls += 1
                    attempt = root/'attempts'/uuid.uuid4().hex
                    attempt.mkdir(parents=True)
                    write_new(attempt/'body.json', raw)
                    receipt = dict(route=item['route'], url=ROUTES[item['route']][0], params=params,
                        observed_at=observed_at, received_at=datetime.now(timezone.utc).isoformat(),
                        status=status, error=error, headers=headers, body_sha256=sha(raw), bytes=len(raw),
                        plan_sha256=plan['sha256'], credential_role=ROUTES[item['route']][1])
                    save(attempt/'receipt.json', receipt)
                    if error or status != 200:
                        failures += 1
                        retryable = error == 'transport_error' or status == 429 or (status is not None and status >= 500)
                        if not retryable or failures >= limits['max_attempts_per_page']:
                            raise RuntimeError(f'request_failed:{status}:{error}')
                        delay = 2**(failures-1)
                        try:
                            delay = max(delay, float(headers.get('retry-after', 0)))
                        except ValueError:
                            from email.utils import parsedate_to_datetime
                            delay = max(delay, (parsedate_to_datetime(headers['retry-after'])-datetime.now(timezone.utc)).total_seconds())
                        provider_wait(delay)
                        continue
                    body = json.loads(raw)
                    list(rows(body, item))
                    next_token = body['next_page_token']
                    if next_token is not None and next_token in seen:
                        raise ValueError('Repeated page token')
                    save(folder/f'page-{len(history):06d}.json', dict(
                        attempt=str(attempt.relative_to(root)),
                        receipt_sha256=sha((attempt/'receipt.json').read_bytes())))
                    history.append((receipt, body, str(attempt.relative_to(root))))
                    seen.add(next_token)
                    token, done, failures = next_token, next_token is None, 0
                    remaining = headers.get('x-ratelimit-remaining')
                    if remaining == '0':
                        delay = max(1, float(headers.get('x-ratelimit-reset', time.time()+60))-time.time())
                        provider_wait(delay)
        except (RuntimeError, ValueError) as exc:
            reason = str(exc)
        report = audit(root)
        report.update(requests_this_run=calls, stop_reason=reason,
                      elapsed_seconds=time.monotonic()-started, resources_before=before,
                      resources_after=resources(root), peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
        runs = root/'runs'
        runs.mkdir(exist_ok=True)
        save(runs/(uuid.uuid4().hex+'.json'), report)
    return report


def iter_records(root, item):
    history, _, complete = committed(root, item)
    if not complete:
        raise ValueError('Partition has not reached terminal page')
    for page, (receipt, body, attempt) in enumerate(history):
        for ordinal, (symbol, row) in enumerate(rows(body, item)):
            yield dict(symbol=symbol, raw=row, source=dict(attempt=attempt,
                page=page, ordinal=ordinal, body_sha256=receipt['body_sha256']))


def audit(root):
    plan = load_plan(root)
    summary = []
    for item in plan['jobs']:
        history, token, complete = committed(root, item)
        counts, minimum, maximum, previous, backwards = Counter(), None, None, {}, 0
        for _, body, _ in history:
            for symbol, row in rows(body, item):
                counts[symbol] += 1
                if 't' in row:
                    stamp = pd.Timestamp(row['t']).value
                    minimum = stamp if minimum is None else min(minimum, stamp)
                    maximum = stamp if maximum is None else max(maximum, stamp)
                    backwards += int(stamp < previous.get(symbol, stamp))
                    previous[symbol] = stamp
        summary.append(dict(id=item['id'], route=item['route'], purpose=item['purpose'],
            pages=len(history), terminal=complete, continuation_pending=token is not None,
            rows=sum(counts.values()), rows_by_symbol=dict(counts), min_timestamp_ns=minimum,
            max_timestamp_ns=maximum, out_of_order=backwards,
            disposition=('captured' if counts else 'empty_response') if complete else 'transport_incomplete'))
    return dict(schema='etfe-fresh-capture-audit-v1', plan_sha256=plan['sha256'],
        observed_at=datetime.now(timezone.utc).isoformat(), partitions=summary,
        capture_complete=all(p['terminal'] for p in summary),
        ready_for_build=False, ready_for_training=False, legacy_data_inputs=[])
