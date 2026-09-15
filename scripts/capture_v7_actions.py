"""Capture whole-market split/dividend records for raw-price basis reconciliation."""
from pathlib import Path
import argparse
from datetime import datetime, timezone
import gzip
import json
import os
import sys
import time
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
import uuid
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import requests
    from dotenv import load_dotenv
    from nn_meta.v7.storage import transaction, receipt, verify, identity, sha
    from scripts.download_v7_data import quota_update, tree_bytes, TASK_RESERVATION
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--budget-root', type=Path, required=True)
    ap.add_argument('--start', required=True)
    ap.add_argument('--end', required=True)
    ap.add_argument('--request-interval-seconds', type=float, default=13.,
                    help='Conservative pacing for the stock-reference entitlement')
    args = ap.parse_args()
    for value in (args.start, args.end):
        if datetime.strptime(value, '%Y-%m-%d').strftime('%Y-%m-%d') != value:
            raise ValueError('Explicit ISO dates required')
    if (args.start > args.end or not args.output.resolve().is_relative_to(args.budget_root.resolve())
            or not 1 <= args.request_interval_seconds <= 60):
        raise ValueError('Chronological scope and shared quota required')
    load_dotenv(ROOT / '.env')
    session = requests.Session()
    source_hash = sha(__file__)
    for kind, date_field in (('splits', 'execution_date'), ('dividends', 'ex_dividend_date')):
        path = '/stocks/v1/' + kind
        query = {date_field + '.gte': args.start, date_field + '.lte': args.end,
                 'limit': 5000, 'sort': date_field + '.asc'}
        declaration = {'path': path, 'params': query}
        fingerprint = identity(declaration)
        dest = args.output / kind
        if dest.exists():
            verify(dest, expected_identity=fingerprint)
            continue
        key = uuid.uuid4().hex
        quota_update(args.budget_root, reserve=key)
        used, count = 0, 0
        try:
            with transaction(dest) as temp:
                url, params, seen, ids = 'https://api.massive.com' + path, query, set(), set()
                for page in range(1000):
                    if url in seen or sha(__file__) != source_hash:
                        raise ValueError('Pagination loop or changed capture source')
                    seen.add(url)
                    for attempt in range(5):
                        time.sleep(args.request_interval_seconds)
                        try:
                            response = session.get(url, params=params, timeout=30, allow_redirects=False,
                                headers={'Authorization': 'Bearer ' + os.environ['MASSIVE_API_KEY']})
                        except requests.RequestException:
                            raise RuntimeError('Corporate action transport failed') from None
                        if response.status_code not in (429, 500, 502, 503, 504):
                            break
                        time.sleep(20 if response.status_code == 429 else 2 ** attempt)
                    if response.status_code != 200:
                        raise RuntimeError(f'Corporate action HTTP {response.status_code}')
                    body = response.json()
                    if body.get('status') != 'OK' or not isinstance(body.get('results'), list):
                        raise ValueError('Invalid corporate action response')
                    for row in body['results']:
                        if (not args.start <= row.get(date_field, '') <= args.end
                                or not row.get('ticker') or not row.get('id') or row['id'] in ids):
                            raise ValueError('Duplicate or out-of-scope action')
                        ids.add(row['id'])
                    payload = gzip.compress(json.dumps({'results': body['results'], 'status': 'OK'},
                                                       sort_keys=True).encode(), mtime=0)
                    if used + len(payload) > TASK_RESERVATION // 2:
                        raise ValueError('Capture exceeds reserved space')
                    (temp / f'page-{page:04d}.json.gz').write_bytes(payload)
                    used += len(payload)
                    count += len(body['results'])
                    print(json.dumps({'kind': kind, 'page': page, 'records': count}), flush=True)
                    if not body.get('next_url'):
                        break
                    parsed = urlsplit(body['next_url'])
                    if parsed.scheme != 'https' or parsed.netloc != 'api.massive.com' or parsed.path != path:
                        raise ValueError('Pagination changed origin or endpoint')
                    url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path,
                        urlencode([(k, v) for k, v in parse_qsl(parsed.query) if k.lower() != 'apikey']), ''))
                    params = None
                else:
                    raise ValueError('Pagination budget exhausted')
                receipt(temp, {'identity': fingerprint, 'query': declaration, 'records': count,
                    'pages': page + 1, 'retrieved_at': datetime.now(timezone.utc).isoformat(),
                    'source_sha256': source_hash, 'historical_publication_vintage_verified': False,
                    'purpose': 'event-date price reconciliation; cumulative current-share factors are not PIT inputs'})
                used = tree_bytes(temp)
        finally:
            if not dest.exists():
                used = sum(tree_bytes(p) for p in dest.parent.glob(dest.name + '.partial-*'))
            quota_update(args.budget_root, finish=(key, used))


if __name__ == '__main__':
    main()
